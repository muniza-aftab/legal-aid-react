"""
ngo_matcher.py — Smart NGO recommendation engine (Phase 3.3).

This is the AUTHORITATIVE import for NGO logic. Do NOT import from ngo_engine.py.

Changes in Phase 3.3:
  • Services-based scoring: NGOs with relevant services get extra weight
  • Priority field: NGOs tagged priority="high" get a boost when risk=High/Critical
  • Helplines loader: get_urgent_helplines() checks data/helplines.json first,
    falls back to the inline URGENT_HELPLINES dict
  • Function signature: (category, city="", max_results=3, risk_level="Medium")
"""
from __future__ import annotations
import json
import os
from app.utils.config import NGO_FILE, NGO_TYPE_TO_CATEGORY

__all__ = ["recommend_ngos", "get_urgent_helplines", "URGENT_HELPLINES"]

# ── Risk priority sets ────────────────────────────────────────────────────────

_HIGH_RISK_PRIORITY_TYPES = {
    "Emergency / Social Services",
    "Legal Aid",
    "Human Rights",
    "Gender Violence",
    "Women & Child Rights",
}

_EMERGENCY_NGO_TYPES = {
    "Emergency / Social Services",
    "Legal Aid",
}

# Services keywords that match legal categories
_CATEGORY_SERVICE_KEYWORDS: dict[str, list[str]] = {
    "Family Law":            ["family", "women", "shelter", "domestic", "divorce"],
    "Labour Law":            ["labour", "worker", "employment", "wages"],
    "Criminal Law":          ["legal aid", "legal representation", "fir", "police"],
    "Cybercrime":            ["cyber", "digital", "online harassment"],
    "Harassment":            ["harassment", "gender violence", "sexual abuse", "shelter"],
    "Property / Tenancy":   ["property", "tenancy", "housing"],
    "Inheritance Law":       ["inheritance", "succession", "family"],
    "Consumer Rights":       ["consumer", "rights", "advocacy"],
    "Constitutional Law":    ["human rights", "constitutional", "legal aid"],
    "General / Other":       ["legal aid", "counselling", "social services"],
}

# ── Inline emergency helplines (fallback if helplines.json not found) ─────────

URGENT_HELPLINES: dict[str, list[dict]] = {
    "Criminal Law": [
        {"label": "Police Emergency",  "number": "15",   "icon": "🚔"},
        {"label": "Legal Aid",         "number": "1099", "icon": "⚖️"},
    ],
    "Harassment": [
        {"label": "Women Helpline",    "number": "1099", "icon": "👩"},
        {"label": "Cyber Crime (FIA)", "number": "9911", "icon": "🛡️"},
    ],
    "Family Law": [
        {"label": "Women Helpline",    "number": "1099", "icon": "👩"},
        {"label": "Madadgaar",         "number": "1098", "icon": "📞"},
    ],
    "Cybercrime": [
        {"label": "Cyber Crime (FIA)", "number": "9911", "icon": "🛡️"},
    ],
    "Labour Law": [
        {"label": "Labour Helpline",   "number": "111-152-152", "icon": "💼"},
    ],
}


# ── Data loaders ──────────────────────────────────────────────────────────────

