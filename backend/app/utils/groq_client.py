from __future__ import annotations
import functools
"""
groq_client.py — Groq LLM + Whisper integration.

Public API:
  analyze_with_rag(query, context_chunks, language) → LegalAnalysis
  transcribe_audio(audio_bytes, language)           → str
"""
import json
import re
import time
import logging
import tempfile
import os
from dataclasses import dataclass, field
from typing import Optional
# streamlit removed for FastAPI backend
from app.utils.legal_taxonomy import LEGAL_CASE_TYPES
from app.utils.grounding import text_list, validate_citations
from app.utils.prompts import CASE_ANALYSIS, DOCUMENT_ANALYSIS
CATEGORY_STRING = " | ".join(LEGAL_CASE_TYPES)

from groq import Groq
from app.utils.config import (
    GROQ_API_KEY, GROQ_API_KEYS, GROQ_LLM_MODEL, GROQ_FAST_MODEL,
    GROQ_WHISPER_MODEL, LEGAL_CATEGORIES,
)

logger = logging.getLogger(__name__)


# ── Risk stabilization ────────────────────────────────────────────────────────

# HARD triggers: single-word evidence of immediate physical/legal danger.
# Matching any of these → High, regardless of LLM output.
# Includes English and Urdu script keywords.
_HARD_HIGH_KEYWORDS = [
    # Violent crime
    "murder", "qatl", "qatal", "killed", "killing", "kill me", "will kill",
    "marne ki", "qatl karna",
    "rape", "zina", "ziyadati", "yagana",
    "kidnap", "kidnapping", "abduction", "apeharna", "uthwa liya",
    # Weapons
    "gun", "weapon", "hathiyar", "bandook", "pistol",
    "bomb", "blast", "dhamaka",
    # Severe abuse
    "torture", "torture kiya", "tashadud kiya",
    "child abuse", "sexual abuse", "ghasb",
    "acid attack", "acid phenka", "tezaab",
    "honor killing", "ghairat ke naam par", "karo kari",
    "forced marriage", "jabri shadi", "jabri nikah",
    "domestic violence", "gharelu tashadud", "ghar mein maar",
    # Threats and missing persons
    "threat to kill", "jaan se maar", "qatal ki dhamki", "marne ki dhamki",
    "missing person", "laapta", "ghaib hai",
    # Trafficking
    "trafficking", "insani sodagari", "kill",
"kill me",
"he will kill me",
"murder",
"suicide",
"rape",
"gunpoint",
"terrorist",
"terrorism",
"jaan se maar",
"جان سے مار",
"قتل",
"قتل کی دھمکی",
"خودکشی",
    # Urdu script violence/assault (critical — always escalate)
    "تشدد",        # violence / assault
    "مار پیٹ",     # beating
    "حملہ",        # attack
    "تجاوز",       # assault / violation
    "ریپ",         # rape (transliterated)
    "اغوا",        # kidnapping
    "اغواء",
    "قتل کرنا",
    "جان کو خطرہ", # life in danger
]

# SOFT triggers: serious but contextual — only raise to High if NOT a
# pure informational question.
_SOFT_HIGH_KEYWORDS = [
    # Physical
    "assault", "attack kiya", "beating", "maar peet", "maara hai",
    "hit me", "mujhe maara",
    # Police / legal action
    "arrested", "arrest kar liya", "giraftar", "giraftari",
    "jail", "imprisonment", "hawaalaati", "thana le gaye",
    "fir registered against", "mukadma",
    # Harassment
    "harassment", "tang kar raha", "zulm", "tashaddud", "pareshan",
    "stalker", "stalking", "peecha kar raha",
    # Intimidation
    "blackmail", "blackmail kar raha",
    "extortion", "bhata", "paise mang raha",
    "threats", "dhamkiyan", "dhamki di",
    "intimidation", "darra raha",
]

# Informational prefixes that cancel soft-trigger escalation.
_INFO_PREFIXES = [
    "what is", "kya hai", "what are", "kya hain",
    "how to file", "how to register", "how to apply",
    "kaise darj karein", "kaise karein", "kaise file karein",
    "how do i", "how does", "kaise hota",
    "explain", "explanation", "definition", "taareef",
    "tell me about", "tell me", "inform", "learn about",
    "general information", "understand", "know my rights",
    "what happens", "kya hota hai",
    "can i", "kya main",
    "is it legal", "is it illegal",
]

_HIGH_RISK_CATEGORIES = {"Criminal Law", "Harassment"}

_MEDIUM_DEFAULT_CATEGORIES = {
    "Family Law", "Labour Law", "Property Law", "Property / Tenancy",
    "Contract Law", "Civil Law / Procedure", "Inheritance Law",
    "Consumer Rights",
}


def _is_info_query(q_lower: str) -> bool:
    """Return True if the query looks like a general information request."""
    # Check explicit prefix patterns
    if any(q_lower.startswith(p) or f" {p} " in q_lower for p in _INFO_PREFIXES):
        return True
    # Pattern: 'kaise X karein' — flexible to allow words between kaise and karein.
    import re as _re
    if _re.search(r'\bkaise\b.{0,30}\b(karein|hota|kar(ein|en)|darj)\b', q_lower):
        return True
    return False


def _matches_risk_term(term: str, text: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.IGNORECASE))


def stabilize_risk(
    llm_risk: str,
    query: str,
    category: str,
) -> tuple[str, str]:
    """
    Rule-based stabilization applied AFTER LLM output.

    Priority order:
      1. Hard High keyword match → always High
      2. Pure informational query → Low (overrides Medium/High without evidence)
      3. Soft High keyword + NOT an info query → High
      4. High-risk category + LLM says Low → raise to Medium
      5. Benign category + LLM says High + no keyword evidence → lower to Medium
      6. Otherwise trust LLM value

    Returns (stabilized_level, reason_string).
    reason_string is "" when LLM value is kept unchanged.
    """
    q_lower   = query.lower()
    cat_lower = category.lower()

    # Questions about a reported event are still active cases. A question
    # prefix must never erase a user's report of abuse or danger.
    is_info = _is_info_query(q_lower)
    active_case = bool(re.search(
        r"\b(my (?:employer|husband|wife|landlord|child|brother|sister|family)|"
        r"(?:he|she|they) (?:will|has|have|is|are)|me|threatened|threatening|unpaid|"
        r"not paid|was arrested|been arrested|was assaulted)\b|میرے|میرا|مجھے|دھمکی", q_lower
    ))
    if is_info and not active_case:
        return "Low", "General information request; no current incident was described."

    # Rule 1: hard physical/criminal danger keywords
    hard_hit = any(_matches_risk_term(kw, q_lower) for kw in _HARD_HIGH_KEYWORDS)
    if hard_hit:
        return (
            "Critical",
            "Threat-to-life, severe violence, or major criminal danger detected.",
        )
    # Rule 2: pure informational queries → Low
    is_info = _is_info_query(q_lower)
    _all_benign_for_info = _MEDIUM_DEFAULT_CATEGORIES | {
        "Inheritance Law", "Constitutional Law", "General / Other",
        "Criminal Law", "Harassment",   # procedural info ("how to file FIR") is not dangerous
    }
    if is_info and not active_case and len(query.split()) < 20:
        if llm_risk in ("High", "Medium"):
            return "Low", "Informational query with no immediate active legal emergency."

    # Rule 3: soft high keywords — escalate only if not informational
    soft_hit = any(_matches_risk_term(kw, q_lower) for kw in _SOFT_HIGH_KEYWORDS)
    if soft_hit and (not is_info or active_case) and llm_risk != "High":
        return "High", "Query contains indicators of serious legal risk."

    # Rule 4: high-risk category + LLM gave Low → raise to Medium
    high_cat = category in _HIGH_RISK_CATEGORIES
    if high_cat and llm_risk == "Low":
        return "Medium", f"{category} matters carry inherent complexity; risk raised to Medium."

    # Rule 5: benign category + LLM says High without keyword evidence → Medium
    benign_cat = category in _MEDIUM_DEFAULT_CATEGORIES
    if benign_cat and llm_risk == "High" and not hard_hit and not soft_hit:
        return "Medium", f"{category} disputes are typically Medium risk without safety concerns."

    # Rule 6: trust LLM
    return llm_risk, ""


