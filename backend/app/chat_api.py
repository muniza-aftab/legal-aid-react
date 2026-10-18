"""
chat_api.py — REST API endpoint for the conversational chat feature.

Exposes:
    POST /chat      → multi-turn legal chat grounded in RAG
    DELETE /chat    → clear a session's history
    GET  /chat/health → liveness check

Run standalone (development):
    uvicorn chat_api:app --reload --port 8000

Or mount into an existing FastAPI/Starlette app:
    from chat_api import app as chat_app
    parent_app.mount("/api", chat_app)

Dependencies (add to requirements.txt if not present):
    fastapi>=0.111.0
    uvicorn>=0.29.0
"""
from __future__ import annotations

import logging
import os
import sys
import time
from typing import Optional

# Ensure project root is on sys.path when run directly
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.utils.chat_service import (
    chat,
    clear_session,
    get_or_create_session,
    get_recent_history,
    ChatResponse,
    SourceDoc,
)
from app.utils.config import GROQ_API_KEY

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("chat_api")

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Pakistan AI Legal Aid — Chat API",
    description=(
        "Multi-turn conversational legal assistant. "
        "Every response is grounded in retrieved Pakistani law documents (RAG). "
        "Groq LLM is used only for language generation — not as a knowledge source."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Allow cross-origin requests so the Streamlit frontend can call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # restrict to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request / Response schemas ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Unique identifier for the user session.",
        examples=["user-abc123"],
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The user's legal question or follow-up message.",
        examples=["My employer has not paid my salary for 3 months. What can I do?"],
    )
    language: str = Field(
        default="English",
        description="Response language. Supported: 'English', 'Urdu'.",
        examples=["English"],
    )

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        allowed = {"English", "Urdu"}
        if v not in allowed:
            raise ValueError(f"language must be one of {sorted(allowed)}")
        return v

    @field_validator("session_id")
    @classmethod
    def sanitize_session_id(cls, v: str) -> str:
        # Prevent path-traversal or injection via session_id
        import re
        if not re.match(r'^[\w\-]{1,128}$', v):
            raise ValueError(
                "session_id may only contain letters, digits, hyphens, and underscores."
            )
        return v


class SourceDocSchema(BaseModel):
    """Structured, traceable source document returned with every reply."""
    title:   str   = Field(..., description="Exact law name from the retrieved document.")
    section: str   = Field("",  description="Section identifier, if available.")
    snippet: str   = Field(..., description="First 200 characters of the retrieved passage.")
    score:   float = Field(..., description="Cosine-similarity score (0–1). Always ≥ 0.50.")


class ChatApiResponse(BaseModel):
    reply:      str                  = Field(..., description="The grounded legal response.")
    sources:    list[SourceDocSchema] = Field(..., description="Traceable retrieved law passages.")
    confidence: str                  = Field(..., description="Retrieval confidence: high | medium | low")
    session_id: str                  = Field(..., description="Echo of the session_id.")
    error:      Optional[str]        = Field(None, description="Error code if something went wrong.")


class ClearRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)


class HealthResponse(BaseModel):
    status:      str
    rag_ready:   bool
    groq_ready:  bool
    timestamp:   float


# ── Startup check ─────────────────────────────────────────────────────────────

@app.on_event("startup")
async def _startup() -> None:
    from app.utils.rag_engine import index_ready
    rag_ok  = index_ready()
    groq_ok = bool(GROQ_API_KEY)
    logger.info("Chat API starting. RAG ready=%s  Groq ready=%s", rag_ok, groq_ok)
    if not rag_ok:
        logger.warning(
            "FAISS index not found! Run `python build_index.py` before using the chat API."
        )
    if not groq_ok:
        logger.warning("GROQ_API_KEY is not set. Chat calls will fail.")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post(
    "/chat",
    response_model=ChatApiResponse,
    summary="Send a message and get a RAG-grounded legal response",
    responses={
        200: {"description": "Successful response"},
        422: {"description": "Validation error"},
        503: {"description": "RAG index not ready"},
    },
)
async def post_chat(request: ChatRequest) -> ChatApiResponse:
    """
    Multi-turn legal chat endpoint.

    Pipeline (enforced on every call):
    1. Validate + sanitize the user message
    2. MANDATORY: retrieve relevant law chunks from FAISS RAG index
    3. Combine context + session history + query into a grounded prompt
    4. Call Groq LLM — constrained to only rephrase retrieved content
    5. Persist exchange in session memory
    6. Return reply + law sources + confidence score

    If the RAG index returns no results, the endpoint returns an explicit
    "insufficient information" message — the LLM is NOT called.
    """
    from app.utils.rag_engine import index_ready

    # Guard: RAG must be available
    if not index_ready():
        raise HTTPException(
            status_code=503,
            detail=(
                "The legal document index is not ready. "
                "Please run `python build_index.py` first."
            ),
        )

    logger.info(
        "Chat [%s] (%s): %.80s…",
        request.session_id, request.language, request.message,
    )

    result: ChatResponse = chat(
        session_id=request.session_id,
        message=request.message,
        language=request.language,
    )

    # Serialise SourceDoc dataclasses → Pydantic schema (handles empty list safely)
    serialised_sources = [
        SourceDocSchema(
            title=s.title,
            section=s.section,
            snippet=s.snippet,
            score=s.score,
        )
        for s in result.sources
    ]

    return ChatApiResponse(
        reply=result.reply,
        sources=serialised_sources,
        confidence=result.confidence,
        session_id=result.session_id,
        error=result.error,
    )


@app.delete(
    "/chat",
    summary="Clear a session's conversation history",
)
async def delete_chat(request: ClearRequest) -> dict:
    """Wipe the stored history for a given session_id."""
    clear_session(request.session_id)
    return {"cleared": True, "session_id": request.session_id}


@app.get(
    "/chat/history",
    summary="Retrieve the conversation history for a session",
)
async def get_history(session_id: str, turns: int = 5) -> dict:
    """Return the last `turns` exchanges for debugging / display purposes."""
    import re
    if not re.match(r'^[\w\-]{1,128}$', session_id):
        raise HTTPException(status_code=422, detail="Invalid session_id format.")
    turns = max(1, min(turns, 20))   # clamp to 1–20
    history = get_recent_history(session_id, n=turns)
    return {"session_id": session_id, "history": history}


@app.get(
    "/chat/health",
    response_model=HealthResponse,
    summary="Liveness + readiness check",
)
async def health_check() -> HealthResponse:
    """Returns the operational status of the RAG index and Groq connection."""
    from app.utils.rag_engine import index_ready
    return HealthResponse(
        status="ok",
        rag_ready=index_ready(),
        groq_ready=bool(GROQ_API_KEY),
        timestamp=time.time(),
    )


# ── Global error handler ──────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def _global_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error in chat_api: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {type(exc).__name__}"},
    )


# ── Dev entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("chat_api:app", host="0.0.0.0", port=8000, reload=True)
