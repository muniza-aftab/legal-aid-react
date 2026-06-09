"""
routing_service.py — Deterministic rule-based case routing engine.

No AI / LLM. Every decision is explicit, scored, and auditable.

Scoring weights
───────────────
NGO
  +30  Same city as applicant
  +25  NGO.categories includes case type  (direct match)
  +15  NGO.handles_all_cases = True       (broader match, only if no direct)

Lawyer
  +20  available = True                   (prerequisite bonus)
  +30  Same city as applicant
  +25  expertise_main matches case type
  +10  Affiliated with matched NGO
  − 2  per active_cases                  (workload penalty)

Confidence
  High   — both NGO and Lawyer matched from DB
  Medium — only one side matched
  Low    — neither matched

Public API
──────────
  route_case(city, case_type, urgency)              → RoutingResult dict
  get_candidate_ngos(city, case_type)               → list[dict with _score]
  get_candidate_lawyers(city, case_type, ngo_id)    → list[dict with _score]
"""
from __future__ import annotations

from typing import Optional

# ─── Weights ─────────────────────────────────────────────────────────────────

W_NGO_CITY        = 30
W_NGO_CATEGORY    = 25
W_NGO_HANDLES_ALL = 15   # applied only when direct match absent

W_LAW_AVAILABLE   = 20
W_LAW_CITY        = 30
W_LAW_EXPERTISE   = 25
W_LAW_NGO_MATCH   = 10
W_LAW_CASE_PENALTY = 2   # deducted per active case


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _ngo_categories(ngo: dict) -> list[str]:
    """Return NGO categories as a Python list (handles JSON-string or list)."""
    raw = ngo.get("categories", [])
    if isinstance(raw, list):
        return raw
    import json
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except Exception:
        return [ngo.get("category", "")] if ngo.get("category") else []


def _score_ngo(ngo: dict, city: str, case_type: str) -> int:
    score      = 0
    cats       = _ngo_categories(ngo)
    direct_hit = case_type in cats

    if city and ngo.get("city", "").lower() == city.lower():
        score += W_NGO_CITY
    if direct_hit:
        score += W_NGO_CATEGORY
    if ngo.get("handles_all_cases") and not direct_hit:
        score += W_NGO_HANDLES_ALL
    return score


def _score_lawyer(
    lawyer: dict,
    city: str,
    case_type: str,
    preferred_ngo_id: str = "",
) -> int:
    if not lawyer.get("available", False):
        return -1                            # unavailable — never assignable

    score = W_LAW_AVAILABLE
    if city and lawyer.get("city", "").lower() == city.lower():
        score += W_LAW_CITY
    if lawyer.get("expertise_main", "") == case_type:
        score += W_LAW_EXPERTISE
    if preferred_ngo_id and lawyer.get("ngo_id", "") == preferred_ngo_id:
        score += W_LAW_NGO_MATCH
    score -= lawyer.get("active_cases", 0) * W_LAW_CASE_PENALTY
    return score


# ─── Candidate lists ─────────────────────────────────────────────────────────

def get_candidate_ngos(city: str, case_type: str) -> list[dict]:
    """
    Return all active NGOs that could handle this case, scored descending.
    Includes NGOs with a direct category match OR handles_all_cases=True.
    City is a HARD requirement — only same-city NGOs are considered.
    Each dict has an extra `_score` key.
    """
    from utils.ngo_service import get_all_ngos
    candidates = []
    for ngo in get_all_ngos(active_only=True):
        if city and ngo.get("city", "").lower() != city.lower():
            continue
        cats = _ngo_categories(ngo)
        if case_type not in cats and not ngo.get("handles_all_cases"):
            continue
        s = _score_ngo(ngo, city, case_type)
        candidates.append({**ngo, "_score": s})
    return sorted(candidates, key=lambda x: x["_score"], reverse=True)


