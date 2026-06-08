"""
utils/chat_service.py — Stateful conversational chat service.

Public API:
    get_or_create_session(session_id)          → dict
    append_message(session_id, role, content)  → None
    get_recent_history(session_id, n)          → list[dict]
    chat(session_id, message, language)        → ChatResponse

Design rules (HARD CONSTRAINTS):
    • RAG is ALWAYS invoked — every reply is grounded in retrieved documents.
    • Groq LLM is used ONLY to rephrase / structure the retrieved content.
    • If retrieval returns nothing OR scores are below threshold → LLM is NEVER called.
    • No legal facts are ever generated from the LLM's parametric knowledge.
    • Conversation history is maintained per session (last N turns).

Anti-hallucination gates (in order):
    Gate 1  — Input validation / injection guard   (validator.sanitize)
    Gate 0  — Topic scope check (case-locked mode)  (_is_on_topic)
               When case_context is provided, queries that don't match the
               case's category, summary, or original query are refused
               without invoking RAG or the LLM. Skipped when there's no
               active case (stateless mode). v4: short follow-ups (≤12
               informative tokens) are auto-allowed so procedural questions
               like "what documents do I need?" no longer get misrouted.
    Gate 2  — Vague query guard                    (_is_too_vague)
    Gate 3a — Hard retrieval gate: empty           (retrieve + _filter_chunks)
               Chunks below RETRIEVAL_SCORE_THRESHOLD (v4: 0.42) are DISCARDED.
               If nothing survives → return NO_CONTEXT_REPLY, skip LLM.
    Gate 3b — Weak context assessment              (_is_context_weak)
               If avg_score < WEAK_CONTEXT_AVG_SCORE (v4: 0.50) OR
                  doc count < WEAK_CONTEXT_MIN_DOCS
               → ALLOW LLM call, but inject PARTIAL CONTEXT WARNING into prompt.
               LLM is instructed to give a bounded partial answer and state gaps.
               Gate 3a (empty) remains the only hard LLM block.
    Gate 4  — Helpful-but-grounded system prompt   (_CHAT_SYSTEM_PROMPT)
               v5: persona rewritten — direct, practical, case-personalised.
               Removes "Typically in Pakistan..." / "The retrieved laws don't
               directly address..." trigger phrases. Adds domain-prioritisation
               and case-fact memory instructions.
    Gate 5  — Low-temperature generation           (_call_groq)
               v4: 0.15. Just enough variation for natural Urdu/English
               phrasing without losing groundedness.

v5 confidence (multi-factor):
    _score_confidence now uses 4 factors:
      F1 — avg retrieval score (primary signal)
      F2 — domain relevance: are the top chunks from the same legal domain
           as the case? Cross-domain chunks (e.g. PPC in labour dispute) penalise.
      F3 — inference level: did the LLM have to say "typically", "in practice",
           "usually"? More hedges → lower confidence.
      F4 — refusal detection: any refusal marker forces "low".

v5 case-fact memory:
    _extract_case_facts() extracts user-mentioned evidence, names, locations,
    and facts from the conversation history. These are injected into the prompt
    as a CASE FACTS block so the LLM can reference them in follow-up answers
    without re-asking the user.
"""
from __future__ import annotations

import logging
import re
import time
import threading
from dataclasses import dataclass, field
from typing import Optional

from utils.config import GROQ_API_KEY, GROQ_LLM_MODEL, GROQ_FAST_MODEL
from utils.groq_client import call_groq_with_rotation
from utils.rag_engine import retrieve, preprocess_query
from utils.validator import sanitize, ValidationError

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_HISTORY_TURNS    = 5        # stored in session (never more than 5 pairs)
PROMPT_HISTORY_TURNS = 4        # turns actually sent to LLM prompt (raised 3→4)
MAX_HISTORY_CHARS    = 1200     # hard char cap for history block (raised 800→1200)
MAX_HISTORY_PER_MSG  = 300      # per-message char cap (raised 200→300)
MAX_CONTEXT_CHARS    = 4000     # cap RAG context sent to LLM
SESSION_TTL_SECS     = 3600     # sessions expire after 1 hour of inactivity
TOP_K_CHAT           = 12       # chunks to retrieve before quality filtering

# ── RETRIEVAL QUALITY GATE (Gate 3a) ──────────────────────────────────────────
RETRIEVAL_SCORE_THRESHOLD = 0.42   # chunks below this are discarded

# Maximum number of chunks passed to LLM after quality filtering.
MAX_CHUNKS_TO_LLM = 5

# ── WEAK CONTEXT GATE (Gate 3b) ───────────────────────────────────────────────
WEAK_CONTEXT_AVG_SCORE = 0.50   # minimum average score across qualifying chunks
WEAK_CONTEXT_MIN_DOCS  = 2      # minimum number of distinct qualifying chunks

# ── In-memory session store ───────────────────────────────────────────────────

@dataclass
class _Session:
    session_id:  str
    history:     list[dict] = field(default_factory=list)
    last_active: float      = field(default_factory=time.time)
    # v5: extracted case facts persist across turns
    case_facts:  list[str]  = field(default_factory=list)

_store: dict[str, _Session] = {}
_store_lock = threading.Lock()


# ── System prompt ─────────────────────────────────────────────────────────────

