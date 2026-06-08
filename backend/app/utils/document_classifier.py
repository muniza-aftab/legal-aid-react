"""
document_classifier.py — Rule-based document type classification for uploaded legal documents.

Classification pipeline:
  1. Rule-based scoring — regex patterns weighted by specificity (English + Urdu).
  2. Optional Groq LLM fallback — triggered when rule confidence < _LLM_THRESHOLD.

Document types:
  "Legal Notice" | "FIR" | "Court Order" | "Rent Agreement" |
  "Employment Contract" | "Unknown"

Isolation guarantee: no RAG, no DB, no existing query-analysis flow is modified.
The Groq client is imported only inside the LLM fallback function (dynamic import),
so this module never breaks if GROQ_API_KEY is absent.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Public constants ───────────────────────────────────────────────────────────

DOCUMENT_TYPES: list[str] = [
    "Legal Notice",
    "FIR",
    "Court Order",
    "Rent Agreement",
    "Employment Contract",
    "Unknown",
]

# Rule-based confidence below this value triggers the LLM fallback (if available)
_LLM_THRESHOLD = 0.40

# Only the first N characters of extracted text are scanned for performance.
# Document headers carry the most discriminating signals.
_SCAN_LIMIT = 3000


# ── Result dataclass ───────────────────────────────────────────────────────────

@dataclass
class ClassificationResult:
    """
    Output of classify_document().

    document_type:         canonical type string or "Unknown"
    confidence:            0.0 – 1.0 (higher = more certain)
    method:                "rule_based" | "llm" | "rule_based+llm_confirm"
    matched_rules:         human-readable names of matched rule patterns
    """
    document_type:  str
    confidence:     float
    method:         str
    matched_rules:  list = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# Rule table
# Each entry: (display_name, regex_pattern, weight)
# Weights 1–5: higher = more type-specific / less ambiguous.
# Patterns use re.IGNORECASE | re.UNICODE; Urdu patterns need no case flag.
# ═══════════════════════════════════════════════════════════════════════════════

_RULES: dict[str, list[tuple[str, str, float]]] = {

    "Legal Notice": [
        # English — title and explicit phrases
        ("title: legal notice",        r"\blegal\s+notice\b",                              5.0),
        ("demand notice",              r"\bdemand\s+notice\b",                             4.0),
        ("notice to vacate",           r"\bnotice\s+to\s+vacate\b",                        4.0),
        ("you are hereby notified",    r"\byou\s+are\s+hereby\s+notified\b",               4.0),
        ("notice is hereby given",     r"\bnotice\s+is\s+hereby\s+given\b",                4.0),
        ("through counsel",            r"\bthrough\s+(?:his\s+|her\s+|their\s+)?counsel\b", 2.5),
        ("days from receipt",          r"\d+\s+days?\s+(?:from|of|within)\s+receipt",      2.5),
        ("without prejudice",          r"\bwithout\s+prejudice\b",                         2.0),
        ("compliance required",        r"\b(?:strict\s+)?compliance\b",                    1.5),
        # Urdu
        ("اردو: قانونی نوٹس",         r"قانونی\s+نوٹس",                                   5.0),
        ("اردو: قانونی اطلاع",        r"قانونی\s+اطلاع",                                  4.0),
        ("اردو: نوٹس",               r"\bنوٹس\b",                                        2.0),
        ("اردو: مہلت",               r"\bمہلت\b",                                        1.5),
    ],

    "FIR": [
        # English
        ("title: FIR abbreviation",    r"\bF\.?I\.?R\.?\b",                                5.0),
        ("first information report",   r"\bfirst\s+information\s+report\b",                5.0),
        ("police station",             r"\bpolice\s+station\b",                            3.0),
        ("FIR / case number",          r"\b(?:fir|case)\s*no\.?\s*\d+",                   3.0),
        ("PPC/CrPC section",           r"\bsection\s+\d+[\w/]*\s*(?:ppc|crpc|mrda)?\b",   2.5),
        ("complainant",                r"\bcomplainant\b",                                 2.5),
        ("accused",                    r"\baccused\b",                                     2.0),
        ("FIR registered/filed",       r"\bfir\s+(?:registered|lodged|filed)\b",           3.0),
        ("challan",                    r"\bchallan\b",                                     2.0),
        ("SHO / IO",                   r"\b(?:sho|investigating\s+officer|i\.o\.)\b",      2.0),
        # Urdu
        ("اردو: ایف آئی آر",          r"ایف\s+آئی\s+آر",                                 5.0),
        ("اردو: مقدمہ",              r"\bمقدمہ\b",                                       3.0),
        ("اردو: تھانہ",             r"\bتھانہ\b",                                       3.0),
        ("اردو: درخواست گزار",      r"درخواست\s+گزار",                                 2.5),
        ("اردو: ملزم",              r"\bملزم\b",                                        2.0),
        ("اردو: پولیس",             r"\bپولیس\b",                                       2.0),
    ],

    "Court Order": [
        # English
        ("in the court of",            r"\bin\s+the\s+courts?\s+of\b",                     4.0),
        ("high court",                 r"\bhigh\s+court\b",                                3.5),
        ("supreme court",              r"\bsupreme\s+court\b",                             4.0),
        ("sessions court",             r"\bsessions?\s+court\b",                           3.5),
        ("district court",             r"\bdistrict\s+court\b",                            3.0),
        ("it is ordered",              r"\bit\s+is\s+(?:hereby\s+)?ordered\b",             4.5),
        ("the court directs",          r"\bthe\s+court\s+(?:directs?|orders?)\b",          4.0),
        ("judgment / decree",          r"\b(?:judgement?|decree|verdict)\b",               3.0),
        ("case / suit number",         r"\b(?:case|suit|civil\s+appeal|writ)\s*no\.?\s*\d+", 2.5),
        ("coram / before justice",     r"\b(?:coram|before\s*:?\s*(?:mr\.?\s*)?justice)\b", 3.5),
        ("order sheet",                r"\border\s+sheet\b",                               3.0),
        # Urdu
        ("اردو: عدالتی حکم",          r"عدالتی\s+حکم",                                   5.0),
        ("اردو: عدالت عالیہ",         r"عدالتِ?\s+عالیہ",                               4.0),
        ("اردو: سپریم کورٹ",          r"سپریم\s+کورٹ",                                   4.0),
        ("اردو: حکم",                r"\bحکم\b",                                        2.0),
        ("اردو: مدعی",               r"\bمدعی\b",                                       2.0),
    ],

    "Rent Agreement": [
        # English
        ("rent agreement",             r"\brent\s+agreement\b",                            5.0),
        ("lease agreement",            r"\blease\s+agreement\b",                           5.0),
        ("tenancy agreement",          r"\btenancy\s+agreement\b",                         5.0),
        ("landlord",                   r"\blandlord\b",                                    3.5),
        ("tenant",                     r"\btenant\b",                                      3.5),
        ("monthly rent",               r"\bmonthly\s+rent\b",                              3.5),
        ("rent of Rs.",                r"\brent\s+of\s+rs\.?\s*[\d,]+",                   3.0),
        ("security deposit",           r"\bsecurity\s+deposit\b",                          2.5),
        ("demised / premises",         r"\b(?:demised\s+)?premises\b",                    2.0),
        ("eviction",                   r"\beviction\b",                                    2.0),
        # Urdu
        ("اردو: کرایہ نامہ",          r"کرایہ\s+نامہ",                                   5.0),
        ("اردو: مالک مکان",           r"مالک\s+مکان",                                   3.5),
        ("اردو: کرایہ دار",          r"کرایہ\s+دار",                                   3.5),
        ("اردو: ماہانہ کرایہ",       r"ماہانہ\s+کرایہ",                               3.5),
        ("اردو: ضمانت رقم",         r"ضمانت\s+رقم",                                   2.5),
    ],

    "Employment Contract": [
        # English
        ("employment contract",        r"\bemployment\s+(?:contract|agreement)\b",         5.0),
        ("offer of employment",        r"\boffer\s+of\s+employment\b",                     4.5),
        ("terms of employment",        r"\bterms\s+of\s+(?:employment|service)\b",         4.0),
        ("job offer",                  r"\bjob\s+offer\b",                                 3.5),
        ("employer",                   r"\bemployer\b",                                    3.0),
        ("employee",                   r"\bemployee\b",                                    3.0),
        ("salary / remuneration",      r"\b(?:salary|remuneration|compensation)\b",        2.5),
        ("designation / position",     r"\b(?:designation|position|role)\b",               2.0),
        ("probation period",           r"\b(?:probation|probationary)\s+period\b",         2.5),
        ("notice period",              r"\bnotice\s+period\b",                             2.5),
        ("date of joining",            r"\b(?:date\s+of\s+(?:joining|commencement)|joining\s+date)\b", 2.5),
        # Urdu
        ("اردو: ملازمت کا معاہدہ",    r"ملازمت\s+کا?\s+معاہدہ",                         5.0),
        ("اردو: تنخواہ",             r"\bتنخواہ\b",                                     3.0),
        ("اردو: آجر",               r"\bآجر\b",                                        2.5),
        ("اردو: ملازم",             r"\bملازم\b",                                      2.5),
        ("اردو: تعیناتی",           r"\bتعیناتی\b",                                   2.0),
    ],
}

# Precompile all patterns for performance
_COMPILED: dict[str, list[tuple[str, re.Pattern, float]]] = {
    doc_type: [
        (name, re.compile(pattern, re.IGNORECASE | re.UNICODE), weight)
        for name, pattern, weight in rules
    ]
    for doc_type, rules in _RULES.items()
}

# Maximum achievable score per type (sum of all weights)
_MAX_SCORE: dict[str, float] = {
    doc_type: sum(w for _, _, w in rules)
    for doc_type, rules in _RULES.items()
}


# ═══════════════════════════════════════════════════════════════════════════════
# Rule-based classification
# ═══════════════════════════════════════════════════════════════════════════════

def _classify_rules(text: str) -> tuple[str, float, list[str]]:
    """
    Score the text against all rule sets and return the best match.

    Returns:
        (document_type, confidence, matched_rule_names)

    Confidence formula:
        match_fraction  = actual_score / max_possible_score_for_best_type
        competition     = second_best_score / best_score  (0.0 when no rival)
        confidence      = match_fraction × (1 - competition × 0.35)
    """
    scan = text[:_SCAN_LIMIT]

    scores:  dict[str, float]     = {}
    matched: dict[str, list[str]] = {}

    for doc_type, rules in _COMPILED.items():
        type_score  = 0.0
        type_hits: list[str] = []
        for name, pattern, weight in rules:
            if pattern.search(scan):
                type_score += weight
                type_hits.append(name)
        scores[doc_type]  = type_score
        matched[doc_type] = type_hits

    if not any(scores.values()):
        return "Unknown", 0.0, []

    # Best and second-best
    sorted_types = sorted(scores, key=lambda t: scores[t], reverse=True)
    best_type    = sorted_types[0]
    best_score   = scores[best_type]

    if best_score == 0.0:
        return "Unknown", 0.0, []

    match_fraction = min(best_score / _MAX_SCORE[best_type], 1.0)

    second_score = scores[sorted_types[1]] if len(sorted_types) > 1 else 0.0
    competition  = (second_score / best_score) if best_score > 0 else 0.0

    confidence = match_fraction * (1.0 - competition * 0.35)
    confidence = round(min(max(confidence, 0.0), 0.95), 3)

    logger.debug(
        "Rule scores: %s  best=%s  match_frac=%.2f  competition=%.2f  conf=%.3f",
        {t: round(s, 1) for t, s in scores.items()},
        best_type, match_fraction, competition, confidence,
    )
    return best_type, confidence, matched[best_type]


# ═══════════════════════════════════════════════════════════════════════════════
# Optional LLM fallback
# ═══════════════════════════════════════════════════════════════════════════════

def _classify_llm(text: str) -> tuple[str, float]:
    """
    Use Groq's fast model to classify the document when rule confidence is low.

    Returns (document_type, confidence).
    Returns ("Unknown", 0.0) silently on any error or missing API key.
    Imports Groq client dynamically so this module never hard-fails without key.
    """
    try:
        from utils.config import GROQ_API_KEY, GROQ_FAST_MODEL  # local import
        from utils.groq_client import call_groq_with_rotation
    except ImportError as exc:
        logger.debug("Groq SDK not available for LLM classification: %s", exc)
        return "Unknown", 0.0

    if not GROQ_API_KEY:
        logger.debug("GROQ_API_KEY not set — skipping LLM classification fallback")
        return "Unknown", 0.0

    # Build a lean prompt — only send the first 1 500 characters
    snippet   = text[:1500].strip()
    type_list = " | ".join(t for t in DOCUMENT_TYPES if t != "Unknown")

    system_msg = (
        "You are a legal document classifier for Pakistani law. "
        "You will be given the beginning of a legal document and must classify it. "
        "Respond ONLY with valid JSON in the format: "
        '{"type": "<DocumentType>", "confidence": <0.0-1.0>}'
    )
    user_msg = (
        f"Classify this document. Choose EXACTLY one of: [{type_list}].\n\n"
        f"Document text:\n{snippet}"
    )

    try:
        response = call_groq_with_rotation(lambda c: c.chat.completions.create(
            model=GROQ_FAST_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user",   "content": user_msg},
            ],
            temperature=0.0,
            max_tokens=64,
        ))
        raw = response.choices[0].message.content.strip()

        # Extract the JSON object (handles markdown code fences)
        json_match = re.search(r"\{[^}]+\}", raw)
        if not json_match:
            logger.warning("LLM classifier returned non-JSON: %s", raw[:120])
            return "Unknown", 0.0

        data       = json.loads(json_match.group())
        raw_type   = data.get("type", "Unknown")
        confidence = float(data.get("confidence", 0.0))

        # Canonicalise the returned type (case-insensitive match)
        doc_type = "Unknown"
        for dt in DOCUMENT_TYPES:
            if raw_type.strip().lower() == dt.lower():
                doc_type = dt
                break

        confidence = round(min(max(confidence, 0.0), 0.95), 3)
        logger.info("LLM classified: type=%s  confidence=%.3f", doc_type, confidence)
        return doc_type, confidence

    except Exception as exc:
        logger.warning("LLM classification failed (%s): %s", type(exc).__name__, exc)
        return "Unknown", 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def classify_document(
    text: str,
    detected_language: str = "Unknown",
    use_llm_fallback: bool = True,
) -> ClassificationResult:
    """
    Classify the type of an extracted legal document.

    Args:
        text:               Extracted plain text from the document.
        detected_language:  Language hint from text_extractor ("English"|"Urdu"|"Mixed"|"Unknown").
                            Currently informational; future rules may weight differently.
        use_llm_fallback:   When True and GROQ_API_KEY is set, the LLM is invoked
                            if rule-based confidence < _LLM_THRESHOLD.

    Returns:
        ClassificationResult with document_type, confidence, method, matched_rules.
    """
    if not text or not text.strip():
        return ClassificationResult(
            document_type="Unknown",
            confidence=0.0,
            method="rule_based",
            matched_rules=[],
        )

    # ── Step 1: rule-based ────────────────────────────────────────────────────
    rule_type, rule_conf, rule_hits = _classify_rules(text)

    logger.info(
        "Rule classification: type=%s  confidence=%.3f  rules_matched=%d  lang=%s",
        rule_type, rule_conf, len(rule_hits), detected_language,
    )

    # High-confidence rule result — return immediately
    if rule_conf >= _LLM_THRESHOLD:
        return ClassificationResult(
            document_type=rule_type,
            confidence=rule_conf,
            method="rule_based",
            matched_rules=rule_hits,
        )

    # ── Step 2: optional LLM fallback ─────────────────────────────────────────
    if not use_llm_fallback:
        return ClassificationResult(
            document_type=rule_type,
            confidence=rule_conf,
            method="rule_based",
            matched_rules=rule_hits,
        )

    llm_type, llm_conf = _classify_llm(text)

    # LLM failed or returned Unknown — keep rule result
    if llm_type == "Unknown" or llm_conf == 0.0:
        return ClassificationResult(
            document_type=rule_type,
            confidence=rule_conf,
            method="rule_based",
            matched_rules=rule_hits,
        )

    # Both agree — blend confidence upward (mutual reinforcement)
    if llm_type == rule_type:
        blended = round(min((rule_conf + llm_conf) / 2 * 1.15, 0.95), 3)
        return ClassificationResult(
            document_type=llm_type,
            confidence=blended,
            method="rule_based+llm_confirm",
            matched_rules=rule_hits,
        )

    # They disagree — trust LLM when it is more confident; else keep rules
    if llm_conf > rule_conf:
        return ClassificationResult(
            document_type=llm_type,
            confidence=llm_conf,
            method="llm",
            matched_rules=[],
        )

    return ClassificationResult(
        document_type=rule_type,
        confidence=rule_conf,
        method="rule_based",
        matched_rules=rule_hits,
    )
