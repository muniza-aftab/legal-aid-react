"""
db.py — SQLite database helpers + schema bootstrap.

Owns:
  • users_logs       (anonymous query analytics — used by app.py)
  • feedback         (user thumbs-up/comment — used by app.py)
  • ngos             (admin-managed legal-aid NGOs — used by ngo_service.py)
  • lawyers          (admin-managed lawyer registry — used by lawyer_service.py)

Auto-migrates pre-existing databases idempotently:
  • CREATE TABLE IF NOT EXISTS  for table creation
  • PRAGMA table_info + ALTER TABLE  for new columns

Public exports:
  Functions:
      get_connection()    → sqlite3.Connection
      init_db()           → None  (call once at startup)
      log_query(...)      → int
      save_feedback(...)  → int
      fetch_all_logs()    → list[dict]
      fetch_all_feedback()→ list[dict]

  Constants used by the NGO/lawyer service modules:
      NGO_CATEGORIES      — list[str]   canonical NGO category list
      LAWYER_EXPERTISE_AREAS     — list[str]   canonical lawyer main-expertise list
      EXPERTISE_SUBAREAS       — dict[str, list[str]]
                            valid sub-specialisations per main expertise

Note on the `applications` table:
  That table is owned by utils/application_service.py for historical
  reasons (it predates this file's responsibilities). It is created by
  application_service.init_applications_table() at startup. This module
  does not touch it.
"""
from __future__ import annotations
import sqlite3
import os
from datetime import datetime

from app.utils.config import DB_PATH


# ─────────────────────────────────────────────────────────────────────────────
# Canonical reference lists
# ─────────────────────────────────────────────────────────────────────────────
# Imported by:
#   • utils/ngo_service.py     (validates NGO category field)
#   • utils/lawyer_service.py  (validates expertise_main + expertise_sub)
#   • pages/admin_dashboard.py (Phase 3 dropdowns)
#
# Keep these in sync with the case categories produced by groq_client.
# Free-text values are still acceptable in the database; the constraint
# is enforced at the service layer.

from app.utils.legal_taxonomy import (
    NGO_CATEGORIES,
    LAWYER_EXPERTISE_AREAS,
    EXPERTISE_SUBAREAS,
)

# ─────────────────────────────────────────────────────────────────────────────
# Connection helper
# ─────────────────────────────────────────────────────────────────────────────

class _Connection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def get_connection() -> sqlite3.Connection:
    """
    Open a SQLite connection with row_factory so cursors yield dict-like rows.
    Thread-safe (check_same_thread=False) because Streamlit reruns invoke
    DB calls from worker threads.
    """
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15, factory=_Connection)
    conn.row_factory = sqlite3.Row
    return conn


# ─────────────────────────────────────────────────────────────────────────────
# Schema bootstrap (idempotent)
# ─────────────────────────────────────────────────────────────────────────────