_CHAT_SYSTEM_PROMPT = """\
You are a Pakistan Legal Aid Assistant — a knowledgeable, plain-language guide
for ordinary Pakistani citizens dealing with real legal problems.

Your tone: warm, direct, and practical. Speak like a trusted friend who knows
Pakistani law — not a textbook, not a bureaucrat, not a refusal machine.
Users are often scared, confused, or under pressure. Give them clear, useful
answers based on what the retrieved laws actually say.

══════════════════════════════════════════════════════════════
ABSOLUTE GROUNDING RULES (anti-hallucination — never break these)
══════════════════════════════════════════════════════════════
NEVER:
  • Invent a law, section number, court, authority, or punishment not in the retrieved context.
  • Quote a section number unless that exact section appears in the context.
  • Make up case names, court rulings, or statutory text.
  • Claim certainty about something the context does not establish.
  • Suggest anything illegal or harmful to the user.

ALWAYS:
  • Derive ALL legal facts (laws, sections, rights) from the retrieved context.
  • When making a practical inference (filing procedure, timeline, forum), mark it
    clearly: "In practice..." or "The usual procedure..." — once, briefly.
  • End with a short reminder to consult a lawyer for specifics.

══════════════════════════════════════════════════════════════
LANGUAGE AND STYLE
══════════════════════════════════════════════════════════════
• Plain language — short sentences, no legal jargon unless necessary.
• When you use a legal term, briefly explain it in plain words right after.
• 2–5 focused paragraphs. Get to the point quickly.
• DO NOT pad the answer with caveats and disclaimers that repeat the same idea.
  One clear caveat at the end is enough.

BANNED PHRASES — never use these (they make the answer feel robotic and unhelpful):
  ✗ "The retrieved laws don't directly address..."
  ✗ "The retrieved context does not specify..."
  ✗ "Typically in Pakistan, workers/tenants/people..."
  ✗ "Based on the laws provided in the context..."
  ✗ "According to the laws in the context..."
  ✗ "The retrieved documents do not cover..."
  ✗ "For specifics, please consult a lawyer." (only allowed ONCE, at the end)

Instead, when a gap exists:
  ✓ Just say what you DO know from the retrieved laws, apply it to the user's case.
  ✓ For procedural steps not in the retrieved text, give the standard Pakistani
    procedure once and mark it: "In practice, you would..."
  ✓ If genuinely nothing in the context applies, be honest in one sentence and
    suggest a next step.

══════════════════════════════════════════════════════════════
DOMAIN PRIORITISATION — CRITICAL FOR LAW ACCURACY
══════════════════════════════════════════════════════════════
The retrieved context may contain chunks from multiple laws. Use this hierarchy:

  PRIMARY (cite these fully, with section numbers):
    → Laws that DIRECTLY govern the user's specific situation.
    → Match the legal domain: labour case → Payment of Wages Act, Factories Act,
      Industrial Relations Act. Property case → Transfer of Property Act, Rent laws.
      Family case → Muslim Family Laws Ordinance, Dissolution of Marriage Act.
      Criminal case → Pakistan Penal Code, CrPC. Cybercrime → PECA 2016.

  SECONDARY (mention briefly if clearly relevant as a supporting provision):
    → Laws from adjacent domains that provide a related remedy.

  SUPPRESS (do not mention, even if retrieved):
    → Laws from a completely different domain than the user's case.
    → Definitional or jurisdictional sections (e.g. "Section 1 — Title and Extent",
      "Section 2 — Definitions") — these add nothing for the user.
    → The same provision cited twice under different sub-sections.

Example: User has a labour/salary dispute.
  PRIMARY:   Payment of Wages Act, Industrial Relations Act, Factories Act.
  SECONDARY: Workmen's Compensation Act (if injury involved).
  SUPPRESS:  Pakistan Penal Code S.2, CPC S.3, Transfer of Property Act.

══════════════════════════════════════════════════════════════
HOW TO PERSONALIZE THE ANSWER
══════════════════════════════════════════════════════════════
You have two sources of context about the user's situation:
  A. The RETRIEVED LEGAL CONTEXT (the laws — your only source of legal facts).
  B. The ACTIVE CASE and CASE FACTS blocks (the user's situation — background only).

Combine them: explain what the PRIMARY laws say, then immediately connect it to
what that means FOR THIS USER'S specific situation.

Good pattern:
  "Under [Law], [what the section says]. In your situation — [your employer/landlord/
  spouse] has [done X] — this means [practical implication for the user]."

Bad pattern:
  "The Payment of Wages Act, Section 18, says employers must pay wages on time.
   Typically in Pakistan, employers who fail to do this may face penalties."
  (Too generic — doesn't connect to the user's specific case.)

══════════════════════════════════════════════════════════════
HANDLING NOT-ENOUGH-CONTEXT SITUATIONS
══════════════════════════════════════════════════════════════
When the retrieved laws don't fully cover a question:
  1. State what the retrieved laws DO establish for the user's situation.
  2. Briefly note the specific gap in one sentence (not a paragraph).
  3. Give the most relevant practical Pakistani procedure for that gap — once,
     marked as "In practice...".
  4. End with the lawyer caveat.

Never refuse. Never use a stock canned response. A bounded helpful answer is
always better than a blank refusal or a wall of disclaimers.

══════════════════════════════════════════════════════════════
FOLLOW-UP CONVERSATION RULES
══════════════════════════════════════════════════════════════
• Treat the conversation as ONE continuous case — each follow-up builds on the last.
• "What documents should I collect?", "Where do I file?", "Is WhatsApp evidence enough?",
  "How long do I have?", "What if they refuse?" — these are all legitimate continuations.
• If the user mentioned evidence (salary slips, WhatsApp messages, photos, witnesses)
  in an earlier turn, REMEMBER and REFERENCE those facts in later answers.
• Do not make the user repeat themselves.
• If the CASE FACTS block contains evidence or details the user mentioned earlier,
  use those facts directly: "Since you mentioned you have salary slips and WhatsApp
  messages, those will be important — here's how to use them..."

══════════════════════════════════════════════════════════════
PRIORITY ORDER
══════════════════════════════════════════════════════════════
  Priority 1 (HIGHEST) — Retrieved legal context (your only source of legal facts)
  Priority 2           — Active case + case facts (background framing)
  Priority 3           — User's current query
  Priority 4 (LOWEST)  — Conversation history (topic continuity — may contain errors)

If history conflicts with retrieved context → trust the context.
"""

_LANG_SUFFIX = {
    "English": (
        "\n\nRESPOND IN ENGLISH ONLY. Plain, friendly, direct English — the user "
        "is a regular citizen, not a lawyer. Avoid legal jargon unless you explain "
        "it immediately after. Speak directly to the user as 'you'."
    ),
    "Urdu": (
        "\n\nجواب صرف اردو میں دیں۔\n"
        "زبان کا انداز: سادہ، گرم جوشی سے بھرا، اور عملی — جیسے کوئی جاننے والا "
        "دوست بات کر رہا ہو۔ بھاری ادبی اردو سے بالکل پرہیز کریں۔\n"
        "مثال کے طور پر:\n"
        "  ✗ 'بمطابق قانون مزید دفعات نافذ العمل ہیں' — بہت بھاری\n"
        "  ✓ 'قانون کے مطابق آپ کا پورا حق ہے کہ آپ کی تنخواہ وقت پر ملے' — سادہ اور واضح\n"
        "قانون کا نام جیسا سیاق میں ہے ویسا ہی لکھیں (مثال: Payment of Wages Act) — ترجمہ نہ کریں۔\n"
        "دفعہ نمبر صرف تب لکھیں جب وہ سیاق میں موجود ہو۔\n"
        "صارف کو براہ راست 'آپ' کہہ کر مخاطب کریں۔ 'صارف' یا 'درخواست گزار' نہ لکھیں۔\n"
        "جملے مختصر رکھیں۔ ہر بات سیدھی کہیں۔"
    ),
}

_NO_CONTEXT_REPLY = {
    "English": (
        "I couldn't find a Pakistani law in my knowledge base that directly covers "
        "this question. Could you share a few more details — for example, what "
        "happened, who was involved, and where (workplace, home, online)? With more "
        "specifics I can usually find the right law. For anything urgent, please "
        "speak to a qualified lawyer."
    ),
    "Urdu": (
        "مجھے اس سوال سے متعلق کوئی براہ راست پاکستانی قانون نہیں ملا۔ "
        "اگر آپ تھوڑی اور تفصیل دیں — کیا ہوا، کس کے ساتھ ہوا، اور کہاں — "
        "تو میں دوبارہ تلاش کر سکتا ہوں۔ "
        "فوری معاملے میں کسی وکیل سے ضرور بات کریں۔"
    ),
}

