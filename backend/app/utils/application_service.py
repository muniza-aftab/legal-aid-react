"""
utils/application_service.py — Legal Application Submission, NGO Routing & Lawyer Assignment.

Public API (unchanged from Phase 1 — backward compatible):
    submit_application(data)         -> dict    save + route + assign
    get_all_applications(...)        -> list[dict]
    get_application(app_id)          -> dict | None
    update_status(app_id, status)    -> bool
    get_stats()                      -> dict

New in Phase 2:
    assign_lawyer(app_id, lawyer_id) -> bool    admin override
    assign_ngo(app_id, ngo_id)       -> bool    admin override
    get_routing_explanation(app_id)  -> dict    explainable routing audit

Architecture:
    Routing is fully deterministic — no LLM involved in assignment decisions.
    DB-driven path tried first; static fallback ensures zero regression when
    the NGO/lawyer tables are empty (first-run state).
    The two new columns (assigned_lawyer_id, assigned_ngo_id) are added via
    idempotent migration inside init_applications_table().
"""
from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime
from typing import Optional

from utils.config import DB_PATH

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────


URGENCY_LEVELS: list[str] = ["Low", "Medium", "High", "Critical"]

_URGENCY_PRIORITY: dict[str, int] = {
    "Critical": 4,
    "High":     3,
    "Medium":   2,
    "Low":      1,
}

from utils.legal_taxonomy import (
    LEGAL_CASE_TYPES,
    NGO_CATEGORIES,
    LAWYER_EXPERTISE_AREAS,
)
CASE_TYPES = LEGAL_CASE_TYPES


# ─────────────────────────────────────────────────────────────────────────────
# DB connection helper
# ─────────────────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


# ─────────────────────────────────────────────────────────────────────────────
# Schema bootstrap (idempotent)
# ─────────────────────────────────────────────────────────────────────────────

