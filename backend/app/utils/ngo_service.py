"""
utils/ngo_service.py — CRUD service for the DB-driven NGO registry.

Public API:
    add_ngo(data)              → dict
    get_all_ngos(...)          → list[dict]
    get_ngo(ngo_id)            → dict | None
    update_ngo(ngo_id, data)   → bool
    deactivate_ngo(ngo_id)     → bool
    reactivate_ngo(ngo_id)     → bool
    delete_ngo(ngo_id)         → bool
    get_ngo_by_name(name)      → dict | None
    get_ngos_for_category(cat) → list[dict]
    get_ngo_stats()            → dict

Schema note:
    `categories` is stored as a JSON array string (e.g. '["Family Law","Labour Law"]').
    `category` is kept as the primary/first category for backward-compatible routing.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

from utils.db import get_connection, NGO_CATEGORIES
from utils.config import PAKISTAN_CITIES


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _to_list(raw) -> list:
    """Parse categories from a JSON string or list to a Python list."""
    if isinstance(raw, list):
        return raw
    if not raw:
        return []
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else [result]
    except (json.JSONDecodeError, TypeError):
        return [raw] if raw else []


def _enrich(record: dict) -> dict:
    """Convert raw DB row dict: parse `categories` JSON string → list."""
    record = dict(record)
    raw = record.get("categories", "[]")
    parsed = _to_list(raw)
    # Fall back to `category` field if categories array is empty (legacy rows)
    if not parsed and record.get("category"):
        parsed = [record["category"]]
    record["categories"] = parsed
    return record


# ─────────────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────────────

def _validate_categories(categories: list) -> None:
    if not categories:
        raise ValueError("At least one category is required.")
    for cat in categories:
        if cat not in NGO_CATEGORIES:
            raise ValueError(
                f"Invalid category: '{cat}'. Must be one of: {', '.join(NGO_CATEGORIES)}"
            )


def _validate_ngo_data(data: dict, require_all: bool = True) -> None:
    if require_all or "ngo_name" in data:
        name = str(data.get("ngo_name", "")).strip()
        if not name:
            raise ValueError("NGO name is required.")
        if len(name) > 120:
            raise ValueError("NGO name must be 120 characters or fewer.")

    if require_all or "categories" in data:
        _validate_categories(data.get("categories") or [])

    if require_all or "city" in data:
        city = str(data.get("city", "")).strip()
        valid_cities = [c for c in PAKISTAN_CITIES if c != "Any City"]
        if city and city not in valid_cities:
            raise ValueError(f"City must be one of: {', '.join(valid_cities)}")

    if "contact_email" in data:
        email = str(data.get("contact_email", "")).strip()
        if email and "@" not in email:
            raise ValueError("Contact email is not valid.")

    if "contact_phone" in data:
        phone = str(data.get("contact_phone", "")).strip()
        if phone and len(phone) < 7:
            raise ValueError("Contact phone number is too short.")


# ─────────────────────────────────────────────────────────────────────────────
# Write operations
# ─────────────────────────────────────────────────────────────────────────────

def add_ngo(data: dict) -> dict:
    """
    Register a new NGO.

    Required fields: ngo_name, categories (list)
    Optional fields: city, contact_email, contact_phone, handles_all_cases, active
    """
    categories = _to_list(data.get("categories", []))
    if not categories and data.get("category"):
        categories = [data["category"]]

    data_with_cats = {**data, "categories": categories}
    _validate_ngo_data(data_with_cats, require_all=True)

    ngo_id    = f"NGO-{uuid.uuid4().hex[:8].upper()}"
    timestamp = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
    primary   = categories[0]

    record = {
        "ngo_id":            ngo_id,
        "ngo_name":          str(data["ngo_name"]).strip(),
        "category":          primary,
        "categories":        json.dumps(categories),
        "city":              str(data.get("city", "")).strip(),
        "contact_email":     str(data.get("contact_email", "")).strip(),
        "contact_phone":     str(data.get("contact_phone", "")).strip(),
        "handles_all_cases": int(bool(data.get("handles_all_cases", False))),
        "active":            int(bool(data.get("active", True))),
        "created_at":        timestamp,
    }

    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO ngos
                   (ngo_id, ngo_name, category, categories, city,
                    contact_email, contact_phone, handles_all_cases, active, created_at)
                   VALUES
                   (:ngo_id, :ngo_name, :category, :categories, :city,
                    :contact_email, :contact_phone, :handles_all_cases, :active, :created_at)""",
                record,
            )
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise ValueError(
                f"An NGO named '{record['ngo_name']}' already exists."
            ) from exc
        raise

    record["categories"] = categories  # return as list, not JSON string
    return record