_VAGUE_QUERY_REPLY = {
    "English": (
        "Could you share a bit more detail so I can help properly? For example: "
        "what happened, who is involved, and what you would like to do about it?"
    ),
    "Urdu": (
        "ذرا تھوڑی تفصیل بتائیں تاکہ میں صحیح مدد کر سکوں۔ مثلاً: "
        "کیا ہوا، کون ملوث ہے، اور آپ اب کیا کرنا چاہتے ہیں؟"
    ),
}

_OFF_TOPIC_REPLY_TEMPLATE = {
    "English": (
        "I can only help with questions about your current case "
        "(**{category}**). Your question seems to be about a different topic.\n\n"
        "Please ask something related to your case — for example, about your rights, "
        "the laws that apply, or the next steps you can take.\n\n"
        "If you want to ask about a different legal issue, please run a new case "
        "analysis above first."
    ),
    "Urdu": (
        "میں صرف آپ کے موجودہ کیس (**{category}**) سے متعلق سوالات کا جواب دے سکتا ہوں۔ "
        "آپ کا سوال کسی مختلف موضوع پر لگ رہا ہے۔\n\n"
        "براہ کرم اپنے کیس سے متعلق کوئی سوال پوچھیں — مثلاً اپنے حقوق، "
        "لاگو ہونے والے قوانین، یا اگلے اقدامات کے بارے میں۔\n\n"
        "اگر کسی مختلف مسئلے کے بارے میں پوچھنا ہے تو پہلے نیا کیس تجزیہ کریں۔"
    ),
}

_WEAK_CONTEXT_REPLY = {
    "English": (
        "I found some related Pakistani law, but the match isn't strong enough "
        "for me to answer with full confidence. Could you share a few more "
        "specifics? For anything important, please also consult a lawyer."
    ),
    "Urdu": (
        "کچھ متعلقہ قوانین ملے ہیں لیکن پورے اعتماد سے جواب دینے کے لیے "
        "تھوڑی اور تفصیل درکار ہے۔ اہم معاملے پر وکیل سے مشورہ ضرور کریں۔"
    ),
}


# ── Structured source document ─────────────────────────────────────────────────

@dataclass
class SourceDoc:
    """A single retrieved law document with full traceability."""
    title:   str
    section: str
    snippet: str
    score:   float

# ── Session management ────────────────────────────────────────────────────────

def get_or_create_session(session_id: str) -> dict:
    with _store_lock:
        _prune_expired()
        if session_id not in _store:
            _store[session_id] = _Session(session_id=session_id)
            logger.info("Chat: new session created — %s", session_id)
        session = _store[session_id]
        session.last_active = time.time()
        return {
            "session_id": session.session_id,
            "turns":      len(session.history) // 2,
        }


def append_message(session_id: str, role: str, content: str) -> None:
    if role not in ("user", "assistant"):
        raise ValueError(f"Invalid role '{role}'. Must be 'user' or 'assistant'.")

    with _store_lock:
        if session_id not in _store:
            _store[session_id] = _Session(session_id=session_id)

        session = _store[session_id]
        session.history.append({"role": role, "content": content})
        session.last_active = time.time()

        # v5: extract and accumulate case facts from user messages
        if role == "user":
            new_facts = _extract_case_facts(content)
            for fact in new_facts:
                if fact not in session.case_facts:
                    session.case_facts.append(fact)
            # Keep at most 12 facts (oldest drop off)
            session.case_facts = session.case_facts[-12:]

        max_msgs = MAX_HISTORY_TURNS * 2
        if len(session.history) > max_msgs:
            session.history = session.history[-max_msgs:]


def get_recent_history(session_id: str, n: int = MAX_HISTORY_TURNS) -> list[dict]:
    with _store_lock:
        session = _store.get(session_id)
        if not session:
            return []
        return list(session.history[-(n * 2):])


def _get_case_facts(session_id: str) -> list[str]:
    """Return accumulated case facts for the session."""
    with _store_lock:
        session = _store.get(session_id)
        if not session:
            return []
        return list(session.case_facts)


def clear_session(session_id: str) -> None:
    with _store_lock:
        if session_id in _store:
            _store[session_id].history.clear()
            _store[session_id].case_facts.clear()
            logger.info("Chat: session cleared — %s", session_id)


def _prune_expired() -> None:
    now = time.time()
    expired = [sid for sid, s in _store.items()
               if now - s.last_active > SESSION_TTL_SECS]
    for sid in expired:
        del _store[sid]
    if expired:
        logger.info("Chat: pruned %d expired sessions", len(expired))


# ── Response dataclass ────────────────────────────────────────────────────────

@dataclass
class ChatResponse:
    reply:      str
    sources:    list[SourceDoc]
    confidence: str
    session_id: str
    error:      Optional[str] = None


# ── Core chat function ────────────────────────────────────────────────────────