def _load_ngos() -> list[dict]:
    try:
        with open(NGO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _load_helplines() -> dict[str, dict[str, list[dict]]]:
    """
    Load structured helplines from data/helplines.json if available.
    Structure: {category: {risk_level: [{icon, label, number}, ...]}}
    Falls back to empty dict → caller uses URGENT_HELPLINES inline dict.
    """
    _base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    helplines_path = os.path.join(_base, "data", "helplines.json")
    try:
        with open(helplines_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


# ── Scoring helpers ───────────────────────────────────────────────────────────

def _services_score(ngo: dict, category: str) -> float:
    """
    Award 0.5 per matching keyword found in the NGO's services list.
    Max contribution: 1.5 (capped so it doesn't dominate category match).
    """
    keywords = _CATEGORY_SERVICE_KEYWORDS.get(category, [])
    if not keywords:
        return 0.0
    services = ngo.get("services", [])
    if isinstance(services, str):
        services = [services]
    services_text = " ".join(str(s) for s in services).lower()
    hits = sum(1 for kw in keywords if kw in services_text)
    return min(hits * 0.5, 1.5)


# ── Public API ────────────────────────────────────────────────────────────────

def recommend_ngos(
    category: str,
    city: str = "",
    max_results: int = 3,
    risk_level: str = "Medium",
) -> list[dict]:
    """
    Return up to max_results NGOs relevant to category + risk_level.

    Parameters:
      category    — legal category string (e.g. "Labour Law")
      city        — optional city name for proximity scoring
      max_results — maximum NGOs to return (default: 3)
      risk_level  — "Low" | "Medium" | "High" | "Critical" (default: "Medium").
                    Critical is treated as urgency-equivalent to High for routing.

    Scoring weights:
      +4.0  High/Critical risk + emergency/legal-aid NGO type
      +3.0  City match (partial, case-insensitive)
      +2.0  Nationwide coverage
      +2.0  Category match via NGO_TYPE_TO_CATEGORY
      +1.5  Services match (capped, via _services_score)
      +1.0  NGO priority == "high" when risk is High/Critical
      +1.0  High/Critical risk + other priority types

    Only NGOs with score > 0 are returned.
    Falls back to Legal Aid / Emergency NGOs when count is low.
    """
    # Defensive normalisation
    category   = str(category or "General / Other")
    city       = str(city or "")
    risk_level = str(risk_level or "Medium")
    if risk_level not in ("Low", "Medium", "High", "Critical"):
        risk_level = "Medium"
    try:
        max_results = int(max_results)
    except (TypeError, ValueError):
        max_results = 3

    ngos = _load_ngos()
    if not ngos:
        return []

    # Critical is urgency-equivalent to High for routing purposes:
    # both should boost emergency / legal-aid NGOs.
    is_high = risk_level in ("High", "Critical")
    scored: list[tuple[float, dict]] = []

    for ngo in ngos:
        score    = 0.0
        ngo_type = ngo.get("type", "")
        ngo_city = ngo.get("city", "Nationwide")

        # ── Category match ────────────────────────────────────────────────────
        # Support both old (type-based) and new (categories list) structure
        matched_from_type = NGO_TYPE_TO_CATEGORY.get(ngo_type, [])
        categories_field  = ngo.get("categories", [])
        if category in matched_from_type or category in categories_field:
            score += 2.0

        # ── Services match ────────────────────────────────────────────────────
        score += _services_score(ngo, category)

        # ── City proximity ────────────────────────────────────────────────────
        if city and city.lower() in ngo_city.lower():
            score += 3.0
        elif ngo_city.lower() == "nationwide":
            score += 2.0

        # ── Risk-level boosts ─────────────────────────────────────────────────
        if is_high:
            if ngo_type in _EMERGENCY_NGO_TYPES:
                score += 4.0
            elif ngo_type in _HIGH_RISK_PRIORITY_TYPES:
                score += 1.0
            # Priority field boost
            if ngo.get("priority", "").lower() == "high":
                score += 1.0

        scored.append((score, ngo))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Only genuinely relevant NGOs (score > 0)
    top = [n for s, n in scored if s > 0.0][:max_results]

    # Pad with Legal Aid / Emergency NGOs if under max_results
    if len(top) < max_results:
        included = {n["name"] for n in top}
        for _, ngo in scored:
            if len(top) >= max_results:
                break
            if ngo["name"] not in included and ngo.get("type") in (
                "Legal Aid", "Human Rights", "Emergency / Social Services"
            ):
                top.append(ngo)
                included.add(ngo["name"])

    return top


def get_urgent_helplines(category: str, risk_level: str = "Medium") -> list[dict]:
    """
    Return inline emergency helpline numbers for a given category + risk level.

    Loads from data/helplines.json if available, else uses inline URGENT_HELPLINES.

    Rules:
      - Low      → never return (not urgent)
      - Medium   → return only for Criminal Law, Harassment, Family Law
      - High     → return if category has helplines
      - Critical → same as High (always return helplines if available)
    """
    if risk_level == "Low":
        return []

    _MEDIUM_CATEGORIES = {"Criminal Law", "Harassment", "Family Law"}
    if risk_level == "Medium" and category not in _MEDIUM_CATEGORIES:
        return []

    # Try structured helplines.json first
    structured = _load_helplines()
    if structured:
        cat_data = structured.get(category, {})
        # High and Critical → try "High" tier first, fall back to "Medium"
        if risk_level in ("High", "Critical"):
            entries = cat_data.get("High") or cat_data.get("Medium") or []
        else:
            entries = cat_data.get("Medium") or []
        if entries:
            return entries

    # Fallback to inline dict
    return URGENT_HELPLINES.get(category, [])