# ── Result dataclasses ────────────────────────────────────────────────────────

@dataclass
class LegalAnalysis:
    summary:      str = ""
    category:     str = "General / Other"
    laws:         list[str] = field(default_factory=list)
    rights:       list[str] = field(default_factory=list)
    next_steps:   list[str] = field(default_factory=list)
    risk_level: str = "Medium"   # Low | Medium | High | Critical
    risk_reason:  str = ""
    confidence:   str = "Medium"       # Low | Medium | High
    sources:      list[dict] = field(default_factory=list)  # retrieved chunks used
    error:        Optional[str] = None


@dataclass
class DocumentAnalysis:
    summary:             str       = ""
    key_legal_points:    list[str] = field(default_factory=list)
    deadlines:           list[str] = field(default_factory=list)
    procedural_guidance: list[str] = field(default_factory=list)
    risk_indicators:     list[str] = field(default_factory=list)
    cited_laws:          list[str] = field(default_factory=list)
    urdu_explanation:    str       = ""
    confidence:          str       = "Medium"
    disclaimer:          str       = ""
    error:               Optional[str] = None
    analyzed_characters: int = 0
    total_characters: int = 0
    segments_analyzed: int = 0
    truncated: bool = False


# ── Prompt builders ───────────────────────────────────────────────────────────

_LANG_INSTRUCTION = {
    "English": (
        "Respond ONLY in clear simple English. Every word in your JSON output must be in "
        "English. Do NOT use Urdu, Arabic, or any other script. Section numbers and dates "
        "stay as digits."
    ),
    "Urdu": (
        "تمام وضاحتیں سادہ اور قدرتی اردو رسم الخط میں دیں۔ "
        "قانون کے اصل سرکاری نام، زمرے اور خطرے/اعتماد کی مقررہ ویلیوز انگریزی میں رہیں۔ "
        "باقی جملوں میں انگریزی فقرے شامل نہ کریں۔ دفعہ نمبر اور تاریخ کے اعداد برقرار رکھیں۔"
    ),
}

_SYSTEM_PROMPT = CASE_ANALYSIS


# ── Legal intent detection ────────────────────────────────────────────────────
# Before calling the LLM, we classify whether the query is plausibly legal.
# This prevents the LLM from hallucinating laws for greetings / random text.

# Minimum character length for a query we'll even attempt to retrieve for
_MIN_LEGAL_QUERY_LEN = 8

# Signals that strongly suggest a legal issue is present
_LEGAL_SIGNAL_WORDS = [
    # English
    "rights", "law", "legal", "court", "police", "fir", "case", "complaint",
    "salary", "wages", "rent", "eviction", "divorce", "custody", "inheritance",
    "contract", "termination", "fired", "dismissed", "harassed", "harassment",
    "arrested", "bail", "property", "land", "deed", "fraud", "cheque",
    "notice", "lawyer", "advocate", "judge", "tribunal", "section", "act",
    "compensation", "damages", "penalty", "fine", "registration",
    "violence", "assault", "abuse", "theft", "robbery", "murder", "threat",
    "dispute", "illegal", "right", "claim", "sue", "court order",
    # Transliterated terms (still used as fallback)
    "haq", "adalat", "wakeel", "talaq", "kiraya", "tankhwah", "naukri",
    "giraftari", "mukadma", "thana", "mehr", "wirasat", "zemin",
    "makaan", "blackmail", "kirayadar", "tashaddud", "giraftar",
    "dhoka", "qanoon", "haqooq", "jaidad",
    # ── Urdu script — greatly expanded ────────────────────────────────────────
    # Core legal terms
    "حق", "عدالت", "وکیل", "طلاق", "کرایہ", "تنخواہ", "نوکری",
    "گرفتاری", "مقدمہ", "تھانہ", "وراثت", "زمین", "مکان",
    "معاوضہ", "دعویٰ", "شکایت", "ملازمت", "اجرت",
    # Violence / crime
    "تشدد", "مار", "پیٹنا", "چوری", "ڈکیتی", "قتل", "دھمکی",
    "ہراسانی", "ہراساں", "زیادتی", "بدسلوکی", "ظلم",
    # Police / FIR
    "پولیس", "گرفتار", "ایف آئی آر", "تھانہ", "گرفتاری",
    "درخواست", "رپورٹ", "مقدمہ درج",
    # Property / tenancy
    "جائیداد", "جائداد", "کرایہ دار", "مالک مکان", "بے دخل",
    "زمین", "رجسٹری", "تنازعہ", "قبضہ",
    # Family law
    "نکاح", "طلاق", "خلع", "مہر", "تحویل", "بچے", "بچوں",
    "حضانت", "نان نفقہ", "گھریلو",
    # Labour
    "تنخواہ", "نوکری", "ملازمت", "برخاستگی", "کام",
    "فیکٹری", "مزدور", "محنت",
    # Finance / fraud
    "دھوکہ", "فراڈ", "رقم", "قرض", "چیک", "ادائیگی",
    # Inheritance
    "وراثت", "ورثاء", "حصہ", "وصیت",
    # General legal
    "قانون", "حقوق", "انصاف", "سزا", "جرمانہ", "معاہدہ",
    "مدد", "مسئلہ", "مسئلے", "ضرورت", "مشورہ",
    # Action words that imply a legal dispute
    "نہیں دیا", "نہیں ملا", "نہیں ملی", "نکال دیا",
    "کیا ہے", "ہوا ہے", "ہوئی ہے", "کر رہا ہے",
]