def get_candidate_lawyers(
    city: str,
    case_type: str,
    preferred_ngo_id: str = "",
) -> list[dict]:
    """
    Return all available lawyers whose expertise matches case_type, scored.
    City is a HARD requirement — only same-city lawyers are considered.
    Each dict has an extra `_score` key.
    """
    from utils.lawyer_service import get_all_lawyers
    candidates = []
    for lawyer in get_all_lawyers():
        if lawyer.get("expertise_main", "") != case_type:
            continue
        if city and lawyer.get("city", "").lower() != city.lower():
            continue
        s = _score_lawyer(lawyer, city, case_type, preferred_ngo_id)
        if s < 0:       # unavailable
            continue
        candidates.append({**lawyer, "_score": s})
    return sorted(candidates, key=lambda x: x["_score"], reverse=True)


# ─── Routing reason builder ───────────────────────────────────────────────────

def _build_reason(
    ngo: Optional[dict],
    lawyer: Optional[dict],
    city: str,
    case_type: str,
    urgency: str,
) -> str:
    parts = []

    if ngo:
        ngo_clauses = [f"NGO '{ngo['ngo_name']}'"]
        if city and ngo.get("city", "").lower() == city.lower():
            ngo_clauses.append(f"is in {city}")
        if ngo.get("handles_all_cases") and case_type not in _ngo_categories(ngo):
            ngo_clauses.append("handles all case types")
        else:
            ngo_clauses.append(f"covers {case_type}")
        parts.append(" — ".join(ngo_clauses))

    if lawyer:
        law_clauses = [f"Lawyer '{lawyer['full_name']}'"]
        if city and lawyer.get("city", "").lower() == city.lower():
            law_clauses.append(f"is in {city}")
        law_clauses.append(f"specialises in {case_type}")
        if lawyer.get("available"):
            law_clauses.append("is currently available")
        parts.append(" — ".join(law_clauses))

    if not parts:
        return (
            f"No matching NGO or lawyer found for {case_type} in {city or 'any city'}. "
            "Case is pending manual assignment."
        )

    reason = "Automatically assigned: " + ". ".join(parts) + "."
    if urgency in ("High", "Critical"):
        reason += f" Case is flagged {urgency} priority."
    return reason


# ─── Main routing function ────────────────────────────────────────────────────

def route_case(city: str, case_type: str, urgency: str = "Medium") -> dict:
    """
    Core routing function — returns best NGO + Lawyer with full explanation.

    Returns:
        {
          "ngo":               dict | None,      # best NGO (without _score)
          "lawyer":            dict | None,      # best Lawyer (without _score)
          "reason":            str,              # human-readable explanation
          "confidence":        "High"|"Medium"|"Low",
          "score":             int,              # combined raw score
          "ngo_score":         int,
          "lawyer_score":      int,
          "candidate_ngos":    list[dict],       # top 5 (without _score)
          "candidate_lawyers": list[dict],       # top 5 (without _score)
        }
    """
    cand_ngos    = get_candidate_ngos(city, case_type)
    best_ngo     = cand_ngos[0] if cand_ngos else None
    pref_ngo_id  = best_ngo["ngo_id"] if best_ngo else ""

    cand_lawyers = get_candidate_lawyers(city, case_type, pref_ngo_id)
    best_lawyer  = cand_lawyers[0] if cand_lawyers else None

    ngo_score    = best_ngo["_score"]    if best_ngo    else 0
    lawyer_score = best_lawyer["_score"] if best_lawyer else 0

    if best_ngo and best_lawyer:
        confidence = "High"
    elif best_ngo or best_lawyer:
        confidence = "Medium"
    else:
        confidence = "Low"

    reason = _build_reason(best_ngo, best_lawyer, city, case_type, urgency)

    def _clean(d: Optional[dict]) -> Optional[dict]:
        return {k: v for k, v in d.items() if k != "_score"} if d else None

    return {
        "ngo":               _clean(best_ngo),
        "lawyer":            _clean(best_lawyer),
        "reason":            reason,
        "confidence":        confidence,
        "score":             ngo_score + lawyer_score,
        "ngo_score":         ngo_score,
        "lawyer_score":      lawyer_score,
        "candidate_ngos":    [_clean(n) for n in cand_ngos[:5]],
        "candidate_lawyers": [_clean(l) for l in cand_lawyers[:5]],
    }