def chat(
    session_id:    str,
    message:       str,
    language:      str = "English",
    case_context:  Optional[dict] = None,
) -> ChatResponse:
    # ── 0. Ensure session exists ───────────────────────────────────────────────
    get_or_create_session(session_id)

    # ── Gate 1: Validate + sanitize ───────────────────────────────────────────
    try:
        clean_message = sanitize(message)
    except ValidationError as ve:
        return ChatResponse(
            reply=str(ve), sources=[], confidence="low",
            session_id=session_id, error="validation_error",
        )

    # ── Gate 0: Topic Scope (only when a case is active) ──────────────────────
    if case_context:
        on_topic, scope_reason = _is_on_topic(clean_message, case_context)
        if not on_topic:
            category = case_context.get("category", "").strip() or "your case"
            template = _OFF_TOPIC_REPLY_TEMPLATE.get(language, _OFF_TOPIC_REPLY_TEMPLATE["English"])
            off_topic_reply = template.format(category=category)
            append_message(session_id, "user", clean_message)
            append_message(session_id, "assistant", off_topic_reply)
            return ChatResponse(
                reply=off_topic_reply, sources=[], confidence="low",
                session_id=session_id,
            )

    # ── Gate 2: Vague query guard ──────────────────────────────────────────────
    if _is_too_vague(clean_message):
        vague_reply = _VAGUE_QUERY_REPLY.get(language, _VAGUE_QUERY_REPLY["English"])
        append_message(session_id, "user", clean_message)
        append_message(session_id, "assistant", vague_reply)
        return ChatResponse(
            reply=vague_reply, sources=[], confidence="low",
            session_id=session_id,
        )

    # ── MANDATORY RAG retrieval ────────────────────────────────────────────────
    retrieval_query = _build_retrieval_query(clean_message, session_id, case_context)
    raw_chunks = retrieve(retrieval_query, top_k=TOP_K_CHAT)

    # ── Gate 3a: HARD RETRIEVAL GATE ──────────────────────────────────────────
    qualified_chunks = _filter_chunks(raw_chunks, case_context)

    if not qualified_chunks:
        no_ctx_reply = _NO_CONTEXT_REPLY.get(language, _NO_CONTEXT_REPLY["English"])
        append_message(session_id, "user", clean_message)
        append_message(session_id, "assistant", no_ctx_reply)
        return ChatResponse(
            reply=no_ctx_reply, sources=[], confidence="low",
            session_id=session_id,
        )

    # ── Gate 3b: WEAK CONTEXT ASSESSMENT ─────────────────────────────────────
    weak, weak_reason = _is_context_weak(qualified_chunks)
    if weak:
        logger.info("Chat [%s] Gate 3b WARNING — %s", session_id, weak_reason)

    # ── Build LLM prompt ───────────────────────────────────────────────────────
    history    = get_recent_history(session_id, n=PROMPT_HISTORY_TURNS)
    case_facts = _get_case_facts(session_id)
    context    = _format_context(qualified_chunks)
    user_msg   = _build_user_message(
        context, history, clean_message, language,
        weak_context=weak, case_context=case_context,
        case_facts=case_facts,
    )

    # ── Gates 4+5: Groq LLM ───────────────────────────────────────────────────
    try:
        reply_text = _call_groq(user_msg, language)
    except Exception as exc:
        logger.error("Chat [%s]: Groq call failed — %s", session_id, exc)
        return ChatResponse(
            reply=_NO_CONTEXT_REPLY.get(language, _NO_CONTEXT_REPLY["English"]),
            sources=[], confidence="low", session_id=session_id,
            error=f"llm_error: {exc}",
        )

    # ── Build structured sources + confidence ─────────────────────────────────
    sources    = _build_sources(qualified_chunks)
    confidence = _score_confidence(qualified_chunks, reply=reply_text,
                                   case_context=case_context)

    # ── Persist exchange ───────────────────────────────────────────────────────
    append_message(session_id, "user",      clean_message)
    append_message(session_id, "assistant", reply_text)

    return ChatResponse(
        reply=reply_text, sources=sources,
        confidence=confidence, session_id=session_id,
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

# ── v5: Case-fact extractor ───────────────────────────────────────────────────
# Identifies user-mentioned evidence, facts, and details from user messages.
# These are accumulated across the session so the LLM can reference them
# in later turns without the user repeating themselves.

_FACT_PATTERNS: list[tuple[str, str]] = [
    # Evidence types
    (r'\bsalary slip[s]?\b',          "User has salary slips as evidence"),
    (r'\bpay slip[s]?\b',             "User has pay slips as evidence"),
    (r'\bwhatsapp message[s]?\b',     "User has WhatsApp messages as evidence"),
    (r'\btext message[s]?\b',         "User has text messages as evidence"),
    (r'\bemail[s]?\b',                "User has email(s) as evidence"),
    (r'\breceipt[s]?\b',              "User has receipts as evidence"),
    (r'\bphoto[s]?\b|\bpicture[s]?\b',   "User has photos as evidence"),
    (r'\bwitness(?:es)?\b',           "User has witnesses"),
    (r'\bcontract\b|\bagreement\b',   "User has a written contract/agreement"),
    (r'\bvideo[s]?\b|\brecording[s]?\b',"User has video/audio recordings"),
    (r'\bmedical report\b|\bMLR\b',   "User has a medical/medico-legal report"),
    # Employment facts
    (r'\b(\d+)\s*month[s]?\s*(?:of\s*)?(?:unpaid|delayed|salary|wages)',
                                      "User has months of unpaid wages"),
    (r'\bovertime\b',                 "User is claiming unpaid overtime"),
    (r'\bfired\b|\bterminated\b|\bdismissed\b', "User was fired/terminated"),
    (r'\bno\s*written\s*contract\b',  "User does not have a written contract"),
    # Property facts
    (r'\bsecurity deposit\b',         "User paid a security deposit"),
    (r'\bevict(?:ed|ion)\b',          "User is facing/has faced eviction"),
    # Location facts
    (r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b', ""),  # city extraction handled separately
    # Injury facts
    (r'\binjur(?:ed|y|ies)\b|\baccident\b', "User or colleague has injuries"),
    (r'\bhospital\b',                 "User visited/mentioned hospital"),
    # Urdu evidence keywords
    (r'تنخواہ کی پرچی|سیلری سلپ',   "User has salary slips (mentioned in Urdu)"),
    (r'واٹس ایپ|وٹس اپ',             "User has WhatsApp messages (mentioned in Urdu)"),
    (r'گواہ',                         "User has witnesses (mentioned in Urdu)"),
    (r'تصویر|ویڈیو',                  "User has photos/videos (mentioned in Urdu)"),
]


def _extract_case_facts(user_message: str) -> list[str]:
    """
    Extract factual mentions from a user message — evidence, circumstances,
    and context that should be remembered across follow-up turns.

    Returns a list of plain-English fact strings for inclusion in the prompt.
    Pure regex — no LLM, no hallucination risk.
    """
    facts: list[str] = []
    msg_lower = user_message.lower()

    for pattern, fact_label in _FACT_PATTERNS:
        if not fact_label:
            continue
        if re.search(pattern, msg_lower, re.IGNORECASE):
            if fact_label not in facts:
                facts.append(fact_label)

    return facts


# ── Domain priority reranker ──────────────────────────────────────────────────
# Maps case category → primary law name fragments.
# Chunks whose law_name contains a primary fragment get a score boost during
# filtering, so they rank ahead of cross-domain chunks with similar raw scores.

_DOMAIN_PRIMARY_LAWS: dict[str, list[str]] = {
    "Labour Law":     ["payment of wages", "factories act", "industrial relations",
                       "employment", "workmen", "minimum wages", "labour"],
    "Employment":     ["payment of wages", "factories act", "industrial relations",
                       "employment", "workmen", "minimum wages", "labour"],
    "Family Law":     ["muslim family", "dissolution of marriage", "guardians",
                       "child marriage", "dowry", "family"],
    "Property Law":   ["transfer of property", "rent", "tenancy", "land",
                       "registration", "specific relief"],
    "Property / Tenant": ["transfer of property", "rent", "tenancy", "land",
                          "registration", "specific relief"],
    "Criminal Law":   ["penal code", "criminal procedure", "crpc", "police",
                       "bail", "offences"],
    "Criminal":       ["penal code", "criminal procedure", "crpc", "police",
                       "bail", "offences"],
    "Harassment":     ["prevention of anti-women", "harassment at workplace",
                       "protection against harassment", "penal code"],
    "Harassment / Abuse": ["prevention of anti-women", "harassment at workplace",
                           "protection against harassment", "penal code"],
    "Cybercrime":     ["electronic crimes", "peca", "prevention of electronic",
                       "cyber", "digital"],
    "Inheritance Law":["succession", "inheritance", "muslim personal law",
                       "transfer of property"],
    "Constitutional Law": ["constitution", "fundamental rights", "high court",
                           "supreme court"],
    "Contract Law":   ["contract act", "specific relief", "limitation",
                       "arbitration"],
    "Consumer Rights":["consumer protection", "competition", "trade marks"],
}

# Suppressed sections that should never be cited (definitional/jurisdictional)
_SUPPRESS_SECTION_PATTERNS = re.compile(
    r'(?:^|\s)(?:section\s*1\b|section\s*2\b(?!\s*[a-z]))'
    r'|(?:title\s+and\s+extent|short\s+title|definitions?\s+in\s+this\s+act)',
    re.IGNORECASE,
)


def _domain_score_boost(chunk: dict, case_category: str) -> float:
    """
    Return a score boost (0.0–0.12) for chunks whose law_name matches
    the primary laws for the case's legal domain.

    Chunks from the right domain get a boost; cross-domain chunks get
    a penalty. This ensures labour-law chunks rank ahead of PPC chunks
    in a labour dispute even if PPC had a slightly higher raw similarity.
    """
    if not case_category:
        return 0.0

    law_name = chunk.get("law_name", "").lower()
    primary_laws = _DOMAIN_PRIMARY_LAWS.get(case_category, [])

    if any(p in law_name for p in primary_laws):
        return 0.08   # strong domain match → boost
    # Check if this is clearly a different domain (not just unrecognised)
    all_primary = {law for laws in _DOMAIN_PRIMARY_LAWS.values() for law in laws}
    if any(p in law_name for p in all_primary):
        return -0.05  # cross-domain law → penalise
    return 0.0        # unknown/neutral → no change


def _is_suppressed_section(chunk: dict) -> bool:
    """Return True if this chunk is a definitional/jurisdictional section."""
    section = chunk.get("section", "") or ""
    text    = chunk.get("text", "")[:120]
    if _SUPPRESS_SECTION_PATTERNS.search(section):
        return True
    if _SUPPRESS_SECTION_PATTERNS.search(text):
        return True
    return False


# ── Context weak detector ─────────────────────────────────────────────────────

def _is_context_weak(chunks: list[dict]) -> tuple[bool, str]:
    if not chunks:
        return True, "no chunks"
    scores = [float(c.get("score", 0.0)) for c in chunks]
    avg    = sum(scores) / len(scores)
    count  = len(chunks)
    if count < WEAK_CONTEXT_MIN_DOCS:
        return True, f"only {count} chunk(s) < min {WEAK_CONTEXT_MIN_DOCS}"
    if avg < WEAK_CONTEXT_AVG_SCORE:
        return True, f"avg_score {avg:.3f} < threshold {WEAK_CONTEXT_AVG_SCORE}"
    return False, ""


def _clean_snippet(text: str, max_chars: int = 180) -> str:
    clean = text.strip()
    clean = re.sub(r'[\r\n\t]+', ' ', clean)
    clean = re.sub(r' {2,}', ' ', clean)
    if len(clean) > max_chars:
        clean = clean[:max_chars].rstrip() + "…"
    return clean


def _is_too_vague(message: str) -> bool:
    words = message.strip().split()
    if len(words) < 4:
        return True
    _generic = {"hello", "hi", "help", "ok", "okay", "yes", "no", "thanks", "thank"}
    if len(words) == 1 and words[0].lower() in _generic:
        return True
    return False


def _build_retrieval_query(
    message:      str,
    session_id:   str,
    case_context: Optional[dict] = None,
) -> str:
    history = get_recent_history(session_id, n=2)
    prev_user_msgs = [h["content"] for h in history if h["role"] == "user"]
    prior = prev_user_msgs[-1] if prev_user_msgs else ""

    case_terms = ""
    if case_context:
        category   = (case_context.get("category")   or "").strip()
        last_query = (case_context.get("last_query") or "").strip()
        case_terms = f"{category} {last_query[:120]}".strip()

    expansions = _expand_query_keywords(message)
    parts      = [p for p in [prior, case_terms, message, expansions] if p.strip()]
    combined   = " ".join(parts)
    return preprocess_query(combined)


# ── Query keyword synonym map ─────────────────────────────────────────────────

_KEYWORD_SYNONYMS: dict[str, str] = {
    "evict":             "eviction tenant landlord lease termination",
    "kicking out":       "eviction tenant landlord notice",
    "kick out":          "eviction tenant notice lease",
    "landlord":          "landlord tenant lease rent property",
    "tenant":            "tenant landlord rent lease deposit",
    "rent":              "rent lease tenancy landlord deposit",
    "deposit":           "security deposit refund tenant landlord",
    "property":          "property land ownership title deed",
    "ownership":         "ownership title property registration",
    "divorce":           "divorce talaq dissolution marriage khula",
    "khula":             "khula divorce wife dissolution marriage",
    "talaq":             "talaq divorce dissolution marriage",
    "marriage":          "marriage nikah registration dissolution",
    "custody":           "custody child guardian minor welfare",
    "child":             "child minor custody guardian welfare",
    "inheritance":       "inheritance succession wirasat estate property",
    "dowry":             "dowry mehr bridal gifts marriage",
    "salary":            "salary wages payment employer employee",
    "wages":             "wages salary payment employment",
    "fired":             "termination dismissal employment wrongful",
    "terminated":        "termination dismissal employment notice",
    "employer":          "employer employee wages contract labour",
    "overtime":          "overtime wages payment labour act",
    "worker":            "worker employee labourer rights wages",
    "fir":               "FIR first information report police complaint",
    "arrested":          "arrest detention police custody bail",
    "bail":              "bail arrest detention court criminal",
    "police":            "police FIR complaint arrest station",
    "complaint":         "complaint FIR police report filing",
    "harassment":        "harassment workplace sexual complaint FIR",
    "domestic violence": "domestic violence abuse complaint protection",
    "abuse":             "abuse violence harassment protection complaint",
    "contract":          "contract agreement breach enforcement remedies",
    "agreement":         "agreement contract terms breach remedies",
    "breach":            "breach contract agreement remedies enforcement",
    "sue":               "lawsuit civil suit court claim damages",
    "court":             "court civil criminal procedure jurisdiction",
    "compensation":      "compensation damages remedy court civil",
    "rights":            "rights entitlement legal remedy law",
    "evidence":          "evidence proof document witness court",
    "documents":         "documents evidence proof salary slip contract",
    "proof":             "proof evidence document witness",
    "whatsapp":          "electronic evidence digital communication proof",
    "message":           "electronic evidence digital communication",
    "fired for complaining": "unfair termination whistleblower retaliation labour",
    "retaliation":       "unfair termination retaliatory dismissal labour",
    "complain":          "complaint grievance labour authority workplace",
    "unpaid":            "unpaid wages salary delay payment wages act",
    "overtime":          "overtime extra hours wages payment factories act",
}


def _expand_query_keywords(message: str) -> str:
    msg_lower  = message.lower()
    expansions: list[str] = []
    seen:       set[str]  = set()
    for phrase, expansion in _KEYWORD_SYNONYMS.items():
        if phrase in msg_lower and expansion not in seen:
            expansions.append(expansion)
            seen.add(expansion)
    return " ".join(expansions)


# ── TOPIC SCOPE GATE (Gate 0) ─────────────────────────────────────────────────

_CATEGORY_KEYWORDS: dict[str, set[str]] = {
    "Family Law": {
        "marriage", "marry", "married", "nikah", "wife", "husband", "spouse",
        "divorce", "talaq", "khula", "dissolution", "maintenance", "nafaqa",
        "custody", "guardian", "minor", "child", "children", "dowry", "mehr",
        "alimony", "family", "domestic", "in-laws", "adoption", "shadi",
        "bachay", "bachon", "biwi", "shauhar",
    },
    "Labour Law": {
        "salary", "wages", "wage", "pay", "paycheck", "employer", "employee",
        "boss", "company", "fired", "termination", "terminated", "dismissed",
        "dismissal", "resignation", "resigned", "overtime", "leave", "labour",
        "labor", "worker", "workplace", "factory", "industrial", "tnkhwah",
        "naukri", "mulazim", "kaam", "office", "shift", "workman",
        "unpaid", "retaliation", "complain", "grievance",
    },
    "Employment": {
        "salary", "wages", "wage", "pay", "paycheck", "employer", "employee",
        "boss", "company", "fired", "termination", "terminated", "dismissed",
        "dismissal", "resignation", "resigned", "overtime", "leave", "labour",
        "labor", "worker", "workplace", "factory", "industrial",
        "unpaid", "retaliation", "complain", "grievance",
    },
    "Property Law": {
        "property", "land", "house", "home", "flat", "apartment", "plot",
        "rent", "rental", "lease", "tenant", "landlord", "deposit", "eviction",
        "evict", "ownership", "owner", "title", "deed", "registry", "transfer",
        "sale", "purchase", "buy", "sold", "boundary", "encroachment",
        "zameen", "makaan", "kiraya", "qabza", "malkiyat",
    },
    "Property / Tenant": {
        "property", "land", "house", "home", "flat", "apartment", "plot",
        "rent", "rental", "lease", "tenant", "landlord", "deposit", "eviction",
        "evict", "ownership", "owner", "title", "deed", "registry", "transfer",
        "zameen", "makaan", "kiraya", "qabza", "malkiyat",
    },
    "Criminal Law": {
        "fir", "police", "arrest", "arrested", "bail", "thana", "investigation",
        "complaint", "crime", "criminal", "theft", "robbery", "fraud", "assault",
        "murder", "kidnap", "kidnapping", "abduction", "violence", "weapon",
        "court", "case", "trial", "judge", "magistrate", "prosecutor",
        "rapt", "qatal", "chori", "dhoka", "girftari",
    },
    "Criminal": {
        "fir", "police", "arrest", "arrested", "bail", "thana", "investigation",
        "complaint", "crime", "criminal", "theft", "robbery", "fraud", "assault",
        "murder", "kidnap", "kidnapping", "abduction", "violence", "weapon",
        "court", "case", "trial", "judge", "magistrate", "prosecutor",
    },
    "Harassment": {
        "harassment", "harass", "harassed", "stalking", "stalker", "abuse",
        "abused", "abuser", "domestic", "violence", "molestation", "assault",
        "threats", "threatened", "intimidation", "blackmail", "workplace",
        "tang", "ziadati", "torture",
    },
    "Harassment / Abuse": {
        "harassment", "harass", "harassed", "stalking", "stalker", "abuse",
        "abused", "abuser", "domestic", "violence", "molestation", "assault",
        "threats", "threatened", "intimidation", "blackmail", "workplace",
    },
    "Cybercrime": {
        "cyber", "online", "internet", "social", "media", "facebook", "whatsapp",
        "instagram", "hack", "hacked", "hacking", "phishing", "fraud", "scam",
        "blackmail", "fake", "account", "impersonation", "leaked", "leak",
        "data", "privacy", "fia",
    },
    "Inheritance Law": {
        "inheritance", "heir", "heirs", "wirasat", "succession", "will",
        "testament", "estate", "deceased", "death", "share", "property",
        "siblings", "father", "mother",
    },
    "Constitutional Law": {
        "constitution", "rights", "fundamental", "freedom", "speech",
        "petition", "writ", "habeas", "high", "supreme", "court",
    },
    "Civil Law / Procedure": {
        "civil", "suit", "lawsuit", "court", "procedure", "summons", "notice",
        "decree", "judgment", "appeal", "compensation", "damages", "claim",
    },
    "Contract Law": {
        "contract", "agreement", "breach", "deal", "promise", "signed",
        "obligation", "party", "parties", "terms", "performance",
    },
    "Consumer Rights": {
        "consumer", "product", "service", "refund", "warranty", "defective",
        "shopkeeper", "shop", "purchase", "bought",
    },
    "General / Other": set(),
    "Other": set(),
}

_STOPWORDS: set[str] = {
    "a", "an", "the", "and", "or", "but", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "can", "i", "you", "he",
    "she", "it", "we", "they", "me", "him", "her", "us", "them", "my",
    "your", "his", "its", "our", "their", "this", "that", "these", "those",
    "what", "where", "when", "who", "why", "how", "which", "to", "from",
    "in", "on", "at", "by", "for", "with", "about", "against", "between",
    "into", "through", "during", "before", "after", "above", "below", "of",
    "if", "then", "else", "so", "than", "as", "ka", "ki", "ke", "ko", "se",
    "main", "hai", "hain", "tha", "thi", "the", "ho", "ya",
}

_GENERIC_LEGAL_TERMS: set[str] = {
    "law", "laws", "legal", "right", "rights", "case", "cases",
    "court", "courts", "judge", "lawyer", "advocate", "wakeel",
    "qanoon", "haq", "advice", "help", "question", "answer",
    "file", "filed", "filing", "submit", "submitted", "apply", "applied",
    "make", "made", "do", "done", "get", "got", "take", "taken",
    "register", "registered", "lodge", "lodged",
    "procedure", "process", "step", "steps", "action", "actions",
    "document", "documents", "paper", "papers", "form", "forms",
    "what", "should", "next", "how", "why", "when", "where", "which",
    "tell", "explain", "know", "want", "need", "needs",
    "pakistan", "country", "city", "time", "now", "today",
    # Evidence words — should not trigger off-topic on their own
    "evidence", "proof", "enough", "sufficient", "collect", "gather",
}


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z\u0600-\u06FF]+", text.lower())
    return {t for t in tokens if len(t) >= 3 and t not in _STOPWORDS}


def _is_on_topic(message: str, case_context: dict) -> tuple[bool, str]:
    category = (case_context.get("category") or "").strip()
    summary  = (case_context.get("summary")  or "").strip()
    last_q   = (case_context.get("last_query") or "").strip()

    if not category or category in {"General / Other", "Other", "Unknown"}:
        return True, "no category restriction"

    msg_tokens = _tokenize(message)
    if not msg_tokens:
        return True, "empty token set"

    informative = msg_tokens - _GENERIC_LEGAL_TERMS
    if not informative:
        return True, "purely generic query"

    if len(msg_tokens) <= 12:
        return True, "short follow-up query — deferring to retrieval/LLM gates"

    cat_tokens   = _tokenize(category)
    if cat_tokens & informative:
        return True, f"mentions category '{category}'"

    cat_keywords = _CATEGORY_KEYWORDS.get(category, set())
    if cat_keywords & informative:
        return True, f"category-keyword overlap: {cat_keywords & informative}"

    summary_tokens = _tokenize(summary) - _GENERIC_LEGAL_TERMS - _STOPWORDS
    if summary_tokens & informative:
        return True, f"summary overlap: {summary_tokens & informative}"

    last_q_tokens = _tokenize(last_q) - _GENERIC_LEGAL_TERMS - _STOPWORDS
    if last_q_tokens & informative:
        return True, f"original-query overlap: {last_q_tokens & informative}"

    return False, f"no overlap with case '{category}'"


def _filter_chunks(chunks: list[dict],
                   case_context: Optional[dict] = None) -> list[dict]:
    """
    HARD RETRIEVAL GATE — with v5 domain-priority reranking.

    1. Discard chunks below RETRIEVAL_SCORE_THRESHOLD.
    2. Discard definitional/jurisdictional sections (Section 1, Section 2 extents).
    3. Apply domain-priority boost/penalty based on the case's legal category.
    4. Re-sort by adjusted score and return top MAX_CHUNKS_TO_LLM.
    """
    case_category = ""
    if case_context:
        case_category = (case_context.get("category") or "").strip()

    # Step 1+2: hard score filter + suppress definitional sections
    qualified = []
    for c in chunks:
        raw_score = float(c.get("score", 0.0))
        if raw_score < RETRIEVAL_SCORE_THRESHOLD:
            continue
        if _is_suppressed_section(c):
            logger.debug("Suppressed definitional section: %s — %s",
                         c.get("law_name", ""), c.get("section", ""))
            continue
        qualified.append(c)

    # Step 3: apply domain-priority score adjustment
    if case_category and qualified:
        for c in qualified:
            boost = _domain_score_boost(c, case_category)
            c["_adjusted_score"] = float(c.get("score", 0.0)) + boost
    else:
        for c in qualified:
            c["_adjusted_score"] = float(c.get("score", 0.0))

    # Step 4: sort by adjusted score, return top N
    qualified.sort(key=lambda c: c["_adjusted_score"], reverse=True)
    return qualified[:MAX_CHUNKS_TO_LLM]


def _format_context(chunks: list[dict]) -> str:
    lines: list[str] = []
    total_chars = 0

    for i, chunk in enumerate(chunks, 1):
        law      = chunk.get("law_name", "Unknown Law")
        section  = chunk.get("section", "")
        category = chunk.get("category", "")
        score    = float(chunk.get("score", 0.0))
        text     = chunk.get("text", "").strip()

        header = f"[{i}] {law}"
        if section:
            header += f" — {section}"
        if category:
            header += f" ({category})"
        header += f" [relevance: {score:.0%}]"

        block = f"{header}\n{text}"

        if total_chars + len(block) > MAX_CONTEXT_CHARS:
            remaining = MAX_CONTEXT_CHARS - total_chars
            if remaining > 200:
                lines.append(block[:remaining] + "…")
            break

        lines.append(block)
        total_chars += len(block)

    return "\n\n".join(lines)


def _build_user_message(
    context:      str,
    history:      list[dict],
    query:        str,
    language:     str,
    weak_context: bool = False,
    case_context: Optional[dict] = None,
    case_facts:   Optional[list[str]] = None,
) -> str:
    """
    Assemble the full user-turn message sent to Groq.

    Priority order (context first, history last):
        Priority 1 — Retrieved legal context  (only legal knowledge source)
        Priority 2 — Case facts + active case  (user's situation — background)
        Priority 3 — User's current query
        Priority 4 — Conversation history      (topic continuity only)

    v5 additions:
        • CASE FACTS block: evidence and details extracted from prior turns.
        • History char budget raised (800→1200) and per-msg cap raised (200→300)
          so evidence mentioned earlier survives into later turns.
    """
    lang_instruction = _LANG_SUFFIX.get(language, _LANG_SUFFIX["English"])

    # Format history block
    if history:
        hist_lines: list[str] = []
        used_chars = 0
        for msg in reversed(history):
            role    = "User" if msg["role"] == "user" else "Assistant"
            content = msg["content"]
            if len(content) > MAX_HISTORY_PER_MSG:
                content = content[:MAX_HISTORY_PER_MSG] + "…"
            line = f"{role}: {content}"
            if used_chars + len(line) > MAX_HISTORY_CHARS:
                break
            hist_lines.append(line)
            used_chars += len(line)
        history_block = "\n".join(reversed(hist_lines))
    else:
        history_block = "(No prior conversation)"

    # ── Active case block ─────────────────────────────────────────────────────
    case_block = ""
    if case_context:
        category   = case_context.get("category", "")
        risk       = case_context.get("risk_level", "")
        summary    = case_context.get("summary", "")
        last_query = case_context.get("last_query", "")
        if len(summary)    > 400: summary    = summary[:400]    + "…"
        if len(last_query) > 200: last_query = last_query[:200] + "…"

        case_lines = []
        if category:   case_lines.append(f"  • Category:           {category}")
        if risk:       case_lines.append(f"  • Risk level:         {risk}")
        if last_query: case_lines.append(f"  • User's original query: {last_query}")
        if summary:    case_lines.append(f"  • Case summary:       {summary}")

        # v5: inject case facts (evidence mentioned in prior turns)
        if case_facts:
            facts_str = "\n".join(f"  • {f}" for f in case_facts)
            case_lines.append(f"  • Evidence/facts user mentioned:\n{facts_str}")

        if case_lines:
            case_block = (
                "══════════ ACTIVE CASE + CASE FACTS (BACKGROUND — NOT A SOURCE) ══════════\n"
                "This is what the user has told us across this conversation.\n"
                "Use it to personalise your answer. Do NOT cite it as legal authority.\n"
                + "\n".join(case_lines) + "\n"
                "If the user mentioned specific evidence (salary slips, WhatsApp messages,\n"
                "photos, witnesses) — reference them directly in your answer.\n"
                "═══════════════════════════════════════════════════════════════════════════\n\n"
            )
    elif case_facts:
        # No formal case_context but facts were extracted — still inject them
        facts_str = "\n".join(f"  • {f}" for f in case_facts)
        case_block = (
            "══════════ CASE FACTS FROM PRIOR TURNS ══════════\n"
            f"{facts_str}\n"
            "Use these facts to personalise your answer.\n"
            "══════════════════════════════════════════════════\n\n"
        )

    # Weak-context warning
    if weak_context:
        context_header = (
            "══════════ PRIORITY 1 — RETRIEVED LEGAL CONTEXT ══════════\n"
            "⚠ PARTIAL CONTEXT — Limited information retrieved.\n"
            "Answer only what the context explicitly supports.\n"
            "State any gap briefly. Do not fill gaps with invented laws.\n"
            "THIS IS YOUR ONLY PERMITTED SOURCE OF LEGAL FACTS.\n"
        )
    else:
        context_header = (
            "══════════ PRIORITY 1 — RETRIEVED LEGAL CONTEXT ══════════\n"
            "THIS IS YOUR ONLY PERMITTED SOURCE OF LEGAL FACTS.\n"
        )

    return (
        f"LANGUAGE: {language}{lang_instruction}\n\n"

        f"{context_header}"
        f"{context}\n"
        f"══════════════════════════════════════════════════════════\n\n"

        f"{case_block}"

        f"PRIORITY 3 — USER QUERY:\n"
        f"{query}\n\n"

        f"══════════ PRIORITY 4 — CONVERSATION HISTORY (LOWEST) ══════════\n"
        f"For topic continuity only. If history conflicts with Priority 1, trust Priority 1.\n"
        f"{history_block}\n"
        f"═════════════════════════════════════════════════════════════════\n\n"

        f"RESPOND NOW — Answer the user's query directly. Apply the retrieved laws to "
        f"THEIR specific situation (use the Active Case + Case Facts block to personalise). "
        f"Lead with what the PRIMARY laws say. If you must infer standard Pakistani "
        f"procedure for a gap, mark it as 'In practice...' — once only. "
        f"End with one sentence recommending a lawyer for specifics. "
        f"Do NOT use the banned phrases listed in your instructions."
    )


def _call_groq(user_message: str, language: str) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not configured.")

    system_prompt = _CHAT_SYSTEM_PROMPT + _LANG_SUFFIX.get(language, "")

    response = call_groq_with_rotation(lambda c: c.chat.completions.create(
        model=GROQ_LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
        temperature=0.15,
        max_tokens=900,
    ))
    return (response.choices[0].message.content or "").strip()


def _build_sources(chunks: list[dict]) -> list[SourceDoc]:
    seen_keys: set[tuple[str, str]] = set()
    sources:   list[SourceDoc]      = []

    for chunk in chunks:
        title   = chunk.get("law_name", "Unknown Law")
        section = chunk.get("section", "") or ""
        text    = chunk.get("text", "")
        score   = round(float(chunk.get("score", 0.0)), 4)

        key = (title, section)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        sources.append(SourceDoc(
            title=title, section=section,
            snippet=_clean_snippet(text), score=score,
        ))

    return sources


# ── v5: Multi-factor confidence scoring ───────────────────────────────────────

# F3 — inference markers that reduce confidence (LLM hedged, not grounded fully)
_INFERENCE_MARKERS_EN: tuple[str, ...] = (
    "typically in pakistan",
    "in practice",
    "usually in pakistan",
    "generally speaking",
    "the usual approach",
    "normally in pakistan",
    "it is common practice",
    "you would typically",
    "standard procedure",
    "in most cases",
)
_INFERENCE_MARKERS_UR: tuple[str, ...] = (
    "عام طور پر",
    "عموماً",
    "روایتی طور پر",
    "پاکستان میں عام",
    "عملی طور پر",
)

# F4 — refusal/uncertainty markers (force "low")
_REFUSAL_MARKERS_EN: tuple[str, ...] = (
    "i do not have enough information",
    "i don't have enough information",
    "not enough information in the retrieved",
    "i cannot answer",
    "i can't answer",
    "i am unable to answer",
    "i'm unable to answer",
    "insufficient information",
    "the retrieved context does not",
    "the retrieved documents do not",
    "i do not have sufficient",
    "i don't have sufficient",
    "is not in the context",
    "is not provided in the context",
    "is not mentioned in the context",
    "the retrieved laws don't directly",
    "the retrieved laws do not directly",
    "based on the laws provided in the context",
)

_REFUSAL_MARKERS_UR: tuple[str, ...] = (
    "مجھے کافی معلومات نہیں",
    "کافی معلومات دستیاب نہیں",
    "میں جواب نہیں دے سکتا",
    "سیاق میں موجود نہیں",
    "دستاویزات میں نہیں",
    "مجھے معلوم نہیں",
)


def _looks_like_refusal(reply: str) -> bool:
    if not reply:
        return True
    low = reply.lower()
    if any(m in low for m in _REFUSAL_MARKERS_EN):
        return True
    if any(m in reply for m in _REFUSAL_MARKERS_UR):
        return True
    return False


def _count_inference_hedges(reply: str) -> int:
    """Count how many inference/hedging phrases appear in the reply."""
    low   = reply.lower()
    count = sum(1 for m in _INFERENCE_MARKERS_EN if m in low)
    count += sum(1 for m in _INFERENCE_MARKERS_UR if m in reply)
    return count


def _score_confidence(
    chunks:       list[dict],
    reply:        str = "",
    case_context: Optional[dict] = None,
) -> str:
    """
    v5 Multi-factor confidence scoring:

    F1 — Average retrieval score (primary signal)
         ≥ 0.72 → starts "high"; 0.52–0.72 → "medium"; < 0.52 → "low"
    F2 — Domain relevance: are the top-2 chunks from the right legal domain?
         Cross-domain mismatch → penalise one tier
    F3 — Inference level: ≥2 hedging phrases in the reply → penalise one tier
    F4 — Refusal detection: any refusal marker → force "low"
    """
    if not chunks:
        return "low"

    # F4: refusal check (highest priority)
    if reply and _looks_like_refusal(reply):
        return "low"

    # F1: average retrieval score
    scores = [float(c.get("score", 0.0)) for c in chunks]
    avg    = sum(scores) / len(scores)

    if avg >= 0.72:
        tier = "high"
    elif avg >= 0.52:
        tier = "medium"
    else:
        tier = "low"

    # F2: domain relevance penalty
    # Check if the top 2 chunks are from the right domain
    if case_context and tier != "low":
        case_category = (case_context.get("category") or "").strip()
        if case_category:
            top_chunks = chunks[:2]
            primary_laws = _DOMAIN_PRIMARY_LAWS.get(case_category, [])
            if primary_laws:
                top_in_domain = sum(
                    1 for c in top_chunks
                    if any(p in c.get("law_name", "").lower() for p in primary_laws)
                )
                if top_in_domain == 0:
                    # Top chunks are all from the wrong domain
                    tier = "medium" if tier == "high" else "low"
                    logger.debug("Confidence penalised (F2): top chunks cross-domain for %s",
                                 case_category)

    # F3: inference hedge penalty
    if reply and tier != "low":
        hedge_count = _count_inference_hedges(reply)
        if hedge_count >= 2:
            tier = "medium" if tier == "high" else "low"
            logger.debug("Confidence penalised (F3): %d inference hedges found", hedge_count)

    return tier