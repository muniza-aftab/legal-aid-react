"""
utils/lawyer_service.py — CRUD service for the DB-driven lawyer registry.

Public API:
    add_lawyer(data)                 → dict   (the saved lawyer)
    get_all_lawyers(available_only)  → list[dict]
    get_lawyer(lawyer_id)            → dict | None
    update_lawyer(lawyer_id, data)   → bool
    set_availability(lawyer_id, bool)→ bool
    increment_cases(lawyer_id)       → bool
    decrement_cases(lawyer_id)       → bool
    get_lawyers_for_ngo(ngo_id)      → list[dict]
    get_lawyer_stats()               → dict

Architecture rules:
    • No SQL in pages.
    • No LLM / RAG coupling.
    • expertise_sub stored as comma-separated string in DB;
      returned as list[str] in all dict results.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from app.utils.db import get_connection
from app.utils.legal_taxonomy import (
    LAWYER_EXPERTISE_AREAS,
    EXPERTISE_SUBAREAS,
)
from app.utils.config import PAKISTAN_CITIES


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sub_to_str(sub: list[str] | str | None) -> str:
    """Convert sub-expertise list → comma-delimited string for storage."""
    if isinstance(sub, list):
        return ",".join(s.strip() for s in sub if s.strip())
    return str(sub or "").strip()


def _str_to_sub(value: str) -> list[str]:
    """Convert comma-delimited string → list (empty items stripped)."""
    return [s.strip() for s in value.split(",") if s.strip()]


def _row_to_dict(row) -> dict:
    """Convert a sqlite3.Row to dict, expanding expertise_sub to a list."""
    d = dict(row)
    d["expertise_sub"] = _str_to_sub(d.get("expertise_sub", ""))
    d["available"]     = bool(d.get("available", 1))
    return d


# ─────────────────────────────────────────────────────────────────────────────
# Validation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _validate_lawyer_data(data: dict, require_all: bool = True) -> None:
    """Raise ValueError with a human-readable message on bad input."""
    if require_all or "full_name" in data:
        name = str(data.get("full_name", "")).strip()
        if not name:
            raise ValueError("Full name is required.")

    if require_all or "bar_license" in data:
        lic = str(data.get("bar_license", "")).strip()
        if not lic:
            raise ValueError("Bar license number is required.")

    if require_all or "city" in data:
        city = str(data.get("city", "")).strip()
        valid = [c for c in PAKISTAN_CITIES if c != "Any City"]
        if not city or city not in valid:
            raise ValueError(f"City must be one of: {', '.join(valid)}")

    if require_all or "expertise_main" in data:
        exp = str(data.get("expertise_main", "")).strip()
        if not exp:
            raise ValueError("Main expertise is required.")
        if exp not in LAWYER_EXPERTISE_AREAS:
            raise ValueError(
                f"expertise_main must be one of: {', '.join(LAWYER_EXPERTISE_AREAS)}"
            )

    if "expertise_sub" in data:
        sub = data["expertise_sub"]
        if isinstance(sub, list):
            valid_sub = EXPERTISE_SUBAREAS.get(data.get("expertise_main", ""), [])
            bad = [s for s in sub if s and s not in valid_sub]
            if bad:
                raise ValueError(
                    f"Invalid sub-specializations: {bad}. "
                    f"Valid for {data.get('expertise_main', '?')}: {valid_sub}"
                )
    if data.get("ngo_id"):
        from app.utils.ngo_service import get_ngo
        ngo = get_ngo(data["ngo_id"])
        if not ngo or not ngo.get("active"):
            raise ValueError("Select an active registered NGO.")
        if not ngo.get("handles_all_cases") and data.get("expertise_main") not in ngo.get("categories", []):
            raise ValueError("The lawyer's expertise must be supported by the selected NGO.")


# ─────────────────────────────────────────────────────────────────────────────
# Write operations
# ─────────────────────────────────────────────────────────────────────────────

def add_lawyer(data: dict) -> dict:
    """
    Register a new lawyer.

    Required fields in data:
        full_name, bar_license, city, expertise_main

    Optional fields:
        ngo_id, expertise_sub (list[str]), available (bool)

    Returns the saved lawyer as a dict (expertise_sub as list).
    Raises ValueError on validation failure or duplicate bar_license.
    """
    _validate_lawyer_data(data, require_all=True)

    lawyer_id = f"LAW-{uuid.uuid4().hex[:8].upper()}"
    timestamp = datetime.utcnow().isoformat(sep=" ", timespec="seconds")

    record = {
        "lawyer_id":      lawyer_id,
        "full_name":      str(data["full_name"]).strip(),
        "bar_license":    str(data["bar_license"]).strip(),
        "ngo_id":         str(data.get("ngo_id", "")).strip(),
        "city":           str(data["city"]).strip(),
        "expertise_main": str(data["expertise_main"]).strip(),
        "expertise_sub":  _sub_to_str(data.get("expertise_sub", [])),
        "active_cases":   int(data.get("active_cases", 0)),
        "available":      int(bool(data.get("available", True))),
        "created_at":     timestamp,
    }

    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO lawyers
                   (lawyer_id, full_name, bar_license, ngo_id, city,
                    expertise_main, expertise_sub, active_cases, available, created_at)
                   VALUES
                   (:lawyer_id, :full_name, :bar_license, :ngo_id, :city,
                    :expertise_main, :expertise_sub, :active_cases, :available, :created_at)""",
                record,
            )
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise ValueError(
                f"Bar license '{record['bar_license']}' is already registered."
            ) from exc
        raise

    result = dict(record)
    result["expertise_sub"] = _str_to_sub(result["expertise_sub"])
    result["available"]     = bool(result["available"])
    return result