# Patterns that almost certainly indicate a non-legal query
_NON_LEGAL_PATTERNS = [
    r'^\s*(hi|hello|hey|salam|assalam|السلام|مرحبا|ہیلو)\b',
    r'^\s*(how are you|kya haal|آپ کیسے)\b',
    r'^\s*(what is your name|aap ka naam|آپ کا نام)\b',
    r'^\s*(thank you|shukriya|شکریہ|thanks)\b',
    r'^\s*(test|testing|1234|abc)\b',
    r'^\s*(good morning|good night|good evening|subah bakhair|شب بخیر)\b',
]


def classify_legal_intent(query: str) -> str:
    """
    Lightweight pre-LLM classification of query legal intent.

    Returns one of:
      "legal"     — query has clear legal signals → proceed with full RAG+LLM
      "vague"     — emotional/personal but unclear legal issue → proceed but flag
      "non_legal" — greetings, random text, no legal content → short-circuit

    This never replaces the LLM — it's a filter before calling it.
    """
    q = query.strip()
    q_lower = q.lower()

    # Too short to be a meaningful legal query
    if len(q) < _MIN_LEGAL_QUERY_LEN:
        return "non_legal"

    # Check explicit non-legal patterns
    for pat in _NON_LEGAL_PATTERNS:
        if re.search(pat, q, re.IGNORECASE):
            return "non_legal"

    # Check for hard emergency keywords — always legal and urgent
    if any(kw in q_lower for kw in _HARD_HIGH_KEYWORDS):
        return "legal"

    # Check for legal signal words
    signals_found = sum(
        1 for w in _LEGAL_SIGNAL_WORDS
        if w in q_lower or w in q  # q for Urdu script match
    )
    if signals_found >= 1:
        return "legal"

    # Query has some length but no clear legal signal — treat as vague
    word_count = len(q.split())

    # Special case: Urdu script queries describing a situation are almost
    # always legal complaints. If the query contains Urdu script and is
    # long enough to be a sentence, treat as legal rather than vague.
    # Urdu uses shorter words than English so 6+ words = a full statement.
    _has_urdu_script = bool(re.search(r'[\u0600-\u06FF]', q))
    if _has_urdu_script and word_count >= 5:
        return "legal"  # Urdu sentences describing a situation → legal

    if word_count >= 10:
        return "vague"  # long enough to be a real question, just unclear

    return "non_legal"
# Previously this module had _build_history_context() that injected previous
# turns into the LLM prompt for conversational continuity. That has been
# removed — Groq now sees ONLY the current query and the freshly retrieved
# RAG chunks. Continuity across turns is handled entirely at retrieval time
# via build_retrieval_query() in app.py, which combines recent queries
# before the FAISS search to disambiguate follow-ups. This guarantees the
# legal answer is grounded in chunks that match the conversational topic
# without exposing the LLM to prior responses it might cite from.


def _build_user_message(
    query: str,
    context_chunks: list[dict],
    language: str,
    chat_history: list[dict] | None = None,   # accepted but IGNORED — see note
) -> str:
    """
    Build the user message sent to Groq.

    RAG-DOMINANCE ENFORCEMENT:
      Groq receives ONLY the current user query and freshly retrieved RAG chunks.
      Chat history is NOT injected into the prompt.

    ENCODING SAFETY:
      All chunk text is ensured to be valid UTF-8 strings before insertion.
      Slicing uses character positions (Python str is already Unicode).
    """
    lang_note = _LANG_INSTRUCTION.get(language, _LANG_INSTRUCTION["English"])

    # Encoding-safe helper: ensure a value is a clean Unicode string
    def _safe_str(v: object, max_len: int = 700) -> str:
        if not isinstance(v, str):
            v = str(v)
        # Re-encode through UTF-8 to strip any corrupted bytes
        try:
            v = v.encode("utf-8", errors="replace").decode("utf-8")
        except Exception:
            pass
        return v[:max_len]

    if context_chunks:
        context_lines = []
        for i, chunk in enumerate(context_chunks, 1):
            section_note = f" | {chunk['section']}" if chunk.get("section") else ""
            score_pct    = f"{chunk.get('score', 0):.0%}"
            # Annotate schedule/appendix chunks so the LLM does not cite them
            # as operative sections (they're often mislabeled with a section #).
            schedule_warn = ""
            if chunk.get("is_schedule"):
                schedule_warn = (
                    "\n⚠️ NON-OPERATIVE TEXT: This source is from a SCHEDULE / APPENDIX / FORM, "
                    "NOT an operative section. Do NOT cite a section number from this source."
                )
            header = (
                f"[Source {i}] {_safe_str(chunk['law_name'], 80)}{section_note}\n"
                f"Category: {_safe_str(chunk['category'], 50)} | Relevance: {score_pct}"
                f"{schedule_warn}"
            )
            body = _safe_str(chunk["text"], 700)
            context_lines.append(f"{header}\n\n{body}")

        context_block = "\n\n" + ("═" * 50) + "\n\n".join(context_lines)
        grounding_note = (
            "IMPORTANT: Base your entire LEGAL response on the retrieved sources above. "
            "Only cite sections that appear in these sources."
        )
    else:
        context_block = "[No legal sections retrieved for this query]"
        grounding_note = (
            "No relevant legal sections were retrieved. "
            "Set confidence to 'Low'. Explain in summary that you lack sufficient "
            "legal context for this specific query and the user should consult a lawyer. "
            "Do NOT fabricate laws or sections. Laws array should be empty."
        )

    return (
        f"═══ LANGUAGE INSTRUCTION (MANDATORY) ═══\n"
        f"{lang_note}\n"
        f"═══════════════════════════════════════\n\n"
        f"RETRIEVED LEGAL SOURCES:\n{context_block}\n\n"
        f"{'═' * 50}\n\n"
        f"{grounding_note}\n\n"
        f"USER'S CURRENT QUERY:\n{_safe_str(query, 2000)}\n\n"
        f"Respond with ONLY the JSON object, with all text values in the language specified above."
    )


# ── Client factory + multi-key rotation ───────────────────────────────────────
# GROQ_API_KEYS holds every configured key (primary + optional backups, each
# from a SEPARATE Groq account — keys on the same account share one quota
# pool). When the active key gets a 429 rate-limit response, we rotate to the
# next key and retry transparently, so callers' existing retry/error-handling
# logic only ever sees an error once every configured key is exhausted.
_active_key_idx = 0


@functools.lru_cache(maxsize=None)
def _client_for_key(idx: int) -> Groq:
    return Groq(api_key=GROQ_API_KEYS[idx], timeout=45.0, max_retries=0)


def _get_client() -> Groq:
    if not GROQ_API_KEYS:
        raise RuntimeError(
            "GROQ_API_KEY is not set. "
            "Get a free key at https://console.groq.com and add it to .env"
        )
    return _client_for_key(_active_key_idx)


