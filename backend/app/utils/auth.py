"""Server-validated, expiring sessions for administration and anonymous chat."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.utils.db import get_connection

_lock = threading.Lock()
_requests: dict[tuple[str, str], deque] = defaultdict(deque)


def init_auth() -> None:
    with get_connection() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS access_sessions (
            token_hash TEXT PRIMARY KEY, kind TEXT NOT NULL,
            session_id TEXT NOT NULL, expires_at REAL NOT NULL
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_access_expiry ON access_sessions(expires_at)")


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_session(kind: str, session_id: str = "") -> dict:
    token = secrets.token_urlsafe(32)
    session_id = session_id or secrets.token_hex(24)
    expires = time.time() + (8 * 3600 if kind == "admin" else 3600)
    with get_connection() as conn:
        conn.execute("DELETE FROM access_sessions WHERE expires_at <= ?", (time.time(),))
        conn.execute("INSERT INTO access_sessions VALUES (?, ?, ?, ?)",
                     (_digest(token), kind, session_id, expires))
    return {"token": token, "session_id": session_id, "expires_at": expires}


def verify_session(token: str, kind: str, session_id: str = "") -> bool:
    if not token or len(token) > 256:
        return False
    with get_connection() as conn:
        row = conn.execute(
            "SELECT session_id FROM access_sessions WHERE token_hash=? AND kind=? AND expires_at>?",
            (_digest(token), kind, time.time()),
        ).fetchone()
    return bool(row and (not session_id or hmac.compare_digest(row["session_id"], session_id)))


def revoke_session(token: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM access_sessions WHERE token_hash=?", (_digest(token),))


def check_password(password: str) -> bool:
    expected = os.getenv("ADMIN_PASSWORD", "")
    if not expected:
        raise HTTPException(503, "Administrator access is not configured. Set ADMIN_PASSWORD on the backend.")
    return hmac.compare_digest(password.encode(), expected.encode())


def require_chat_session(request: Request, session_id: str) -> None:
    if not verify_session(request.headers.get("X-Chat-Token", ""), "chat", session_id):
        raise HTTPException(401, "Chat session expired. Start a new conversation.")


def _rate_limit(request: Request, group: str, maximum: int) -> None:
    key = (request.client.host if request.client else "unknown", group)
    now = time.monotonic()
    with _lock:
        # Bound the accounting map as well as each per-client window.
        if len(_requests) > 10000:
            for old_key in list(_requests):
                if not _requests[old_key] or _requests[old_key][-1] < now - 60:
                    del _requests[old_key]
        window = _requests[key]
        while window and window[0] <= now - 60:
            window.popleft()
        if len(window) >= maximum:
            raise HTTPException(429, "Too many requests. Please retry in a minute.", headers={"Retry-After": "60"})
        window.append(now)


async def enforce_access(request: Request) -> None:
    path, method = request.url.path, request.method
    if path == "/api/admin/login":
        _rate_limit(request, "login", 10)
        return
    protected = (
        path.startswith(("/api/admin/", "/api/analytics/", "/api/routing/"))
        or (path.startswith("/api/applications") and not (path == "/api/applications" and method == "POST"))
        or (path.startswith(("/api/ngos", "/api/lawyers")) and (method != "GET" or path.endswith("/stats")))
    )
    if protected and not verify_session(request.headers.get("X-Admin-Token", ""), "admin"):
        raise HTTPException(401, "Administrator session required. Please sign in again.")
    if method == "POST" and path in {"/api/analyze", "/api/analyze-document", "/api/transcribe", "/api/tts", "/api/chat"}:
        _rate_limit(request, "processing", 30)
    if method == "POST" and path in {"/api/applications", "/api/chat/sessions", "/api/feedback", "/api/pdf"}:
        _rate_limit(request, "submission", 30)