def update_lawyer(lawyer_id: str, data: dict) -> bool:
    """
    Update mutable fields of a lawyer (patch semantics).
    Returns True if a row was changed.
    """
    _validate_lawyer_data(data, require_all=False)

    allowed = {
        "full_name", "bar_license", "ngo_id", "city",
        "expertise_main", "expertise_sub", "available",
    }
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return False

    if "expertise_sub" in updates:
        updates["expertise_sub"] = _sub_to_str(updates["expertise_sub"])
    if "available" in updates:
        updates["available"] = int(bool(updates["available"]))

    set_clause = ", ".join(f"{col} = ?" for col in updates)
    values     = list(updates.values()) + [lawyer_id]

    try:
        with get_connection() as conn:
            cur = conn.execute(
                f"UPDATE lawyers SET {set_clause} WHERE lawyer_id = ?", values
            )
        return cur.rowcount > 0
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise ValueError(
                f"Bar license '{data.get('bar_license', '')}' is already registered."
            ) from exc
        raise


def delete_lawyer(lawyer_id: str) -> bool:
    """Permanently delete a lawyer. Returns True if a row was deleted."""
    with get_connection() as conn:
        if conn.execute("SELECT 1 FROM applications WHERE assigned_lawyer_id=? LIMIT 1", (lawyer_id,)).fetchone():
            raise ValueError("This lawyer has case history. Mark the lawyer unavailable instead of deleting the record.")
        cur = conn.execute("DELETE FROM lawyers WHERE lawyer_id = ?", (lawyer_id,))
    return cur.rowcount > 0


def set_availability(lawyer_id: str, available: bool) -> bool:
    """Set a lawyer's availability flag. Returns True if changed."""
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE lawyers SET available = ? WHERE lawyer_id = ?",
            (int(available), lawyer_id),
        )
    return cur.rowcount > 0


def increment_cases(lawyer_id: str) -> bool:
    """Increment active_cases by 1. Returns True if changed."""
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE lawyers SET active_cases = active_cases + 1 WHERE lawyer_id = ?",
            (lawyer_id,),
        )
    return cur.rowcount > 0


def decrement_cases(lawyer_id: str) -> bool:
    """Decrement active_cases by 1 (floor 0). Returns True if changed."""
    with get_connection() as conn:
        cur = conn.execute(
            """UPDATE lawyers
               SET active_cases = MAX(0, active_cases - 1)
               WHERE lawyer_id = ?""",
            (lawyer_id,),
        )
    return cur.rowcount > 0


# ─────────────────────────────────────────────────────────────────────────────
# Read operations
# ─────────────────────────────────────────────────────────────────────────────

