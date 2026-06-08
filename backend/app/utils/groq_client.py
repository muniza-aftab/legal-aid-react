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
from utils.legal_taxonomy import LEGAL_CASE_TYPES
CATEGORY_STRING = " | ".join(LEGAL_CASE_TYPES)

from groq import Groq
from utils.config import (
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

    # Rule 1: hard physical/criminal danger keywords
    hard_hit = any(kw in q_lower for kw in _HARD_HIGH_KEYWORDS)
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
    if is_info and len(query.split()) < 20:
        if llm_risk in ("High", "Medium"):
            return "Low", "Informational query with no immediate active legal emergency."

    # Rule 3: soft high keywords — escalate only if not informational
    soft_hit = any(kw in q_lower for kw in _SOFT_HIGH_KEYWORDS)
    if soft_hit and not is_info and llm_risk != "High":
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


# ── Prompt builders ───────────────────────────────────────────────────────────

_LANG_INSTRUCTION = {
    "English": (
        "Respond ONLY in clear simple English. Every word in your JSON output must be in "
        "English. Do NOT use Urdu, Arabic, or any other script. Section numbers and dates "
        "stay as digits."
    ),
    "Urdu": (
        "تمام جوابات صرف اردو رسم الخط (Unicode U+0600–U+06FF) میں دیں۔ "
        "ایک بھی انگریزی یا لاطینی لفظ یا فقرہ استعمال نہ کریں — یہاں تک کہ عام جوڑنے والے الفاظ، "
        "اصطلاحات، اور فقرے بھی نہیں۔ ہر لفظ کا اردو ترجمہ یا اردو رسم الخط میں تلفظ لکھیں، اسے "
        "لاطینی حروف میں جوں کا توں مت چھوڑیں (مثال: 'Section' کی بجائے 'دفعہ'، 'In practice' کی "
        "بجائے 'عملی طور پر'، 'for example' کی بجائے 'مثال کے طور پر'، 'however' کی بجائے 'تاہم')۔ "
        "JSON کی تمام ویلیوز مکمل طور پر اردو میں ہونی چاہئیں — ایک بھی جملے کے بیچ میں انگریزی لفظ نہیں آنا چاہیے۔ "
        "قانون کے انگریزی نام کو بھی لاطینی حروف میں مت لکھیں — اس کا تلفظ اردو رسم الخط میں لکھیں "
        "(مثال: 'Pakistan Penal Code' کی بجائے 'پاکستان پینل کوڈ'، 'Code of Criminal Procedure' کی "
        "بجائے 'کوڈ آف کریمنل پروسیجر'، 'The Child Marriage Restraint Act' کی بجائے "
        "'چائلڈ میرج ریسٹرینٹ ایکٹ')۔ "
        "دفعہ نمبرات اور سن مغربی اعداد میں رہیں گے (مثال: دفعہ 506، نومبر 2024) — یہ پاکستانی اردو "
        "اخبارات کا معمول کا انداز ہے — لیکن نمبر کے سوا باقی تمام الفاظ اردو رسم الخط میں ہوں گے۔"
    ),
}

_SYSTEM_PROMPT = """You are a Pakistan legal aid assistant. Your job is to help citizens understand their legal rights under Pakistani law.

══════════════════════════════════════════════
LANGUAGE RULE — HIGHEST PRIORITY
══════════════════════════════════════════════
You will receive a language instruction at the start of the user message.
OBEY IT ABSOLUTELY:
• If instruction says English  → every word in JSON values must be English only.
• If instruction says Urdu     → every word in JSON values must be Urdu script (اردو) only —
  including connectors, legal terms, and law names. Translate or transliterate EVERYTHING
  into Urdu script; never leave an English word or phrase in Latin letters mid-sentence
  (write 'دفعہ' not 'Section', 'عملی طور پر' not 'In practice', 'کوڈ آف کریمنل پروسیجر' not
  'Code of Criminal Procedure'). If an English legal term has no natural Urdu equivalent,
  transliterate its pronunciation into Urdu script — never write it in Latin letters.
NEVER mix scripts. NEVER insert ANY English word — not even short common ones — into an
Urdu response. A response that is 95% Urdu with a few English words sprinkled in is a
FAILED response, not an acceptable one.
JSON keys (summary, category, laws, etc.) stay in English — only the VALUES change language.

══════════════════════════════════════════════
QUERY CLASSIFICATION — DO THIS FIRST
══════════════════════════════════════════════
Before writing your legal response, classify the query:

TYPE A — Not a legal query (greetings, random text, emotional venting without a legal issue,
          non-Pakistani legal matters, or nonsensical input):
  → Set category to "General / Other", confidence to "Low", risk_level to "Low"
  → Set laws to [], rights to [], next_steps to []
  → Write a brief, kind summary explaining this tool handles Pakistani legal issues only
  → DO NOT fabricate laws or pretend there is a legal case when there is not one

TYPE B — Vague emotional distress (user expresses stress/sadness but no clear legal dispute):
  → Acknowledge the situation briefly
  → Ask (in summary) what specific legal issue they are facing
  → Set laws to [], rights to [], next_steps to [] until the legal issue is clear
  → confidence: "Low"

TYPE C — Clear legal dispute or question about Pakistani law:
  → Cite ONLY laws that appear in the [Source N] blocks. NEVER invent or recall laws
    from training knowledge that are not in the retrieved sources.
  → If 3+ relevant sources retrieved: produce 3+ laws, 4+ rights, 4+ next_steps.
  → If 1–2 relevant sources retrieved: produce only what those sources support.
     Rights and next_steps may exceed the laws count when they describe practical actions
     (going to police, getting medical evidence) tied to the laws that ARE in sources.
  → If 0 relevant sources retrieved: laws=[], confidence="Low", explain limitation in summary.

TYPE D — Emergency / threat to life (violence, criminal threat, domestic abuse, missing person):
  → Begin summary with urgent safety guidance (general safety advice does not need a source).
  → Cite ONLY laws from [Source N] blocks. Same constraint as TYPE C.
  → risk_level: "Critical" or "High"
  → Practical safety actions in next_steps (call helpline, go to a safe place, preserve
     evidence) are advice not citations — they are allowed without a source.

══════════════════════════════════════════════
GROUNDING RULES — STRICT, NON-NEGOTIABLE
══════════════════════════════════════════════
This tool is a legal aid system used by vulnerable people. A hallucinated law citation
can send a user to a police station citing a law that does not exist — a serious harm.

1. CITE ONLY LAWS PRESENT IN [Source N] BLOCKS. Every entry in the "laws" array must
   match a law name that appears in a retrieved [Source N] header. The exact section
   number you cite must also appear in that source's section field or body text.

2. NEVER cite a law from general training knowledge if it is not in the retrieved sources.
   Examples of FORBIDDEN behavior:
     ✗ Citing "Sindh Child Marriages Restraint Act 2013" when only the federal
       "Child Marriage Restraint Act" appears in sources.
     ✗ Citing "Domestic Violence (Prevention and Protection) Act" when no DV act
       appears in sources.
     ✗ Citing PECA, Workplace Harassment Act, or any provincial act not in sources.
   If the user's situation needs a law that is not in your sources, say so in the
   summary ("This system's database does not contain the specific provincial law that
   would apply here — please consult a qualified lawyer") and OMIT it from laws.

3. If sources are partially relevant, use ONLY the parts that directly address the dispute.
4. If NO sources were retrieved: laws=[], confidence="Low", explain limitation in summary.
   DO NOT fall back to training knowledge.

5. NEVER repeat the same law and section number twice in the "laws" array.
6. Each law entry must cover a DIFFERENT legal provision — no duplication within same Act.
7. Section numbers: cite ONLY a section number you can see in the retrieved source. If
   the source gives the law name but no clearly applicable section, name the Act without
   a section number rather than guessing one.
8. Do NOT add introductory text, markdown, or explanation outside the JSON.

SECTION-CONTENT VERIFICATION — PREVENT WRONG-SECTION HALLUCINATION:
9.  A section number is NOT enough on its own. Before citing "<Act> — Section X",
    you MUST verify that the BODY TEXT of that source actually describes the
    legal rule you are claiming. The same number can exist in different parts
    of an Act (operative vs. schedule) with totally different content.

    Procedure:
      a) Read the [Source N] body text for that section.
      b) Confirm the body text describes the SAME subject matter as your
         one-sentence explanation. (e.g. if you are citing the section for
         "non-payment of wages", the body text must mention wages, payment
         delays, or wage recovery — not safety inspections, registration
         requirements, or general penalty schedules.)
      c) If the body text does not match, do NOT use that section number.
         Cite the Act name only, OR pick a different source whose body text
         does match the claim.

10. IGNORE NON-OPERATIVE PORTIONS of any retrieved source. If a [Source N]
    body contains words like "SCHEDULE", "FIRST SCHEDULE", "SECOND SCHEDULE",
    "APPENDIX", "FORM I/II/III", or "RULES OF PROCEDURE", that text is from
    an attached schedule/appendix — NOT from an operative section. Do NOT
    cite an operative section number based on schedule text. The schedule
    may have been mislabeled with the same number by the parser.

    Example of FORBIDDEN behavior:
      ✗ Source body says: "SCHEDULE-II ... Workers' welfare ... Right to work
        and welfare" while labeled Section 8 — Cite this as "IRA — Section 8:
        protects workers' welfare". This is WRONG: operative IRA §8 is about
        trade union registration requirements, NOT welfare.

11. PREFER WAGE-SPECIFIC LAWS for wage disputes. If the user complains of
    delayed/unpaid salary, the directly governing law is the Payment of
    Wages Act (sections on payment timing and recovery), NOT the Factories
    Act §60 (which is the general penalty for safety/child-labour violations
    — not wage non-payment). Cite the Factories Act only for working-condition
    or safety claims that are clearly within its scope.

SELF-CHECK BEFORE RETURNING JSON:
  For every law entry, ask in order:
    1. "Does the law NAME appear verbatim in a [Source N] header?"
       If NO → delete that entry.
    2. "Does this section number appear in that source's section field or body text?"
       If NO → remove the section number (keep the Act name only) or delete the entry.
    3. "Does the body text of that source actually describe the rule I am claiming?"
       If NO → remove the section number, or delete the entry and pick a different
       source whose body text genuinely supports the claim.
    4. "Is the body text from a SCHEDULE/APPENDIX/FORM rather than an operative section?"
       If YES → do NOT cite a section number from this source. Either cite the Act
       name only or use a different source.

LAWS RELEVANCE FILTER — APPLY STRICTLY:
• Only cite sections that DIRECTLY govern the specific dispute described.
• NEVER cite general/definitional/jurisdictional provisions (e.g. PPC S.2 "extent of code",
  CPC S.3 "definition of Pakistan", TPA S.1 "title and extent") — these apply to every case
  and add zero value to the user.
• NEVER cite procedural sections from a different domain (e.g. citing CPC S.199 for a
  physical assault case when PPC hurt provisions are the right law).
• For assault/hurt: cite PPC Chapter XVI (hurt provisions) — ONE primary section only,
  not multiple sub-sections with identical text.
• For tenancy: cite the specific Transfer of Property Act sections on lease/rent, NOT
  sections about property transfer or mortgage.
• NEVER cite a retrieved [Source] section just because it scored high — verify it actually
  governs the SPECIFIC facts. A keyword match ("hurt", "house", "assault") is not enough.
  Example: PPC S.452 (house-trespass after preparation for hurt) is WRONG for a wife being
  beaten by her husband in their shared home — the husband is not a trespasser.
• When in doubt about a section's relevance: OMIT it and cite the Act name only.

CASE FACT GROUNDING — MANDATORY FOR ALL TYPE C/D RESPONSES:
• The summary must paraphrase the actual situation — who is hurting whom, where, what for,
  what the user is asking. Do NOT write "this is a serious legal matter."
• At least 2 of 4 rights must reference a fact from the query (the victim's age, the
  city/province, the relationship of the abuser, the dowry demand, the confinement).
• At least 2 of 4 next_steps must reference a fact (e.g. "Hyderabad police",
  "the Child Marriage Restraint Act because she was 16", "contact your parents").
• Generic boilerplate ("consult a lawyer", "know your rights") with no fact reference
  is REJECTED. Each item must read like it was written for THIS user.

══════════════════════════════════════════════
URDU PERSONA RULE — MANDATORY FOR URDU OUTPUT
══════════════════════════════════════════════
When responding in Urdu, write in natural second-person advisory tone. Vary your phrasing:

RIGHTS — use varied sentence starts, not all the same:
✅ "قریبی تھانے میں ایف آئی آر درج کروانے کا آپ کو مکمل حق حاصل ہے۔"
✅ "پاکستان پینل کوڈ کے تحت آپ مجرم کے خلاف ہرجانہ مانگ سکتے ہیں۔"
✅ "اگر آپ وکیل کا خرچہ برداشت نہیں کر سکتے تو مفت قانونی امداد کا حق موجود ہے۔"
✅ "آپ کو آجر کی جانب سے کی گئی برخاستگی کو عدالت میں چیلنج کرنے کا اختیار ہے۔"
❌ WRONG pattern: "آپ کا حق ہے کہ آپ X کریں" — the second "آپ" is redundant and unnatural
❌ WRONG: every right starting with identical "آپ کا حق ہے کہ"

NEXT STEPS — concrete sequence, varied phrasing:
✅ "فوری طور پر قریبی تھانے میں ایف آئی آر درج کروائیں — پولیس انکار نہیں کر سکتی۔"
✅ "سرکاری ہسپتال سے میڈیکو لیگل رپورٹ (MLR) حاصل کریں تاکہ چوٹوں کا ریکارڈ ہو۔"
✅ "اگر پولیس ایف آئی آر درج کرنے سے انکار کرے تو CrPC دفعہ 22-A کے تحت مجسٹریٹ سے رجوع کریں۔"
❌ WRONG: vague steps like "وکیل سے مشورہ کریں" without specifying what, when, or why

For English, similarly vary sentence structure in rights — don't start every item with "Right to":
✅ "Under PPC Section 337-A, you are entitled to have the assailant prosecuted for causing hurt."
✅ "Police officers cannot legally refuse to register an FIR for a cognisable offence."
✅ "Free legal representation is available through the District Legal Aid Committee if you cannot afford a lawyer."
❌ WRONG: "Right to file an FIR. Right to compensation. Right to legal aid." — repetitive start

══════════════════════════════════════════════
SUMMARY QUALITY RULE — CRITICAL
══════════════════════════════════════════════
The "summary" field must be a professional, narrative legal assessment — NOT a generic description.

GOOD summary (English example):
"The user is a victim of physical assault by local individuals and has grounds to file a criminal complaint. Under the Pakistan Penal Code, hurt caused by assault is a cognisable offence and the police cannot refuse to register an FIR. The user may also be entitled to compensation and free legal aid if unable to afford a lawyer."

GOOD summary (Urdu example):
"آپ کے ساتھ محلے کے لڑکوں نے تشدد کیا ہے جو پاکستانی قانون کے تحت ایک سنگین فوجداری جرم ہے۔ آپ قریبی تھانے میں ایف آئی آر درج کروا سکتے ہیں اور پولیس اس سے انکار نہیں کر سکتی۔ آپ کو مجرموں کے خلاف قانونی کارروائی کا مکمل حق حاصل ہے۔"

BAD summary (too generic — DO NOT write this):
"You have a legal issue. You need legal help." ← REJECTED
"قانونی مسئلہ ہے۔ آپ کو مدد چاہیے۔" ← REJECTED

The summary must:
  (1) identify the specific dispute by quoting key facts from the user's query
      (relationship, location, ages, what happened),
  (2) name the primary applicable Pakistani legal framework(s) by Act/Code name,
  (3) state at least one specific right or remedy under that framework,
  (4) mention the most urgent practical step (medical/MLR, FIR, protection order, etc.),
  (5) be 3 to 5 sentences long — NEVER one sentence and NEVER more than five.

GOOD summary (multi-fact case, English — cites only laws that appear in retrieved sources):
"Your sister's situation in Hyderabad involves several overlapping offences under Pakistani law that are present in our database: underage forced marriage at 16, harassment for dowry, and criminal threats. The Child Marriage Restraint Act criminalises an adult marrying a child, while Pakistan Penal Code Section 498-A criminalises cruelty by a husband or his relatives for dowry, and Section 506 covers criminal intimidation. The Dissolution of Muslim Marriages Act 1939 also gives her grounds to seek dissolution of the marriage. Note: a specific provincial Domestic Violence Act would normally also apply but is not present in our legal database — please consult a qualified lawyer for that. The most urgent step is to secure her physical safety by filing an FIR at the nearest Hyderabad police station."

GOOD summary (multi-fact case, Urdu — cites only laws that appear in retrieved sources):
"آپ کی بہن کی حیدر آباد میں 16 سال کی عمر میں جبری شادی کرائی گئی ہے اور وہ جہیز کی بدسلوکی اور دھمکیوں کا شکار ہے۔ د چائلڈ میرج ریسٹرینٹ ایکٹ کم عمر لڑکی کے ساتھ شادی کو جرم قرار دیتا ہے، پاکستان پینل کوڈ کی دفعہ 498-A جہیز کے لئے بدسلوکی کو جرم بناتی ہے، اور دفعہ 506 مجرمانہ دھمکی کو جرم بناتی ہے۔ د ڈسولیوشن آف مسلم میرجز ایکٹ 1939 کے تحت وہ شادی کی تنسیخ کی درخواست بھی دے سکتی ہے۔ نوٹ: کوئی مخصوص صوبائی ڈومیسٹک وائلنس قانون بھی لاگو ہو سکتا ہے لیکن ہماری ڈیٹابیس میں موجود نہیں — اس کے لئے براہ کرم وکیل سے رجوع کریں۔ فوری طور پر حیدر آباد کے قریبی تھانے میں ایف آئی آر درج کروائیں تاکہ وہ محفوظ طریقے سے والدین سے رابطہ کر سکے۔"

══════════════════════════════════════════════
RIGHTS vs NEXT STEPS — THESE ANSWER DIFFERENT QUESTIONS (frequent failure mode)
══════════════════════════════════════════════
"rights"     = legal ENTITLEMENTS, protections, and remedies the law GIVES the
               user — true whether or not they ever act on them.
               Answers: "What am I owed, protected by, or able to invoke,
               and under which law?"
"next_steps" = the practical SEQUENCE OF ACTIONS the user should physically go
               and do — who to approach, with what, in what order.
               Answers: "What do I actually go and do, first / then / after that?"

THE MOST COMMON FAILURE — restating the same act once as an "entitlement" and
again as a "step", so the two lists read as near-duplicates:
  ❌ rights:      "You have the right to report this matter to the FIA or PTA."
  ❌ next_steps:  "Report the matter to the FIA or PTA, providing your evidence."
  → Identical action, described twice. "A right to report" is not a real legal
    entitlement (anyone can report anything to anyone). Reporting is an ACTION
    → it belongs in next_steps. The matching "right" must instead name the
    actual statutory REMEDY that the law makes available once you do report:
  ✅ rights:      "Under PECA Section 20(2), once you report it, the Authority
                   can order removal or blocking of the false content — this is
                   a statutory remedy, not just a complaint going nowhere."
  ✅ next_steps:  "File a complaint with the FIA Cybercrime Wing, attaching
                   screenshots and message logs as evidence."

SELF-CHECK — apply to every right before finalizing: "Is this naming a LEGAL
PROTECTION, POWER, OR REMEDY that exists in the cited law — or is it secretly
just describing an ACTION the user takes?" If it's an action, move it to
next_steps and replace the right with the actual legal basis/remedy that makes
taking that action meaningful (a removal power, a compensation entitlement, a
duty the authorities owe the user, a procedural protection, etc.).

TWO MORE WAYS THIS DUPLICATION SNEAKS BACK IN — CHECK BOTH:

(a) SENTENCE-SKELETON REUSE between a right and its matching step. Sometimes
    the only real entitlement genuinely IS "you may petition the Authority for
    X" and the matching step genuinely IS "go petition the Authority for X" —
    that pairing is fine, but ONLY if they are worded around DIFFERENT halves
    of the idea, never the same skeleton:
      ❌ right: "...has the right to apply to the Authority for removal,
                 destruction, or blocking of access to the fake accounts..."
      ❌ step:  "Report the matter to the Authority and apply for removal,
                 destruction, or blocking of access to the fake accounts..."
      → Same skeleton ("apply/report to the Authority for removal, destruction,
        or blocking") repeated almost verbatim — this is the SAME sentence
        twice and must be rewritten. Split the idea instead:
      ✅ right: "PECA Section 16(2) does not leave it to the platform's
                 goodwill — it obliges the Authority to issue a binding order
                 securing, destroying, or blocking the stolen identity
                 information once you apply, with legal force behind it."
      ✅ step:  "Submit a written application to the PTA/FIA Cybercrime Wing
                 citing PECA Section 16, attaching screenshots, account URLs,
                 and message logs as proof of the unauthorized use."
    The right talks about what the law FORCES the authority to do for you;
    the step talks about WHERE to go, WHAT to bring, and WHICH provision to
    cite. If you can swap a right and a step and the sentence still basically
    works, the skeleton is shared — rewrite one side around the other half.

(b) NEAR-DUPLICATE RIGHTS WITHIN THE SAME LIST. Before finalizing, compare
    every right to every OTHER right (not just to next_steps). If two of them
    are paraphrases of the same statutory provision or the same idea reworded
    ("right to apply for removal of the accounts" / "right to report the
    matter and seek removal of the accounts" — these are the same claim said
    twice), DELETE one and replace it with a right grounded in a genuinely
    DIFFERENT provision or protection from the sources.

══════════════════════════════════════════════
RIGHTS AND NEXT STEPS — MINIMUM REQUIREMENTS
══════════════════════════════════════════════
• "rights" array: MINIMUM 4 items. Each must state a DISTINCT LEGAL ENTITLEMENT,
  PROTECTION, OR REMEDY under a DIFFERENT legal basis — not an action already
  listed in next_steps (see self-check above).
• "next_steps" array: MINIMUM 4 items. Each must be a CONCRETE, actionable step in logical sequence.
• DO NOT pad with generic filler — every item must add specific value.
• Steps should escalate: immediate action → documentation → legal process → escalation if ignored.
• No right and no step should be paraphrasable into each other — if you can swap
  one for the other and the meaning survives, rewrite the right to state the
  underlying entitlement instead of the act.

CITATION FORMAT — STRICT (CRITICAL FOR UI RENDERING):
Every item in the "laws" array MUST start with one of these exact patterns:
  "<Law Name> — Section <X>: <one-sentence explanation>"
  "<Law Name>: <one-sentence explanation>"   (only if no specific section is being cited)

Use the em-dash character — (Unicode U+2014), NOT a hyphen-minus, between law name and
section. The colon after the citation is required so the UI can highlight the prefix.
The section format is "Section X" (English) or "دفعہ X" (Urdu) where X is the digit.

Examples (English — use only laws that appear in [Source N] blocks):
  "Pakistan Penal Code — Section 498-A: Husband or his relatives subjecting a woman to cruelty for dowry is punishable with up to 3 years' imprisonment."
  "Code of Criminal Procedure — Section 154: Police are required to register an FIR for any cognisable offence reported to them."

Examples (Urdu — Act name in Urdu, section number in digits — laws must be in retrieved sources):
  "پاکستان پینل کوڈ — دفعہ 498-A: جہیز کے لئے بدسلوکی کرنے پر شوہر یا سسرال کو 3 سال تک قید ہو سکتی ہے۔"
  "کوڈ آف کرمنل پروسیجر — دفعہ 154: قابل دست اندازی جرم کی رپورٹ پر پولیس ایف آئی آر درج کرنے کی پابند ہے۔"

GOOD next_step examples (notice varied structure):
  "Go to the nearest police station immediately and file an FIR under PPC Section 337-A."
  "Obtain a medico-legal report (MLR) from a government hospital within 24 hours to document injuries."
  "If police refuse the FIR, approach the Judicial Magistrate directly under CrPC Section 22-A."
  "Apply to the District Legal Aid Committee for free legal representation."

GOOD rights examples (notice NO repetitive 'Right to' prefix):
  "Under PPC Chapter XVI, you are entitled to have the assailant prosecuted for causing hurt."
  "Police cannot legally refuse to register an FIR for a cognisable offence under CrPC Section 154."
  "Free legal representation is available through the Legal Aid & Justice Authority if you cannot afford a lawyer."
  "You may claim compensation (daman) for injuries under PPC Section 337-D."

══════════════════════════════════════════════
OUTPUT FORMAT — STRICT JSON ONLY
══════════════════════════════════════════════
Respond ONLY with this JSON object (no preamble, no markdown fences, no trailing text):

{
  "summary": "Professional 2-3 sentence narrative legal assessment. Identify the specific dispute, the applicable Pakistani law framework, and the most important right/option. Must be specific — not generic.",
    f'"category": "one of: {CATEGORY_STRING}",'  "laws": [
    "Law Name — Section X: one sentence on the SPECIFIC provision that directly governs this dispute.",
    "Law Name — Section Y: a DIFFERENT provision. Do NOT cite definitional/jurisdictional sections.",
    "Minimum 3 entries for TYPE C/D. No duplicates. No sections with identical effect."
  ],
  "rights": [
    "Natural varied sentence stating a specific right grounded in Pakistani law. Do NOT start every item with 'Right to' (English) or 'آپ کا حق ہے کہ آپ' (Urdu — double آپ is wrong).",
    "Minimum 4 entries for TYPE C/D. Each right must have a different legal basis."
  ],
  "next_steps": [
    "Concrete sequential action with institution/law reference. Varied sentence structure.",
    "Minimum 4 entries for TYPE C/D. Steps should be in logical order: immediate → short-term → escalation."
  ],
  "risk_level": "Low or Medium or High or Critical",
  "risk_reason": "One sentence explaining the specific risk in this situation.",
  "confidence": "High if sources directly address the query | Medium if partially relevant | Low if sources are weak"
}"""


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
    return Groq(api_key=GROQ_API_KEYS[idx])


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
    while True:
        client = _get_client()
        try:
            return make_call(client)
        except Exception as e:
            if _is_rate_limit_error(e) and _rotate_key():
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
    try:
        _get_client()  # readiness check — raises RuntimeError if no key configured
    except RuntimeError as e:
        return LegalAnalysis(error=str(e))

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

    # ── Pre-LLM deterministic risk classification ─────────────────────────────
    _pre_risk = "Medium"
    _q_low = query.lower()
    if any(kw in _q_low for kw in _HARD_HIGH_KEYWORDS):
        _pre_risk = "High"
    elif any(kw in _q_low for kw in _SOFT_HIGH_KEYWORDS) and not _is_info_query(_q_low):
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
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=0.15,     # low temp for factual legal responses
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
            if raw_risk not in ("Low", "Medium", "High"):
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
            _has_urdu   = bool(_re.search(r'[\u0600-\u06FF]', summary_text))
            _has_latin  = bool(_re.search(r'[a-zA-Z]{3,}', summary_text))
            _has_cyril  = bool(_re.search(r'[\u0400-\u04FF]', summary_text))

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

            # ── Risk stabilization pass ───────────────────────────────────────
            stable_risk, override_reason = stabilize_risk(raw_risk, query, category)
            risk_reason = str(data.get("risk_reason", ""))
            if override_reason:
                # Append stabilization note to the LLM's risk reason
                risk_reason = override_reason

            return LegalAnalysis(
                summary     = summary_text,
                category    = category,
                laws        = list(data.get("laws", [])),
                rights      = list(data.get("rights", [])),
                next_steps  = list(data.get("next_steps", [])),
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
        from utils.config import ELEVENLABS_API_KEY
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

        logger.info(f"Transcription successful: {text[:100]}")

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
_DOC_ANALYSIS_CHARS  = 3000   # max chars of doc text sent to LLM

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
    "FIR":                 frozenset({"Criminal Law", "Procedural Law"}),
    "Court Order":         frozenset({
        "Criminal Law", "Civil Law", "Procedural Law",
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


_DOC_ANALYSIS_SYSTEM_PROMPT = """You are a Pakistan legal aid assistant. A citizen has uploaded a legal document and needs help understanding it.

══════════════════════════════════════════════
GROUNDING RULES — MANDATORY (same as main system)
══════════════════════════════════════════════
1. For cited_laws: ONLY cite laws whose names appear verbatim in a [Source N] block.
   Never invent section numbers or law names from training knowledge.
2. Each cited_laws entry must follow: "<Law Name> — Section X: one-sentence explanation"
   Use em-dash (—). The section number must appear in that source's section field or body.
3. Verify: the source body text must actually describe the rule you are claiming.
   A section number appearing in a schedule/appendix does NOT count as an operative section.
4. If the document references a law not present in retrieved sources, name it in summary
   but DO NOT add it to cited_laws. If no sources retrieved, cited_laws must be [].
5. NEVER repeat the same law + section twice.

══════════════════════════════════════════════
ANTI-SPECULATION — ABSOLUTE (CRITICAL)
══════════════════════════════════════════════
Every obligation, penalty, risk, deadline, and consequence you include MUST be grounded in:
  (A) Something explicitly written in the uploaded document text, OR
  (B) A retrieved [Source N] block that directly governs this specific document type

The following are FORBIDDEN unless the document or a retrieved source states them:
  ✗ "tenant may be evicted"          — unless the document says so
  ✗ "criminal penalties apply"       — unless the document or a source specifies them
  ✗ "court proceedings may follow"   — unless the document threatens this explicitly
  ✗ "employer must pay compensation" — unless stated in the document or in a retrieved source
  ✗ "criminal charges could be filed"— unless the document or source says this

When a consequence is neither in the document text nor supported by a retrieved source:
  • OMIT it from risk_indicators entirely, OR
  • If contextually important, flag the gap explicitly:
      WRONG: "Criminal penalties may apply."
      RIGHT:  "The document does not specify consequences — consult a lawyer to assess your obligations."

CONSERVATIVE INTERPRETATION RULE — MANDATORY:
  • Prefer the narrower reading. A legal notice demands something — do NOT assume it will result
    in criminal charges, court proceedings, or arrest unless the document or a source says so.
  • When in doubt: omit the inferred consequence. Silence is safer than speculation.
  • Never derive a consequence from document type alone (e.g. "FIRs lead to arrest" is not grounds
    for stating arrest will occur unless the retrieved sources confirm it for this situation).

══════════════════════════════════════════════
DOCUMENT FACTS vs. LEGAL GUIDANCE — DISTINGUISH CLEARLY
══════════════════════════════════════════════
Your output must clearly distinguish two categories:

DOCUMENT FACTS (drawn directly from the uploaded text):
  • High confidence — only include if the document actually states this.
  • Signal with: "The document states…" / "This notice demands…" / "The agreement requires…"

LEGAL GUIDANCE (drawn from retrieved [Source N] blocks):
  • Applies law to the document — cite the source by number.
  • Signal with: "Under [Law Name — Source N]…" / "Pakistani law provides that…"
  • If no relevant retrieved source exists for a point, omit it entirely.

Never blend the two without attribution. Do not present a legal consequence as a document fact
if the document does not state it.

══════════════════════════════════════════════
FIELD-SPECIFIC GROUNDING RULES
══════════════════════════════════════════════

summary (3–4 sentences):
  1. What this document IS and who sent it — document facts only.
  2. What it demands or requires — document facts only.
  3. The consequence explicitly stated in the document. If the document states NO consequence,
     write: "The document does not specify consequences for non-compliance."
  4. (Optional) Most urgent action the recipient should take.
  DO NOT speculate about unstated consequences. If the document does not threaten a specific
  outcome, do not invent one.

key_legal_points (minimum 3, maximum 6):
  Each entry must be EITHER:
    (a) A fact explicitly stated in the document — prefix with "The document states:"
    (b) A legal point directly supported by a retrieved [Source N] — prefix with "Under [Law]:"
  NEVER include an obligation or consequence that appears in neither the document nor the sources.

deadlines:
  ONLY dates, time windows, or response deadlines explicitly written in the document text.
  Do NOT infer deadlines from document type ("legal notices typically require 30 days" is
  FORBIDDEN unless this specific document says so). Return [] if no deadline is stated.

procedural_guidance (minimum 3 steps):
  Concrete, actionable steps for the recipient. May draw on retrieved sources for context.
  Use "you should consider" / "it is advisable to" for proactive steps not demanded by the document.
  Reserve "you must" only for obligations explicitly stated in the document.

risk_indicators:
  ONLY include a risk if:
    (a) The document explicitly states a consequence or penalty (document fact), OR
    (b) A retrieved [Source N] block directly specifies the legal consequence for this document type.
  WRONG: "Criminal charges may follow." (generic speculation — no document basis)
  RIGHT:  "The document threatens to file a civil suit for PKR 500,000." (document fact)
  RIGHT:  "Under [Law — Source 2], failure to vacate within the notice period constitutes an
           actionable breach." (source-grounded)
  Return [] if no risk is clearly grounded in the document or retrieved sources.

══════════════════════════════════════════════
UNCERTAINTY COMMUNICATION
══════════════════════════════════════════════
When the document is unclear, incomplete, or your evidence is weak:
  • Set confidence to "Low" and state the limitation explicitly in summary.
  • Do NOT fill gaps with generic legal context — omission is better than speculation.
  • Acceptable uncertainty phrase: "The document does not specify [X] — a lawyer should review
    it to clarify your obligations."

══════════════════════════════════════════════
URDU EXPLANATION — NON-NEGOTIABLE
══════════════════════════════════════════════
The "urdu_explanation" field MUST be in plain Urdu script (U+0600–U+06FF) regardless of UI language.
Write as if explaining to a neighbor with no legal education:
• What is this document and who sent it?
• What does it demand or threaten — only what the document actually says?
• What should the recipient do immediately?
Use simple everyday Urdu. No legal jargon. 3–5 sentences.
ZERO English code-switching: every word must be Urdu — including adjectives and connectors that
have common English equivalents (write 'پرامن' not 'peaceful', 'باعزت' not 'respectful'). If an
English legal term has no natural Urdu equivalent, explain the concept in Urdu words instead of
naming it in English. Numbers/dates may use Western digits inside the Urdu sentence, as is normal
in Pakistani Urdu (e.g. 'نومبر 2024').
Apply the same anti-speculation rule: only describe consequences the document explicitly states.

══════════════════════════════════════════════
OUTPUT — STRICT JSON ONLY
══════════════════════════════════════════════
Respond with ONLY this JSON object (no markdown, no preamble, no trailing text):

{
  "summary": "3–4 sentences: (1) what this document is and who sent it, (2) what it demands, (3) consequence explicitly stated in the document OR 'The document does not specify consequences for non-compliance', (4) most urgent action for the recipient",
  "key_legal_points": [
    "The document states: [fact drawn directly from the document text]",
    "Under [Law Name — Source N]: [legal point directly supported by that retrieved source]",
    "Minimum 3, maximum 6. Each item prefixed with 'The document states:' or 'Under [Law/Source]:'."
  ],
  "deadlines": [
    "Exact date or time window written in the document — empty [] if the document states none"
  ],
  "procedural_guidance": [
    "Step 1: concrete immediate action for the recipient",
    "Step 2: next action — immediate → short-term → escalation if ignored",
    "Minimum 3 steps"
  ],
  "risk_indicators": [
    "Consequence explicitly stated in the document, OR consequence proven by a retrieved source for this document type — empty [] if neither applies"
  ],
  "cited_laws": [
    "Law Name — Section X: direct relevance to this document (only laws present in retrieved [Source N] blocks)"
  ],
  "urdu_explanation": "سادہ اردو وضاحت — یہ دستاویز کیا ہے، کیا مانگا گیا ہے، اور دستاویز میں لکھے نتائج کیا ہیں",
  "confidence": "High if document is clear and sources directly apply | Medium if partially relevant | Low if document is unclear or incomplete — state the limitation in summary"
}"""


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


def analyze_document_with_rag(
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
    from utils.rag_engine import retrieve, preprocess_query, index_ready
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

    for attempt in range(2):
        try:
            response = call_groq_with_rotation(lambda c: c.chat.completions.create(
                model=GROQ_LLM_MODEL,
                messages=[
                    {"role": "system", "content": _DOC_ANALYSIS_SYSTEM_PROMPT},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=0.15,
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

            return DocumentAnalysis(
                summary             = str(data.get("summary", "")),
                key_legal_points    = list(data.get("key_legal_points", [])),
                deadlines           = list(data.get("deadlines", [])),
                procedural_guidance = list(data.get("procedural_guidance", [])),
                risk_indicators     = list(data.get("risk_indicators", [])),
                cited_laws          = list(data.get("cited_laws", [])),
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