def init_applications_table() -> None:
    """
    Create the applications table if it does not exist, and add Phase 2
    columns to pre-existing Phase 1 databases.

    Phase 2 adds:
        assigned_lawyer_id TEXT DEFAULT ''
        assigned_ngo_id    TEXT DEFAULT ''

    Safe to call multiple times.
    """
    with _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS applications (
                application_id     TEXT    PRIMARY KEY,
                timestamp          TEXT    NOT NULL,
                name               TEXT    NOT NULL,
                contact            TEXT    NOT NULL,
                email              TEXT    DEFAULT '',
                city               TEXT    NOT NULL,
                case_type          TEXT    NOT NULL,
                urgency            TEXT    NOT NULL,
                priority           INTEGER NOT NULL,
                description        TEXT    NOT NULL,
                status             TEXT    DEFAULT 'pending',
                assigned_ngo       TEXT    DEFAULT '',
                assigned_ngo_id    TEXT    DEFAULT '',
                suggested_lawyer   TEXT    DEFAULT '',
                assigned_lawyer_id TEXT    DEFAULT '',
                notes              TEXT    DEFAULT ''
            );
        """)

        existing = {
            row["name"]
            for row in c.execute("PRAGMA table_info(applications)")
        }
        for col, defn in [
            ("assigned_ngo_id",    "TEXT DEFAULT ''"),
            ("assigned_lawyer_id", "TEXT DEFAULT ''"),
        ]:
            if col not in existing:
                c.execute(f"ALTER TABLE applications ADD COLUMN {col} {defn}")
                logger.info("applications: added column %s", col)


# ─────────────────────────────────────────────────────────────────────────────
# Internal routing helpers
# ─────────────────────────────────────────────────────────────────────────────

def _route_ngo_db(case_type: str, city: str = "") -> tuple:
    """
    Try to find a matching NGO from the DB registry.
    Returns (ngo_name, ngo_id). Both empty strings on miss.
    """
    try:
        from utils.ngo_service import get_ngos_for_category
        ngo_category = case_type
        candidates   = get_ngos_for_category(ngo_category, city=city)
        if candidates:
            chosen = candidates[0]
            return chosen["ngo_name"], chosen["ngo_id"]
    except Exception:
        pass
    return "", ""





def _find_lawyer_db(
    case_type: str,
    city: str = "",
    expertise_sub: str = "",
    ngo_id: str = "",
) -> tuple:
    """
    Find the best lawyer from the DB using deterministic scoring.
    Returns (display_string, lawyer_id, routing_note). All empty on miss.

    Scoring (see lawyer_service.find_best_lawyer):
        +10 available
        + 8 expertise_main match
        + 4 expertise_sub match
        + 3 city match
        + 2 ngo_id match
        -   active_cases (workload penalty)
    """
    try:
        from utils.lawyer_service import find_best_lawyer
        expertise_main = case_type
        best = find_best_lawyer(
            expertise_main=expertise_main,
            city=city,
            expertise_sub=expertise_sub,
            ngo_id=ngo_id,
        )
        if best:
            display = f"{best['full_name']} ({best['bar_license']}, {best['city']})"

            reasons = [f"expertise={best['expertise_main']}"]
            if expertise_sub and expertise_sub in best.get("expertise_sub", []):
                reasons.append(f"sub-spec={expertise_sub}")
            if city and best["city"].lower() == city.lower():
                reasons.append("city-match")
            if ngo_id and best.get("ngo_id") == ngo_id:
                reasons.append("ngo-match")
            # Internal note — not shown to admin in UI
            note = "assigned"

            return display, best["lawyer_id"], note
    except Exception:
        pass
    return "", "", ""


# ─────────────────────────────────────────────────────────────────────────────
# Public routing helpers
# ─────────────────────────────────────────────────────────────────────────────

def route_to_ngo(case_type: str, city: str = "") -> str:
    """Return best NGO name. DB first, static fallback."""
    ngo_name, _ = _route_ngo_db(case_type, city=city)
    return ngo_name


def suggest_lawyers(case_type: str, city: str = "", max_results: int = 2) -> list:
    """Return lawyer suggestions from DB only."""

    display, _lid, _note = _find_lawyer_db(case_type, city=city)

    if not display:
        return []

    parts = display.split("(")
    name = parts[0].strip()

    rest = parts[1].rstrip(")").split(", ") if len(parts) > 1 else ["", city]

    bar_no = rest[0].strip() if len(rest) > 0 else ""
    l_city = rest[1].strip() if len(rest) > 1 else city

    return [{
        "name": name,
        "bar_no": bar_no,
        "city": l_city,
    }]


# ─────────────────────────────────────────────────────────────────────────────
# Core service: submit_application
# ─────────────────────────────────────────────────────────────────────────────

def submit_application(data: dict) -> dict:
    """
    Validate, enrich, route, and persist a new application.

    Required fields: name, contact, city, case_type, urgency, description
    Optional fields: email, expertise_sub (sub-specialization hint from AI)

    Routing pipeline (deterministic, no LLM):
        1. case_type -> NGO category -> DB NGO (city-preferred) or static name
        2. case_type -> expertise_main -> find_best_lawyer() scoring or static list
        3. Persist with assigned_ngo_id + assigned_lawyer_id for admin overrides
    """
    required = ["name", "contact", "city", "case_type", "urgency", "description"]
    missing  = [f for f in required if not str(data.get(f, "")).strip()]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    case_type = data["case_type"].strip()
    urgency   = data["urgency"].strip()

    if case_type not in CASE_TYPES:
        raise ValueError(f"Invalid case_type: '{case_type}'")
    if urgency not in URGENCY_LEVELS:
        raise ValueError(f"Invalid urgency: '{urgency}'")

    city = data.get("city", "").strip()

    # Deterministic routing via routing_service
    from utils.routing_service import route_case
    routing   = route_case(city, case_type, urgency)
    ngo       = routing["ngo"]
    lawyer    = routing["lawyer"]

    ngo_name       = ngo["ngo_name"]    if ngo    else ""
    ngo_id         = ngo["ngo_id"]      if ngo    else ""
    lawyer_display = (
        f"{lawyer['full_name']} ({lawyer['bar_license']}, {lawyer['city']})"
        if lawyer else ""
    )
    lawyer_id      = lawyer["lawyer_id"] if lawyer else ""
    routing_note   = routing["reason"]

    app_id    = f"APP-{uuid.uuid4().hex[:8].upper()}"
    timestamp = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
    priority  = _URGENCY_PRIORITY[urgency]

    application = {
        "application_id":     app_id,
        "timestamp":          timestamp,
        "name":               data["name"].strip(),
        "contact":            data["contact"].strip(),
        "email":              data.get("email", "").strip(),
        "city":               city,
        "case_type":          case_type,
        "urgency":            urgency,
        "priority":           priority,
        "description":        data["description"].strip(),
        "status": (
            "assigned"
            if ngo_name and lawyer_display
            else "pending"
        ),
        "assigned_ngo":       ngo_name,
        "assigned_ngo_id":    ngo_id,
        "suggested_lawyer":   lawyer_display,
        "assigned_lawyer_id": lawyer_id,
        "notes":              routing_note,
    }

    with _conn() as c:
        c.execute(
            """INSERT INTO applications
               (application_id, timestamp, name, contact, email, city,
                case_type, urgency, priority, description,
                status, assigned_ngo, assigned_ngo_id,
                suggested_lawyer, assigned_lawyer_id, notes)
               VALUES
               (:application_id, :timestamp, :name, :contact, :email, :city,
                :case_type, :urgency, :priority, :description,
                :status, :assigned_ngo, :assigned_ngo_id,
                :suggested_lawyer, :assigned_lawyer_id, :notes)""",
            application,
        )

    # Increment lawyer workload counter (non-critical — ignore failures)
    if lawyer_id:
        try:
            from utils.lawyer_service import increment_cases
            increment_cases(lawyer_id)
        except Exception:
            pass

    return application


# ─────────────────────────────────────────────────────────────────────────────
# Admin override helpers (Phase 3 admin dashboard)
# ─────────────────────────────────────────────────────────────────────────────

def assign_lawyer(app_id: str, lawyer_id: str) -> bool:
    """
    Admin override: assign a specific DB lawyer to an application.
    Updates suggested_lawyer display name, assigned_lawyer_id, and
    increments that lawyer's active_cases counter.
    Raises ValueError if lawyer_id not found.
    """
    from utils.lawyer_service import get_lawyer, increment_cases

    lawyer = get_lawyer(lawyer_id)
    if not lawyer:
        raise ValueError(f"Lawyer '{lawyer_id}' not found.")

    display = f"{lawyer['full_name']} ({lawyer['bar_license']}, {lawyer['city']})"
    note    = f"Manually assigned by admin: {lawyer['full_name']}"

    with _conn() as c:
        cur = c.execute(
            """UPDATE applications
               SET suggested_lawyer   = ?,
                   assigned_lawyer_id = ?,
                   notes              = ?,
                   status = CASE WHEN status = 'pending' THEN 'assigned' ELSE status END
               WHERE application_id = ?""",
            (display, lawyer_id, note, app_id),
        )

    if cur.rowcount > 0:
        try:
            increment_cases(lawyer_id)
        except Exception:
            pass
        return True
    return False


def assign_ngo(app_id: str, ngo_id: str) -> bool:
    """
    Admin override: assign a specific DB NGO to an application.
    Raises ValueError if ngo_id not found.
    """
    from utils.ngo_service import get_ngo

    ngo = get_ngo(ngo_id)
    if not ngo:
        raise ValueError(f"NGO '{ngo_id}' not found.")

    with _conn() as c:
        cur = c.execute(
            """UPDATE applications
               SET assigned_ngo    = ?,
                   assigned_ngo_id = ?
               WHERE application_id = ?""",
            (ngo["ngo_name"], ngo_id, app_id),
        )
    return cur.rowcount > 0


# ─────────────────────────────────────────────────────────────────────────────
# Routing explanation (Phase 3 Case Routing tab)
# ─────────────────────────────────────────────────────────────────────────────

def get_routing_explanation(app_id: str) -> dict:
    """
    Return a structured routing audit for a specific application.

    Returns dict with keys: application_id, case_type, city, urgency,
    assigned_ngo, assigned_ngo_id, ngo_source, assigned_lawyer,
    assigned_lawyer_id, lawyer_source, routing_note, confidence,
    expertise_mapped, ngo_category_mapped.

    confidence: "High" (both DB), "Medium" (one DB), "Low" (both static).
    Raises ValueError if app_id not found.
    """
    app = get_application(app_id)
    if not app:
        raise ValueError(f"Application '{app_id}' not found.")

    ngo_source    = "database" if app.get("assigned_ngo_id") else "static"
    lawyer_source = "database" if app.get("assigned_lawyer_id") else "static"

    if ngo_source == "database" and lawyer_source == "database":
        confidence = "High"
    elif ngo_source == "database" or lawyer_source == "database":
        confidence = "Medium"
    else:
        confidence = "Low"

    return {
        "application_id":      app["application_id"],
        "case_type":           app["case_type"],
        "city":                app["city"],
        "urgency":             app["urgency"],
        "assigned_ngo":        app.get("assigned_ngo", ""),
        "assigned_ngo_id":     app.get("assigned_ngo_id", ""),
        "ngo_source":          ngo_source,
        "assigned_lawyer":     app.get("suggested_lawyer", ""),
        "assigned_lawyer_id":  app.get("assigned_lawyer_id", ""),
        "lawyer_source":       lawyer_source,
        "routing_note":        app.get("notes", ""),
        "confidence":          confidence,
        "expertise_mapped": app["case_type"],
        "ngo_category_mapped": app["case_type"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Read + status helpers (unchanged API)
# ─────────────────────────────────────────────────────────────────────────────

def get_all_applications(
    order_by_priority: bool = True,
    filter_ngo: Optional[str] = None,
    filter_case_type: Optional[str] = None,
    filter_urgency: Optional[str] = None,
    filter_status: Optional[str] = None,
) -> list:
    sql    = "SELECT * FROM applications WHERE 1=1"
    params: list = []

    if filter_ngo:
        sql += " AND assigned_ngo = ?"
        params.append(filter_ngo)
    if filter_case_type:
        sql += " AND case_type = ?"
        params.append(filter_case_type)
    if filter_urgency:
        sql += " AND urgency = ?"
        params.append(filter_urgency)
    if filter_status:
        sql += " AND status = ?"
        params.append(filter_status)

    sql += " ORDER BY priority DESC, timestamp DESC" if order_by_priority \
           else " ORDER BY timestamp DESC"

    with _conn() as c:
        rows = c.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_application(app_id: str) -> Optional[dict]:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM applications WHERE application_id = ?", (app_id,)
        ).fetchone()
    return dict(row) if row else None


def update_status(app_id: str, status: str, notes: str = "") -> bool:
    valid = {"pending", "in_review", "assigned", "resolved", "closed"}
    if status not in valid:
        raise ValueError(f"Invalid status '{status}'. Must be one of {sorted(valid)}")
    with _conn() as c:
        cur = c.execute(
            "UPDATE applications SET status=?, notes=? WHERE application_id=?",
            (status, notes, app_id),
        )
    return cur.rowcount > 0


def reroute_application(app_id: str) -> dict:
    """
    Re-run deterministic routing for an existing application and update the DB.
    Returns the full routing result merged with the application_id.
    Raises ValueError if the application is not found.
    """
    app = get_application(app_id)
    if not app:
        raise ValueError(f"Application '{app_id}' not found.")

    from utils.routing_service import route_case
    routing = route_case(app["city"], app["case_type"], app["urgency"])

    ngo    = routing["ngo"]
    lawyer = routing["lawyer"]

    ngo_name       = ngo["ngo_name"]    if ngo    else ""
    ngo_id         = ngo["ngo_id"]      if ngo    else ""
    lawyer_display = (
        f"{lawyer['full_name']} ({lawyer['bar_license']}, {lawyer['city']})"
        if lawyer else ""
    )
    lawyer_id = lawyer["lawyer_id"] if lawyer else ""

    new_status = (
        "assigned" if (ngo_name or lawyer_display)
        else app.get("status", "pending")
    )

    with _conn() as c:
        c.execute(
            """UPDATE applications
               SET assigned_ngo       = ?,
                   assigned_ngo_id    = ?,
                   suggested_lawyer   = ?,
                   assigned_lawyer_id = ?,
                   notes              = ?,
                   status             = ?
               WHERE application_id   = ?""",
            (ngo_name, ngo_id, lawyer_display, lawyer_id,
             routing["reason"], new_status, app_id),
        )

    if lawyer_id and lawyer_id != app.get("assigned_lawyer_id", ""):
        try:
            from utils.lawyer_service import increment_cases
            increment_cases(lawyer_id)
        except Exception:
            pass

    return {**routing, "application_id": app_id, "status": new_status}


def get_stats() -> dict:
    with _conn() as c:
        total        = c.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        ngo_rows     = c.execute(
            "SELECT assigned_ngo, COUNT(*) as cnt FROM applications GROUP BY assigned_ngo"
        ).fetchall()
        urgency_rows = c.execute(
            "SELECT urgency, COUNT(*) as cnt FROM applications GROUP BY urgency"
        ).fetchall()
        status_rows  = c.execute(
            "SELECT status, COUNT(*) as cnt FROM applications GROUP BY status"
        ).fetchall()
        type_rows    = c.execute(
            "SELECT case_type, COUNT(*) as cnt FROM applications GROUP BY case_type"
        ).fetchall()

    return {
        "total":        total,
        "by_ngo":       {r["assigned_ngo"]: r["cnt"] for r in ngo_rows},
        "by_urgency":   {r["urgency"]: r["cnt"] for r in urgency_rows},
        "by_status":    {r["status"]: r["cnt"] for r in status_rows},
        "by_case_type": {r["case_type"]: r["cnt"] for r in type_rows},
    }