def get_all_lawyers(available_only: bool = False) -> list[dict]:
    """
    Return all lawyers, lowest active-case-count first (ready to take new cases).
    If available_only=True, only return available=1 lawyers.
    """
    sql = "SELECT * FROM lawyers"
    if available_only:
        sql += " WHERE available = 1"
    sql += " ORDER BY active_cases ASC, created_at DESC"
    with get_connection() as conn:
        rows = conn.execute(sql).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_lawyer(lawyer_id: str) -> Optional[dict]:
    """Return a single lawyer by ID, or None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM lawyers WHERE lawyer_id = ?", (lawyer_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_lawyers_for_ngo(ngo_id: str) -> list[dict]:
    """Return all lawyers attached to a specific NGO."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM lawyers WHERE ngo_id = ? ORDER BY active_cases ASC",
            (ngo_id,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def find_best_lawyer(
    expertise_main: str,
    city: str = "",
    expertise_sub: str = "",
    ngo_id: str = "",
) -> Optional[dict]:
    """
    Deterministic lawyer assignment — no AI involved.

    Ranking logic (each criterion adds points; highest total wins):
        +10  available = 1
        + 8  expertise_main matches exactly
        + 4  expertise_sub contains the requested sub-specialization
        +12  city matches (case-insensitive) — weighted heavily so
             a same-city lawyer always beats a different-city lawyer
        + 2  attached to the preferred NGO (ngo_id)
        - active_cases  (penalise high caseload)

    If city is provided, lawyers from a different city are only
    considered when NO same-city lawyer with matching expertise exists.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM lawyers
               WHERE expertise_main = ?
               ORDER BY active_cases ASC""",
            (expertise_main,),
        ).fetchall()

    if not rows:
        return None

    # If a city is provided, prefer same-city lawyers exclusively.
    # Only fall back to any city if no same-city lawyer has the expertise.
    if city:
        same_city_rows = [r for r in rows
                          if _row_to_dict(r)["city"].lower() == city.lower()]
        if same_city_rows:
            rows = same_city_rows

    best       = None
    best_score = -999

    for row in rows:
        d     = _row_to_dict(row)
        score = 0

        if d["available"]:
            score += 10
        score += 8   # expertise_main already matched by WHERE clause
        if expertise_sub and expertise_sub in d["expertise_sub"]:
            score += 4
        if city and d["city"].lower() == city.lower():
            score += 12
        if ngo_id and d["ngo_id"] == ngo_id:
            score += 2
        score -= d["active_cases"]

        if score > best_score:
            best_score = score
            best       = d

    return best


def get_lawyer_stats() -> dict:
    """
    Aggregate stats for the analytics tab.

    Returns:
        {
          "total":           int,
          "available":       int,
          "busy":            int,
          "avg_active_cases":float,
          "by_expertise":    {expertise: count},
          "by_city":         {city: count},
          "by_ngo":          {ngo_id: count},
          "top_loaded":      list[dict]  — top 5 by active_cases
        }
    """
    with get_connection() as conn:
        total     = conn.execute("SELECT COUNT(*) FROM lawyers").fetchone()[0]
        available = conn.execute(
            "SELECT COUNT(*) FROM lawyers WHERE available=1"
        ).fetchone()[0]
        avg_row   = conn.execute(
            "SELECT AVG(active_cases) FROM lawyers"
        ).fetchone()[0]

        exp_rows  = conn.execute(
            "SELECT expertise_main, COUNT(*) as cnt FROM lawyers GROUP BY expertise_main"
        ).fetchall()
        city_rows = conn.execute(
            "SELECT city, COUNT(*) as cnt FROM lawyers GROUP BY city"
        ).fetchall()
        ngo_rows  = conn.execute(
            "SELECT ngo_id, COUNT(*) as cnt FROM lawyers WHERE ngo_id != '' GROUP BY ngo_id"
        ).fetchall()
        top_rows  = conn.execute(
            "SELECT * FROM lawyers ORDER BY active_cases DESC LIMIT 5"
        ).fetchall()

    return {
        "total":            total,
        "available":        available,
        "busy":             total - available,
        "avg_active_cases": round(avg_row or 0, 1),
        "by_expertise":     {r["expertise_main"]: r["cnt"] for r in exp_rows},
        "by_city":          {r["city"]: r["cnt"] for r in city_rows},
        "by_ngo":           {r["ngo_id"]: r["cnt"] for r in ngo_rows},
        "top_loaded":       [_row_to_dict(r) for r in top_rows],
    }