def update_ngo(ngo_id: str, data: dict) -> bool:
    """
    Update mutable fields of an NGO (patch semantics — only present keys updated).
    Allowed fields: ngo_name, categories, city, contact_email, contact_phone,
                    handles_all_cases, active
    """
    allowed = {
        "ngo_name", "categories", "city",
        "contact_email", "contact_phone", "handles_all_cases", "active",
    }
    updates: dict = {}

    for k, v in data.items():
        if k not in allowed:
            continue
        if k == "categories":
            categories = _to_list(v)
            _validate_categories(categories)
            updates["category"]   = categories[0]
            updates["categories"] = json.dumps(categories)
        elif k == "handles_all_cases":
            updates[k] = int(bool(v))
        elif k == "active":
            updates[k] = int(bool(v))
        else:
            updates[k] = v

    if "ngo_name" in updates:
        name = str(updates["ngo_name"]).strip()
        if not name:
            raise ValueError("NGO name is required.")
        updates["ngo_name"] = name

    if "contact_email" in updates:
        email = str(updates["contact_email"]).strip()
        if email and "@" not in email:
            raise ValueError("Contact email is not valid.")

    if not updates:
        return False

    set_clause = ", ".join(f"{col} = ?" for col in updates)
    values     = list(updates.values()) + [ngo_id]

    try:
        with get_connection() as conn:
            cur = conn.execute(
                f"UPDATE ngos SET {set_clause} WHERE ngo_id = ?", values
            )
        return cur.rowcount > 0
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise ValueError(
                f"An NGO named '{data.get('ngo_name', '')}' already exists."
            ) from exc
        raise


def deactivate_ngo(ngo_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute("UPDATE ngos SET active = 0 WHERE ngo_id = ?", (ngo_id,))
    return cur.rowcount > 0


def reactivate_ngo(ngo_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute("UPDATE ngos SET active = 1 WHERE ngo_id = ?", (ngo_id,))
    return cur.rowcount > 0


def delete_ngo(ngo_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM ngos WHERE ngo_id = ?", (ngo_id,))
    return cur.rowcount > 0


# ─────────────────────────────────────────────────────────────────────────────
# Read operations
# ─────────────────────────────────────────────────────────────────────────────

def get_all_ngos(
    active_only: bool = False,
    city_filter: Optional[str] = None,
    category_filter: Optional[str] = None,
) -> list[dict]:
    conditions: list[str] = []
    params: list = []

    if active_only:
        conditions.append("active = 1")
    if city_filter:
        conditions.append("city = ?")
        params.append(city_filter)
    if category_filter:
        conditions.append(
            "(category = ? OR categories LIKE ? OR handles_all_cases = 1)"
        )
        params.append(category_filter)
        params.append(f'%"{category_filter}"%')

    sql = "SELECT * FROM ngos"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY created_at DESC"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_enrich(dict(r)) for r in rows]


def get_ngo(ngo_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM ngos WHERE ngo_id = ?", (ngo_id,)
        ).fetchone()
    return _enrich(dict(row)) if row else None


def get_ngo_by_name(name: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM ngos WHERE LOWER(ngo_name) = LOWER(?)", (name,)
        ).fetchone()
    return _enrich(dict(row)) if row else None


def get_ngos_for_category(category: str, city: str = "") -> list[dict]:
    """
    Return active NGOs matching the given category (checks both `category`
    field and `categories` JSON array) or that handle all case types.
    City-preferred sorting.
    """
    sql = """
        SELECT * FROM ngos
        WHERE active = 1
          AND (category = ? OR categories LIKE ? OR handles_all_cases = 1)
        ORDER BY
            CASE WHEN city = ? THEN 0 ELSE 1 END,
            handles_all_cases DESC,
            ngo_name ASC
    """
    like = f'%"{category}"%'
    with get_connection() as conn:
        rows = conn.execute(sql, (category, like, city)).fetchall()
    return [_enrich(dict(r)) for r in rows]


def get_ngo_stats() -> dict:
    with get_connection() as conn:
        total     = conn.execute("SELECT COUNT(*) FROM ngos").fetchone()[0]
        active    = conn.execute("SELECT COUNT(*) FROM ngos WHERE active=1").fetchone()[0]
        all_cases = conn.execute(
            "SELECT COUNT(*) FROM ngos WHERE handles_all_cases=1 AND active=1"
        ).fetchone()[0]
        cat_rows  = conn.execute(
            "SELECT category, COUNT(*) as cnt FROM ngos WHERE active=1 GROUP BY category"
        ).fetchall()
        city_rows = conn.execute(
            "SELECT city, COUNT(*) as cnt FROM ngos WHERE active=1 GROUP BY city"
        ).fetchall()

    return {
        "total":       total,
        "active":      active,
        "inactive":    total - active,
        "handles_all": all_cases,
        "by_category": {r["category"]: r["cnt"] for r in cat_rows},
        "by_city":     {r["city"]: r["cnt"] for r in city_rows},
    }