def init_db() -> None:
    """
    Create tables if they do not exist; add any missing columns to
    pre-existing tables. Safe to call repeatedly.

    Tables created here:
      • users_logs   — anonymous query analytics
      • feedback     — user thumbs/comment
      • ngos         — admin-managed NGO directory
      • lawyers      — admin-managed lawyer registry

    The applications table is created by application_service.py
    independently — see utils/application_service.init_applications_table().
    """
    conn = get_connection()
    cur  = conn.cursor()

    # ── users_logs + feedback (existing tables — unchanged) ──────────────────
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    NOT NULL,
            language    TEXT    NOT NULL,
            query_text  TEXT    NOT NULL,
            category    TEXT    DEFAULT '',
            risk_level  TEXT    DEFAULT '',
            ai_summary  TEXT    DEFAULT '',
            voice_used  INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT    NOT NULL,
            rating    INTEGER NOT NULL,
            comment   TEXT
        );
        """
    )

    # Migration: add any missing columns to a pre-existing users_logs.
    existing = {row["name"] for row in cur.execute("PRAGMA table_info(users_logs)")}
    for col, defn in [
        ("city",       "TEXT DEFAULT ''"),
        ("category",   "TEXT DEFAULT ''"),
        ("risk_level", "TEXT DEFAULT ''"),
        ("ai_summary", "TEXT DEFAULT ''"),
        ("voice_used", "INTEGER DEFAULT 0"),
    ]:
        if col not in existing:
            cur.execute(f"ALTER TABLE users_logs ADD COLUMN {col} {defn}")

    # ── ngos (Phase 1 — used by utils/ngo_service.py) ────────────────────────
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS ngos (
            ngo_id            TEXT    PRIMARY KEY,
            ngo_name          TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            category          TEXT    NOT NULL DEFAULT 'General / Other',
            categories        TEXT    NOT NULL DEFAULT '[]',
            city              TEXT    DEFAULT '',
            contact_email     TEXT    DEFAULT '',
            contact_phone     TEXT    DEFAULT '',
            handles_all_cases INTEGER NOT NULL DEFAULT 0,
            active            INTEGER NOT NULL DEFAULT 1,
            created_at        TEXT    NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_ngos_active   ON ngos(active);
        CREATE INDEX IF NOT EXISTS idx_ngos_category ON ngos(category);
        CREATE INDEX IF NOT EXISTS idx_ngos_city     ON ngos(city);
        """
    )

    existing_ngo_cols = {
        row["name"] for row in cur.execute("PRAGMA table_info(ngos)")
    }
    for col, defn in [
        ("ngo_name",          "TEXT    NOT NULL DEFAULT ''"),
        ("category",          "TEXT    NOT NULL DEFAULT 'General / Other'"),
        ("categories",        "TEXT    NOT NULL DEFAULT '[]'"),
        ("city",              "TEXT    DEFAULT ''"),
        ("contact_email",     "TEXT    DEFAULT ''"),
        ("contact_phone",     "TEXT    DEFAULT ''"),
        ("handles_all_cases", "INTEGER NOT NULL DEFAULT 0"),
        ("active",            "INTEGER NOT NULL DEFAULT 1"),
        ("created_at",        "TEXT    NOT NULL DEFAULT ''"),
    ]:
        if col not in existing_ngo_cols:
            cur.execute(f"ALTER TABLE ngos ADD COLUMN {col} {defn}")

    # ── lawyers (Phase 1 — used by utils/lawyer_service.py) ──────────────────
    # expertise_sub is stored as a comma-separated string at the DB layer;
    # the service module (lawyer_service.py) converts to/from list[str].
    # ngo_id is a TEXT foreign-key reference to ngos.ngo_id; SQLite does not
    # enforce FK constraints unless explicitly enabled, but the service
    # layer validates it on insert.
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS lawyers (
            lawyer_id       TEXT    PRIMARY KEY,
            full_name       TEXT    NOT NULL,
            bar_license     TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            ngo_id          TEXT    DEFAULT '',
            city            TEXT    DEFAULT '',
            expertise_main  TEXT    NOT NULL,
            expertise_sub   TEXT    DEFAULT '',
            active_cases    INTEGER NOT NULL DEFAULT 0,
            available       INTEGER NOT NULL DEFAULT 1,
            created_at      TEXT    NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_lawyers_ngo        ON lawyers(ngo_id);
        CREATE INDEX IF NOT EXISTS idx_lawyers_main       ON lawyers(expertise_main);
        CREATE INDEX IF NOT EXISTS idx_lawyers_available  ON lawyers(available);
        CREATE INDEX IF NOT EXISTS idx_lawyers_city       ON lawyers(city);
        """
    )

    existing_lawyer_cols = {
        row["name"] for row in cur.execute("PRAGMA table_info(lawyers)")
    }
    for col, defn in [
        ("full_name",      "TEXT    NOT NULL DEFAULT ''"),
        ("bar_license",    "TEXT    NOT NULL DEFAULT ''"),
        ("ngo_id",         "TEXT    DEFAULT ''"),
        ("city",           "TEXT    DEFAULT ''"),
        ("expertise_main", "TEXT    NOT NULL DEFAULT ''"),
        ("expertise_sub",  "TEXT    DEFAULT ''"),
        ("active_cases",   "INTEGER NOT NULL DEFAULT 0"),
        ("available",      "INTEGER NOT NULL DEFAULT 1"),
        ("created_at",     "TEXT    NOT NULL DEFAULT ''"),
    ]:
        if col not in existing_lawyer_cols:
            cur.execute(f"ALTER TABLE lawyers ADD COLUMN {col} {defn}")

    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# users_logs helpers
# ─────────────────────────────────────────────────────────────────────────────

def log_query(
    language: str,
    query_text: str,
    category: str = "",
    risk_level: str = "",
    ai_summary: str = "",
    voice_used: bool = False,
    city: str = "",
) -> int:
    """Insert one anonymous query-log row. Returns the new row id."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        """INSERT INTO users_logs
           (timestamp, language, query_text, category,
            risk_level, ai_summary, voice_used, city)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            datetime.utcnow().isoformat(sep=" "),
            language,
            query_text if os.getenv("STORE_QUERY_TEXT", "false").lower() == "true" else "",
            category,
            risk_level,
            ai_summary[:300] if os.getenv("STORE_QUERY_TEXT", "false").lower() == "true" else "",
            int(voice_used),
            city,
        ),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def save_feedback(rating: int, comment: str = "", session_id: str = "") -> int:
    """Insert one feedback row. Returns the new row id."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "INSERT INTO feedback (timestamp, rating, comment) VALUES (?, ?, ?)",
        (datetime.utcnow().isoformat(sep=" "), rating, comment),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def fetch_all_logs() -> list:
    """Return every users_logs row, newest first, as list[dict]."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM users_logs ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_all_feedback() -> list:
    """Return every feedback row, newest first, as list[dict]."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM feedback ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