def _is_rate_limit_error(exc: BaseException) -> bool:
    err = str(exc)
    return "429" in err or "rate_limit" in err.lower() or "rate limit" in err.lower()


def _rotate_key() -> bool:
    """Advance to the next configured Groq key. Returns False once exhausted."""
    global _active_key_idx
    if _active_key_idx + 1 >= len(GROQ_API_KEYS):
        return False
    _active_key_idx += 1
    logger.warning(
        "Groq rate limit hit — rotating to backup API key %d/%d",
        _active_key_idx + 1, len(GROQ_API_KEYS),
    )
    return True


def call_groq_with_rotation(make_call):
    """
    Run make_call(client) against the active Groq API key. On a 429
    rate-limit response, rotates to the next configured key (if any) and
    retries — transparent to callers, whose own retry/error-handling only
    sees an exception once every key has been tried.
    """
    waited = False
    while True:
        client = _get_client()
        try:
            return make_call(client)
        except Exception as e:
            if _is_rate_limit_error(e) and _rotate_key():
                continue
            # A short bounded wait lets normal follow-up requests work on free
            # accounts without changing models or blocking the ASGI event loop.
            if getattr(e, "status_code", None) == 429 and not waited:
                match = re.search(r"try again in\s*([\d.]+)s", str(e), re.I)
                delay = float(match.group(1)) + 1 if match else 10
                if delay <= 35:
                    waited = True
                    time.sleep(delay)
                    continue
            raise


# ── JSON extraction ───────────────────────────────────────────────────────────

def _extract_json(raw: str) -> dict:
    """Strip any markdown fences and parse JSON from model response."""
    cleaned = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE)
    cleaned = cleaned.strip().strip("`").strip()
    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Find JSON object in response
        match = re.search(r'\{[\s\S]+\}', cleaned)
        if match:
            return json.loads(match.group())
        raise


# ── Main analysis ──────────────────────────────────────────────────────────────

def analyze_with_rag(
    query: str,
    context_chunks: list[dict],
    language: str = "English",
    chat_history: list[dict] | None = None,
) -> LegalAnalysis:
    """
    Send query + retrieved context to Groq LLM.

    Args:
        query:          The current user query (sanitized).
        context_chunks: Top-K chunks from RAG retrieval — the ONLY legal source
                        seen by the LLM.
        language:       UI language for the response.
        chat_history:   Accepted for signature compatibility but NOT sent to
                        Groq (Phase 3.1 RAG-dominance rule). Continuity is
                        handled at retrieval time via build_retrieval_query()
                        in app.py — Groq sees only the current query plus
                        the chunks retrieved using the combined query.

    Returns structured LegalAnalysis. Retries once on transient errors.
    """
    # ── Pre-LLM legal intent gate ─────────────────────────────────────────────
    # Classify the query BEFORE spending tokens on retrieval/LLM.
    intent = classify_legal_intent(query)

    if intent == "non_legal":
        # Return a polite non-legal response without calling the LLM or
        # fabricating any laws. This prevents hallucination on greetings/noise.
        if language == "Urdu":
            non_legal_summary = (
                "یہ ٹول صرف پاکستانی قانونی مسائل کے لیے ہے۔ "
                "براہ کرم اپنا قانونی مسئلہ واضح طور پر بیان کریں تاکہ ہم آپ کی مدد کر سکیں۔"
            )
        else:
            non_legal_summary = (
                "This tool is designed to help with Pakistani legal issues. "
                "Please describe your specific legal problem and we can help you understand your rights."
            )
        return LegalAnalysis(
            summary    = non_legal_summary,
            category   = "General / Other",
            laws       = [],
            rights     = [],
            next_steps = [],
            risk_level = "Low",
            risk_reason= "Query does not appear to describe a legal issue.",
            confidence = "Low",
        )

    context_chunks = [chunk for chunk in context_chunks if float(chunk.get("score", 0)) >= 0.40]
    if not context_chunks:
        summary = (
            "اس سوال کے لیے کافی متعلقہ قانونی مواد نہیں ملا۔ مزید تفصیل دیں یا مستند وکیل سے رابطہ کریں۔"
            if language == "Urdu" else
            "I could not find enough relevant law in the available documents for this question. "
            "Please add more details or consult a qualified lawyer."
        )
        risk, reason = stabilize_risk("Low", query, "General / Other")
        return LegalAnalysis(summary=summary, confidence="Low", risk_level=risk, risk_reason=reason)
    try:
        _get_client()
    except RuntimeError as exc:
        return LegalAnalysis(error=str(exc))

    # ── Pre-LLM deterministic risk classification ─────────────────────────────
    _pre_risk = "Medium"
    _q_low = query.lower()
    if any(_matches_risk_term(kw, _q_low) for kw in _HARD_HIGH_KEYWORDS):
        _pre_risk = "High"
    elif any(_matches_risk_term(kw, _q_low) for kw in _SOFT_HIGH_KEYWORDS) and not _is_info_query(_q_low):
        _pre_risk = "High"
    elif _is_info_query(_q_low) and len(query.split()) < 20:
        _pre_risk = "Low"

    # Include the classified intent in the user message so the LLM applies the
    # right query type (TYPE B for vague, TYPE C/D for clear legal queries).
    # NOTE: Urdu queries classified as vague are upgraded to legal (see
    # classify_legal_intent), so "vague" here means English only.
    intent_hint = {
        "legal":  "TYPE C or D",
        "vague":  "TYPE B",
    }.get(intent, "TYPE C")

    user_msg = _build_user_message(query, context_chunks, language, chat_history)
    user_msg += "\nCanonical categories: " + CATEGORY_STRING
    user_msg += (
        "\nReturn law_source_ids as an array of integer Source numbers, one per laws entry in the same order. "
        "Every cited section must occur in that source. category, risk_level, and confidence must retain "
        "their allowed English enum values even when the prose is Urdu."
    )
    user_msg += (
        f"\n\nQUERY CLASSIFICATION HINT: This query appears to be {intent_hint}. "
        f"PRE-ASSESSED RISK (rule-based, use as baseline): {_pre_risk}. "
        f"Only change risk if retrieved sources provide strong evidence of a different severity."
    )

    for attempt in range(2):
        try:
            response = call_groq_with_rotation(lambda c: c.chat.completions.create(
                model=GROQ_LLM_MODEL,
                messages=[
                    {"role": "system", "content": CASE_ANALYSIS},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=0.15,
                **({"reasoning_effort": "low"} if "gpt-oss" in GROQ_LLM_MODEL else {}),
                max_tokens=1800,
                response_format={"type": "json_object"},
            ))
            raw  = response.choices[0].message.content or ""

            # UTF-8 safety: re-encode to strip any corrupted bytes from API
            try:
                raw = raw.encode("utf-8", errors="replace").decode("utf-8")
            except Exception:
                pass

            data = _extract_json(raw)

            # Validate + normalise
            category = data.get("category", "General / Other")
            if category not in LEGAL_CATEGORIES:
                category = "General / Other"

            raw_risk = data.get("risk_level", "Medium")
            if raw_risk not in ("Low", "Medium", "High", "Critical"):
                raw_risk = "Medium"

            conf = data.get("confidence", "Medium")
            if conf not in ("Low", "Medium", "High"):
                conf = "Medium"

            # ── Language output validation ─────────────────────────────────────
            # Check that the LLM actually responded in the requested language.
            # Urdu mismatch on attempt 0 → silent retry with reinforced prompt.
            summary_text = str(data.get("summary", ""))
            _lang_mismatch_note = ""

            import re as _re
            _check_text = "\n".join([
                summary_text,
                *[str(x).split(":", 1)[-1] for x in data.get("laws", [])],
                *[str(x) for x in data.get("rights", [])],
                *[str(x) for x in data.get("next_steps", [])],
            ])
            _has_urdu   = bool(_re.search(r'[\u0600-\u06FF]', _check_text))
            _has_latin  = bool(_re.search(r'[a-zA-Z]{3,}', _check_text))
            _has_cyril  = bool(_re.search(r'[\u0400-\u04FF]', _check_text))

            if _has_cyril:
                _lang_mismatch_note = " [WARNING: response contained non-standard characters and may be unreliable]"
                conf = "Low"
            elif language == "Urdu" and not _has_urdu:
                if attempt == 0:
                    # Silent retry with reinforced Urdu-script instruction
                    _reinforce = (
                        "\n\nCRITICAL: تمام JSON ویلیوز لازمی اردو رسم الخط میں ہونی چاہئیں۔"
                        " مثال سمری: 'آپ کا حق ہے کہ آجر وقت پر تنخواہ ادا کرے۔'"
                        "\nEVERY value in the JSON MUST be in اردو script — absolutely no English."
                    )
                    user_msg = user_msg + _reinforce
                    time.sleep(0.5)
                    continue  # retry with reinforced prompt
                # Still not Urdu on second attempt — flag and proceed
                _lang_mismatch_note = " [تنبیہ: جواب اردو رسم الخط میں نہیں ہے]"
                conf = "Low" if conf == "High" else conf
            elif language == "Urdu" and _has_urdu and _has_latin:
                # Code-switching: response is mostly Urdu but has English words/phrases
                # mixed in mid-sentence (e.g. "Code of Criminal Procedure", "In practice").
                if attempt == 0:
                    _reinforce = (
                        "\n\nCRITICAL: آپ کے جواب میں انگریزی الفاظ یا فقرے اردو جملوں کے بیچ میں "
                        "شامل تھے — یہ ناقابلِ قبول ہے۔ ہر لفظ، بشمول جوڑنے والے الفاظ اور قانون کے "
                        "ناموں کو، اردو رسم الخط میں دوبارہ لکھیں — کوئی بھی لفظ لاطینی حروف میں نہ ہو "
                        "(مثال: 'Section' کی بجائے 'دفعہ'، 'In practice' کی بجائے 'عملی طور پر'، "
                        "'Code of Criminal Procedure' کی بجائے 'کوڈ آف کریمنل پروسیجر')۔ "
                        "صرف دفعہ نمبرات اور سن کے اعداد لاطینی ہندسوں میں رہیں گے۔"
                        "\nRE-WRITE your entire response with ZERO English words — only digits "
                        "(section numbers, years) may stay in Latin numerals."
                    )
                    user_msg = user_msg + _reinforce
                    time.sleep(0.5)
                    continue  # retry with reinforced prompt
                # Still code-switching on second attempt — flag and proceed
                _lang_mismatch_note = " [تنبیہ: جواب میں انگریزی الفاظ شامل ہیں]"
                conf = "Low" if conf == "High" else conf

            if _lang_mismatch_note:
                summary_text = summary_text + _lang_mismatch_note

            laws, unsupported = validate_citations(data.get("laws", []), data.get("law_source_ids", []), context_chunks, language)
            if unsupported or not laws:
                conf = "Low"

            # ── Risk stabilization pass ───────────────────────────────────────
            stable_risk, override_reason = stabilize_risk(raw_risk, query, category)
            risk_reason = str(data.get("risk_reason", ""))
            if override_reason:
                # Append stabilization note to the LLM's risk reason
                risk_reason = override_reason

            return LegalAnalysis(
                summary     = summary_text,
                category    = category,
                laws        = laws,
                rights      = text_list(data.get("rights", [])),
                next_steps  = text_list(data.get("next_steps", [])),
                risk_level  = stable_risk,
                risk_reason = risk_reason,
                confidence  = conf,
                sources     = context_chunks,
            )

        except RuntimeError:
            raise
        except (json.JSONDecodeError, KeyError) as e:
            if attempt == 0:
                time.sleep(1)
                continue
            return LegalAnalysis(
                error=f"Could not parse AI response: {e}. "
                      f"Raw: {locals().get('raw','')[:200]}"
            )
        except Exception as e:
            err = str(e)
            if attempt == 0 and "rate_limit" not in err.lower():
                time.sleep(2)
                continue
            return LegalAnalysis(error=f"Groq API error: {err}")

    return LegalAnalysis(error="Analysis failed after retries.")


# ── Whisper transcription (English only) ──────────────────────────────────────

# Groq Whisper is used ONLY for English.
# Urdu uses ElevenLabs Speech-to-Text (Scribe model) — see _transcribe_urdu_elevenlabs().
_WHISPER_LANG_MAP = {
    "English": "en",
}

_WHISPER_PROMPT = {
    "English": "Legal issue in Pakistan.",
}

# Groq Whisper max file size is 25 MB
_MAX_AUDIO_BYTES = 25 * 1024 * 1024


def _transcribe_urdu_elevenlabs(audio_bytes: bytes) -> tuple[str, Optional[str]]:
    """
    Transcribe Urdu audio using ElevenLabs Speech-to-Text (Scribe model).

    Returns (text, error). On success: (text, None). On failure: ("", error_str).

    ElevenLabs STT endpoint:
        POST https://api.elevenlabs.io/v1/speech-to-text
        Header: xi-api-key: <key>
        Body:   multipart/form-data with audio file + model_id
    """
    try:
        from app.utils.config import ELEVENLABS_API_KEY
    except ImportError:
        ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")

    if not ELEVENLABS_API_KEY:
        return ("", "ElevenLabs API key not set. Add ELEVENLABS_API_KEY to .env.")

    import requests as _req

    url     = "https://api.elevenlabs.io/v1/speech-to-text"
    headers = {"xi-api-key": ELEVENLABS_API_KEY}

    # Write audio bytes to a temp file for multipart upload
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as audio_file:
            files   = {"file": ("recording.wav", audio_file, "audio/wav")}
            payload = {"model_id": "scribe_v1"}       # ElevenLabs Scribe STT model
            resp = _req.post(
                url, headers=headers, files=files, data=payload, timeout=60
            )

        if resp.status_code == 401:
            return ("", "Invalid ElevenLabs API key. Check ELEVENLABS_API_KEY in .env.")
        if resp.status_code == 429:
            return ("", "ElevenLabs rate limit reached. Please wait and try again.")
        if resp.status_code == 413:
            return ("", "Audio file too large for ElevenLabs. Please record a shorter clip.")
        if not resp.ok:
            return ("", f"ElevenLabs STT error {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        # ElevenLabs Scribe returns {"text": "...", "words": [...], ...}
        text = str(data.get("text", "")).strip()
        return (text, None)

    except _req.exceptions.ConnectionError:
        return ("", "Network error: cannot reach ElevenLabs. Check internet connection.")
    except _req.exceptions.Timeout:
        return ("", "ElevenLabs request timed out. Please try again.")
    except Exception as exc:
        return ("", f"ElevenLabs STT failed: {exc}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def transcribe_audio(
    audio_bytes: bytes,
    language: str = "English",
) -> tuple[str, Optional[str]]:
    """
    Speech-to-Text using Groq Whisper for BOTH English and Urdu.

    Returns:
        (text, None) on success
        ("", error_message) on failure
    """

    if not audio_bytes:
        return ("", "No audio data to transcribe.")

    if len(audio_bytes) > _MAX_AUDIO_BYTES:
        return (
            "",
            f"Audio file too large ({len(audio_bytes)//1024//1024} MB). "
            "Maximum is 25 MB. Please record a shorter clip."
        )

    try:
        _get_client()  # readiness check — raises RuntimeError if no key configured
    except RuntimeError as e:
        return ("", str(e))

    # ── Language selection ───────────────────────────────────────
    lang = "ur" if language == "Urdu" else "en"

    # Better prompting for Urdu
    prompt = (
        "پاکستانی قانونی مسئلہ"
        if lang == "ur"
        else "Legal issue in Pakistan."
    )

    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as f:

            logger.info(f"Whisper transcription language: {lang}")

            transcription = call_groq_with_rotation(lambda c: c.audio.transcriptions.create(
                model=GROQ_WHISPER_MODEL,
                file=("recording.wav", f),
                language=lang,
                prompt=prompt,
                response_format="text",
                temperature=0.0,
            ))

        text = str(transcription).strip()

        # Basic validation only
        if not text:
            return (
                "",
                "No speech detected. Please speak clearly and try again."
            )

        logger.info("Transcription completed (%d characters)", len(text))

        return (text, None)

    except Exception as exc:

        err = str(exc)

        logger.exception("Whisper transcription failed")

        if "401" in err or "api_key" in err.lower():
            return (
                "",
                "Invalid or missing Groq API key."
            )

        if "429" in err or "rate_limit" in err.lower():
            return (
                "",
                "Groq rate limit reached. Please try again shortly."
            )

        if "413" in err or "too large" in err.lower():
            return (
                "",
                "Audio file too large."
            )

        if "400" in err or "invalid" in err.lower():
            return (
                "",
                "Audio format rejected. Please record again."
            )

        return (
            "",
            f"Transcription failed: {err}"
        )

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# DOCUMENT ANALYSIS — RAG-grounded analysis of uploaded legal documents
# ═══════════════════════════════════════════════════════════════════════════════

_DOC_RETRIEVAL_CHARS = 800    # chars of doc used as FAISS retrieval query
_DOC_ANALYSIS_CHARS  = 6000  # each segment is reviewed; coverage is returned to the client

_DISCLAIMER_EN = (
    "This analysis is generated by an AI assistant and is for informational purposes only. "
    "It does not constitute legal advice. Always consult a qualified lawyer for advice "
    "specific to your situation."
)
_DISCLAIMER_UR = (
    "یہ تجزیہ صرف معلوماتی مقاصد کے لیے ہے اور قانونی مشورہ نہیں ہے۔ "
    "اپنی مخصوص صورتحال کے لیے کسی مستند وکیل سے رہنمائی حاصل کریں۔"
)

# ── Document-analysis relevance filtering ─────────────────────────────────────
# Uploaded document text is dense legal prose — it creates many weak cross-domain
# FAISS associations that would pollute cited_laws with tangential statutes.
# These thresholds are deliberately higher than the general retrieve() thresholds
# (PRIMARY=0.40, FALLBACK=0.28, MAX_PER_LAW=3) in rag_engine.py.

# Hard floor: any chunk below this boosted_score is dropped, regardless of type.
# Raised from the general PRIMARY_THRESHOLD (0.40) by +0.05.
_DOC_CHUNK_MIN_SCORE = 0.45

# Off-category gate: for known document types, chunks from outside the expected
# legal domain must clear this higher threshold to survive.
_DOC_OFF_CATEGORY_THRESHOLD = 0.55

# Per-law diversity cap for document analysis (vs. MAX_PER_LAW=3 in retrieve()).
# Prevents one statute from dominating the cited_laws section.
_DOC_MAX_PER_LAW = 2

# Category allowlists per classified document type.
# Chunks whose category is NOT in this set are subject to _DOC_OFF_CATEGORY_THRESHOLD.
# "Unknown" document type has no entry → only the score floor is applied.
_DOC_TYPE_CATEGORIES: dict[str, frozenset] = {
    "Legal Notice":        frozenset({
        "Property Law", "Contract Law", "Labour Law",
        "Family Law", "Civil Law", "Criminal Law",
    }),
        "FIR":                 frozenset({"Criminal Law", "Civil Law / Procedure"}),
    "Court Order":         frozenset({
        "Criminal Law", "Civil Law", "Civil Law / Procedure",
        "Family Law", "Property Law", "Labour Law",
    }),
    "Rent Agreement":      frozenset({"Property Law", "Contract Law"}),
    "Employment Contract": frozenset({"Labour Law", "Contract Law"}),
}


def _filter_chunks_for_document(
    chunks: list[dict],
    document_type: str,
) -> list[dict]:
    """
    Post-retrieval relevance filter applied only in the document analysis pipeline.

    Applies three additional gates beyond rag_engine.retrieve():
      1. Hard score floor — drops chunks that passed the standard 0.40 threshold
         but are too weak to ground a document citation (floor = 0.45).
      2. Off-category gate — for known document types, chunks from unrelated law
         domains must score >= 0.55 to be included.  Prevents e.g. Criminal Law
         chunks from appearing in a Rent Agreement analysis unless they are very
         strongly relevant.
      3. Per-law diversity cap — limits to 2 chunks per law (vs. 3 in retrieve())
         to stop a single statute from dominating cited_laws.

    rag_engine.retrieve() is not modified — all extra filtering is local here.
    """
    allowed_cats = _DOC_TYPE_CATEGORIES.get(document_type)  # None → score floor only

    out: list[dict] = []
    per_law: dict[str, int] = {}

    for chunk in chunks:
        # retrieve() sets boosted_score; fall back to raw score if absent.
        score = chunk.get("boosted_score", chunk.get("score", 0.0))
        cat   = chunk.get("category", "")
        law   = chunk.get("law_name", "")

        # Gate 1: absolute score floor
        if score < _DOC_CHUNK_MIN_SCORE:
            logger.debug(
                "doc-filter(floor): dropped '%s' score=%.3f", law[:50], score,
            )
            continue

        # Gate 2: off-category strict threshold
        if allowed_cats is not None and cat not in allowed_cats:
            if score < _DOC_OFF_CATEGORY_THRESHOLD:
                logger.debug(
                    "doc-filter(off-cat): dropped '%s' cat='%s' score=%.3f",
                    law[:50], cat, score,
                )
                continue

        # Gate 3: per-law diversity cap
        if per_law.get(law, 0) >= _DOC_MAX_PER_LAW:
            continue

        per_law[law] = per_law.get(law, 0) + 1
        out.append(chunk)

    logger.info(
        "doc-filter: %d → %d chunks (type='%s' floor=%.2f off-cat=%.2f laws=%d)",
        len(chunks), len(out), document_type,
        _DOC_CHUNK_MIN_SCORE, _DOC_OFF_CATEGORY_THRESHOLD, len(per_law),
    )
    return out


_DOC_ANALYSIS_SYSTEM_PROMPT = DOCUMENT_ANALYSIS


def _build_document_analysis_message(
    document_text: str,
    document_type: str,
    detected_language: str,
    context_chunks: list[dict],
    language: str,
) -> str:
    """Build the Groq user message for document analysis."""

    def _safe_str(v: object, max_len: int = 700) -> str:
        if not isinstance(v, str):
            v = str(v)
        try:
            v = v.encode("utf-8", errors="replace").decode("utf-8")
        except Exception:
            pass
        return v[:max_len]

    # RAG sources block — identical formatting to _build_user_message
    if context_chunks:
        context_lines = []
        for i, chunk in enumerate(context_chunks, 1):
            section_note  = f" | {chunk['section']}" if chunk.get("section") else ""
            score_pct     = f"{chunk.get('score', 0):.0%}"
            schedule_warn = ""
            if chunk.get("is_schedule"):
                schedule_warn = (
                    "\n⚠️ NON-OPERATIVE TEXT: This source is from a SCHEDULE/APPENDIX/FORM. "
                    "Do NOT cite a section number from this source."
                )
            header = (
                f"[Source {i}] {_safe_str(chunk['law_name'], 80)}{section_note}\n"
                f"Category: {_safe_str(chunk['category'], 50)} | Relevance: {score_pct}"
                f"{schedule_warn}"
            )
            context_lines.append(f"{header}\n\n{_safe_str(chunk['text'], 700)}")
        context_block  = "\n\n" + ("═" * 50) + "\n\n".join(context_lines)
        grounding_note = (
            "IMPORTANT: For cited_laws, only cite sections that appear in the retrieved sources above."
        )
    else:
        context_block  = "[No relevant legal sections retrieved for this document type]"
        grounding_note = (
            "No relevant legal sections retrieved. cited_laws must be []. "
            "Set confidence to 'Low'. Rely on the document text alone for summary and guidance."
        )

    # Truncate document text
    doc_snippet = _safe_str(document_text, _DOC_ANALYSIS_CHARS)
    if len(document_text) > _DOC_ANALYSIS_CHARS:
        doc_snippet += (
            f"\n[… document truncated — "
            f"{len(document_text) - _DOC_ANALYSIS_CHARS:,} additional chars omitted …]"
        )

    if language == "Urdu":
        lang_note = (
            "Write summary, key_legal_points, deadlines, procedural_guidance, and risk_indicators "
            "ENTIRELY in natural, everyday Urdu — every adjective, connector, and concept included. "
            "Do NOT switch to English mid-sentence for ANY word, even common ones — translate it "
            "(write 'پرامن' not 'peaceful', 'باعزت' not 'respectful', 'ماحول' not 'environment'). "
            "If no single Urdu word fits, use the closest natural Urdu phrase; never fall back to "
            "the English term. Numbers, dates, and years should use Western digits inside the Urdu "
            "sentence exactly as Pakistani Urdu newspapers write them (e.g. 'نومبر 2024' is correct "
            "and expected — do not invent unfamiliar numeral forms). "
            "cited_laws entries use English law names (official titles have no Urdu equivalent) "
            "followed by an Urdu explanation after the colon. "
            "urdu_explanation must be in plain Urdu (always required). "
            "PARITY — MANDATORY: cover the SAME substantive legal points, deadlines, risks, and "
            "steps you would identify if writing in English. This is the same analysis expressed "
            "naturally in Urdu — not a shorter, simplified, or differently-scoped version."
        )
    else:
        lang_note = (
            "Write summary, key_legal_points, deadlines, procedural_guidance, risk_indicators, "
            "and cited_laws in clear English. "
            "urdu_explanation must be in Urdu script (always required — do not skip it), written "
            "in natural everyday Urdu with NO English loanwords for common concepts — translate "
            "every word (write 'پرامن' not 'peaceful'). Numbers/dates may use Western digits inside "
            "the Urdu sentence as is conventional in Pakistani Urdu (e.g. 'نومبر 2024'). "
            "PARITY — MANDATORY: urdu_explanation must cover the SAME substantive points as the "
            "English summary/key_legal_points — the same analysis in plain Urdu, not a different one."
        )

    return (
        f"LANGUAGE INSTRUCTION: {lang_note}\n\n"
        f"DOCUMENT TYPE (classified): {document_type}\n"
        f"DOCUMENT LANGUAGE (detected): {detected_language}\n\n"
        f"RETRIEVED LEGAL SOURCES (use ONLY these for cited_laws):\n{context_block}\n\n"
        f"{'═' * 50}\n\n"
        f"{grounding_note}\n\n"
        f"DOCUMENT TEXT TO ANALYSE:\n{'─' * 40}\n{doc_snippet}\n{'─' * 40}\n\n"
        f"Respond with ONLY the JSON object."
    )


def _analyze_document_chunk(
    document_text: str,
    document_type: str,
    detected_language: str,
    language: str = "English",
) -> DocumentAnalysis:
    """
    Analyze an uploaded legal document using the existing RAG + Groq pipeline.

    Reuses the same FAISS retrieval, Groq client, and anti-hallucination grounding
    as analyze_with_rag(). Only the prompt structure and output schema differ.

    Args:
        document_text:     Extracted plain text from the uploaded document.
        document_type:     Classified type (e.g. "Legal Notice", "FIR", "Unknown").
        detected_language: "English" | "Urdu" | "Mixed" | "Unknown".
        language:          UI language for the main response fields.

    Returns:
        DocumentAnalysis. On any failure, .error is set and other fields may be empty.
    """
    # Local imports avoid circular dependency — rag_engine does not import groq_client.
    from app.utils.rag_engine import retrieve, preprocess_query, index_ready
    import unicodedata as _ud

    disclaimer = _DISCLAIMER_UR if language == "Urdu" else _DISCLAIMER_EN

    # ── Input sanitization ────────────────────────────────────────────────────
    # Strip null bytes, normalize Unicode, and cap length before any processing.
    document_text = document_text.replace('\x00', '')
    try:
        document_text = _ud.normalize('NFC', document_text)
    except Exception:
        pass
    if len(document_text) > 50_000:
        logger.warning(
            "analyze_document_with_rag: document_text truncated from %d to 50,000 chars",
            len(document_text),
        )
        document_text = document_text[:50_000]

    if not document_text or not document_text.strip():
        return DocumentAnalysis(
            error="No text could be extracted from the document — cannot analyse.",
            disclaimer=disclaimer,
        )

    try:
        _get_client()  # readiness check — raises RuntimeError if no key configured
    except RuntimeError as e:
        return DocumentAnalysis(error=str(e), disclaimer=disclaimer)

    # ── Retrieval — reuse existing retrieve() exactly as /api/analyze does ─────
    context_chunks: list[dict] = []
    if index_ready():
        retrieval_query = preprocess_query(
            f"{document_type} {document_text[:_DOC_RETRIEVAL_CHARS]}"
        )
        context_chunks = retrieve(retrieval_query)
        context_chunks = _filter_chunks_for_document(context_chunks, document_type)
        logger.info(
            "Document analysis: %d chunks after relevance filter (type=%s lang=%s)",
            len(context_chunks), document_type, detected_language,
        )
    else:
        logger.warning(
            "FAISS index not ready — document analysis proceeds without RAG context."
        )

    user_msg = _build_document_analysis_message(
        document_text, document_type, detected_language, context_chunks, language
    )

    user_msg += "\nReturn cited_source_ids: one integer Source number for each cited_laws entry in the same order."

    for attempt in range(2):
        try:
            response = call_groq_with_rotation(lambda c: c.chat.completions.create(
                model=GROQ_LLM_MODEL,
                messages=[
                    {"role": "system", "content": DOCUMENT_ANALYSIS},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=0.15,
                **({"reasoning_effort": "low"} if "gpt-oss" in GROQ_LLM_MODEL else {}),
                max_tokens=1800,
                response_format={"type": "json_object"},
            ))
            raw = response.choices[0].message.content or ""
            try:
                raw = raw.encode("utf-8", errors="replace").decode("utf-8")
            except Exception:
                pass

            data = _extract_json(raw)

            conf = data.get("confidence", "Medium")
            if conf not in ("Low", "Medium", "High"):
                conf = "Medium"

            urdu_expl = str(data.get("urdu_explanation", ""))

            # Validate urdu_explanation is actually in Urdu script
            if urdu_expl and not re.search(r'[؀-ۿ]', urdu_expl):
                if attempt == 0:
                    user_msg += (
                        "\n\nCRITICAL: The urdu_explanation field MUST be in اردو script only. "
                        "Do not use any English words inside it. Example: "
                        "'یہ ایک قانونی نوٹس ہے جس میں آپ سے رقم مانگی گئی ہے۔'"
                    )
                    time.sleep(0.5)
                    continue

            cited_laws, unsupported = validate_citations(
                data.get("cited_laws", []), data.get("cited_source_ids", []), context_chunks, language,
            )
            if unsupported or not context_chunks:
                conf = "Low"

            return DocumentAnalysis(
                summary             = str(data.get("summary", "")),
                key_legal_points    = text_list(data.get("key_legal_points", [])),
                deadlines           = text_list(data.get("deadlines", [])),
                procedural_guidance = text_list(data.get("procedural_guidance", [])),
                risk_indicators     = text_list(data.get("risk_indicators", [])),
                cited_laws          = cited_laws,
                urdu_explanation    = urdu_expl,
                confidence          = conf,
                disclaimer          = disclaimer,
            )

        except RuntimeError:
            raise
        except (json.JSONDecodeError, KeyError) as e:
            if attempt == 0:
                time.sleep(1)
                continue
            return DocumentAnalysis(
                error=f"Could not parse AI response: {e}",
                disclaimer=disclaimer,
            )
        except Exception as e:
            err = str(e)
            if attempt == 0 and "rate_limit" not in err.lower():
                time.sleep(2)
                continue
            return DocumentAnalysis(error=f"Groq API error: {err}", disclaimer=disclaimer)

    return DocumentAnalysis(error="Analysis failed after retries.", disclaimer=disclaimer)


def analyze_document_with_rag(document_text: str, document_type: str,
                              detected_language: str, language: str = "English") -> DocumentAnalysis:
    """Review consecutive segments, merging findings without silently dropping the ending."""
    total = len(document_text)
    disclaimer = _DISCLAIMER_UR if language == "Urdu" else _DISCLAIMER_EN
    if total > 50000:
        return DocumentAnalysis(error="Documents are limited to 50,000 extracted characters. Split this document into smaller files.",
                                disclaimer=disclaimer, total_characters=total, truncated=True)
    segments = [document_text[index:index + _DOC_ANALYSIS_CHARS]
                for index in range(0, total, _DOC_ANALYSIS_CHARS)] or [document_text]
    completed = []
    analyzed = 0
    deadline = time.monotonic() + 100
    failure = None
    for segment in segments:
        if completed and time.monotonic() > deadline - 45:
            break
        result = _analyze_document_chunk(segment, document_type, detected_language, language)
        if result.error:
            failure = result.error
            break
        completed.append(result)
        analyzed += len(segment)
    if not completed:
        return DocumentAnalysis(error=failure or "Document analysis could not complete. Please retry.",
                                disclaimer=disclaimer, total_characters=total, truncated=True)
    def merged(field):
        return list(dict.fromkeys(item for result in completed for item in getattr(result, field)))
    truncated = analyzed < total
    confidence = min((result.confidence for result in completed),
                     key=lambda value: {"Low": 0, "Medium": 1, "High": 2}.get(value, 0))
    return DocumentAnalysis(
        summary="\n\n".join(result.summary for result in completed if result.summary),
        key_legal_points=merged("key_legal_points"), deadlines=merged("deadlines"),
        procedural_guidance=merged("procedural_guidance"), risk_indicators=merged("risk_indicators"),
        cited_laws=merged("cited_laws"),
        urdu_explanation="\n\n".join(result.urdu_explanation for result in completed if result.urdu_explanation),
        confidence="Low" if truncated else confidence, disclaimer=disclaimer,
        analyzed_characters=analyzed, total_characters=total,
        segments_analyzed=len(completed), truncated=truncated,
    )
