"""
main.py — Pakistan AI Legal Aid Assistant · React Backend API
FastAPI server that wraps all existing Python services into REST endpoints.
The existing utils/ logic is reused as-is. This file is purely a thin API layer.
"""
from __future__ import annotations
import asyncio
import functools
import logging
import os
import re as _re
import sys
import time
import uuid
from typing import Optional, List

# Ensure backend app is on path
ROOT = os.path.dirname(os.path.abspath(__file__))
APP  = os.path.join(ROOT, "app")
for p in [ROOT, APP]:
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
logging.getLogger("transformers").setLevel(logging.ERROR)

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("main")

# ── Document analysis constants ────────────────────────────────────────────────
_ANALYSIS_TIMEOUT_SECS = 120          # hard wall-clock limit for the full pipeline
_MIN_TEXT_FOR_ANALYSIS = 20           # chars; below this, skip LLM and return null
_NULL_BYTE_PAT         = _re.compile(r'\x00+')
_CTRL_CHAR_PAT         = _re.compile(r'[\x01-\x08\x0B\x0C\x0E-\x1F\x7F]')


def _sanitize_doc_text(text: str) -> str:
    """Strip null bytes and stray control characters from extracted document text."""
    text = _NULL_BYTE_PAT.sub('', text)
    text = _CTRL_CHAR_PAT.sub('', text)
    return text

# ── Bootstrap DB ──────────────────────────────────────────────────────────────
from app.utils.db import init_db
from app.utils.application_service import init_applications_table
init_db()
init_applications_table()

# ── Import services ────────────────────────────────────────────────────────────
from app.utils.config import (
    GROQ_API_KEY, ELEVENLABS_API_KEY, APP_TITLE, APP_VERSION,
    PAKISTAN_CITIES, LANGUAGES, DISCLAIMER, EMERGENCY_CONTACTS,
)
from app.utils.groq_client import (
    analyze_with_rag, LegalAnalysis, transcribe_audio,
    analyze_document_with_rag, DocumentAnalysis,
)
from app.utils.rag_engine  import retrieve, index_ready, index_stats, preprocess_query
from app.utils.embeddings  import get_model
from app.utils.ngo_matcher import recommend_ngos, get_urgent_helplines
from app.utils.validator   import sanitize, ValidationError
from app.utils.tts         import generate_tts, tts_available
from app.utils.pdf_generator import generate_case_pdf
from app.utils.chat_service  import (
    chat as chat_service,
    clear_session, get_or_create_session, get_recent_history,
    ChatResponse, SourceDoc,
)
from app.utils.application_service import (
    submit_application, get_all_applications, get_application,
    update_status, get_stats, assign_lawyer, assign_ngo, get_routing_explanation,
    reroute_application,
    CASE_TYPES, URGENCY_LEVELS,
)
from app.utils.routing_service import (
    route_case as _route_case,
    get_candidate_lawyers,
)
from app.utils.ngo_service import (
    add_ngo, update_ngo, delete_ngo, deactivate_ngo, reactivate_ngo,
    get_all_ngos, get_ngo, get_ngo_stats,
)
from app.utils.lawyer_service import (
    add_lawyer, update_lawyer, delete_lawyer, set_availability,
    get_all_lawyers, get_lawyer, get_lawyers_for_ngo, get_lawyer_stats,
)
from app.utils.db import log_query, save_feedback, fetch_all_logs, fetch_all_feedback
from app.utils.translations import T
from app.utils.document_loader     import load_upload, cleanup_temp, TempDocument
from app.utils.text_extractor      import extract_text
from app.utils.document_classifier import classify_document
from app.utils.legal_taxonomy import (
    LEGAL_CASE_TYPES, URGENCY_LEVELS, NGO_CATEGORIES,
    LAWYER_EXPERTISE_AREAS, EXPERTISE_SUBAREAS,
)

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Pakistan AI Legal Aid — API",
    description="React frontend API layer wrapping the existing Python services.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://legal-aid-react-gvvenv4go-muniza-aftab-s-projects.vercel.app", "https://legal-aid-react.vercel.app", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _warmup_rag() -> None:
    """
    The embedding model and FAISS index are normally loaded lazily on first
    use, which makes whichever request happens to arrive first pay a multi-
    second loading cost synchronously. Load them here instead, before the
    server starts accepting traffic, so every request is fast from the start.
    """
    try:
        get_model()
        index_stats()
        logger.info("RAG warmup complete — embedding model and FAISS index pre-loaded.")
    except Exception as e:
        logger.warning(f"RAG warmup skipped (will lazy-load on first request instead): {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class AnalyzeRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    language: str = Field(default="English")
    city: str = Field(default="")

class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    message: str    = Field(..., min_length=1, max_length=2000)
    language: str   = Field(default="English")
    case_context: dict = Field(default_factory=dict)

    @field_validator("session_id")
    @classmethod
    def validate_sid(cls, v):
        import re
        if not re.match(r'^[\w\-]{1,128}$', v):
            raise ValueError("Invalid session_id")
        return v

class FeedbackRequest(BaseModel):
    session_id: str
    rating: int  # 1-5
    comment: str = ""

class ApplicationRequest(BaseModel):
    full_name: str
    cnic: str = ""
    phone: str = ""
    email: str = ""
    city: str = ""
    case_type: str
    urgency: str
    description: str
    language: str = "English"

class StatusUpdateRequest(BaseModel):
    status: str

class AssignLawyerRequest(BaseModel):
    lawyer_id: str

class AssignNGORequest(BaseModel):
    ngo_id: str

class NGOCreateRequest(BaseModel):
    name: str
    city: str = ""
    contact: str = ""
    email: str = ""
    categories: List[str] = []
    handles_all_cases: bool = False
    active: bool = True

class LawyerCreateRequest(BaseModel):
    full_name: str
    bar_license: str
    city: str
    expertise_main: str
    ngo_id: str = ""
    available: bool = True

class SetAvailabilityRequest(BaseModel):
    available: bool


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH / CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "rag_ready": index_ready(),
        "groq_ready": bool(GROQ_API_KEY),
        "tts_ready": tts_available(),
        "timestamp": time.time(),
        "version": APP_VERSION,
    }

@app.get("/api/config")
async def config():
    return {
        "app_title": APP_TITLE,
        "app_version": APP_VERSION,
        "languages": LANGUAGES,
        "cities": PAKISTAN_CITIES,
        "case_types": CASE_TYPES,
        "urgency_levels": URGENCY_LEVELS,
        "ngo_categories": NGO_CATEGORIES,
        "lawyer_expertise": LAWYER_EXPERTISE_AREAS,
        "expertise_subareas": EXPERTISE_SUBAREAS,
        "disclaimer": DISCLAIMER,
        "emergency_contacts": EMERGENCY_CONTACTS,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# LEGAL ANALYSIS (RAG)
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    try:
        clean = sanitize(req.query)
    except ValidationError as ve:
        raise HTTPException(status_code=422, detail=str(ve))

    if not index_ready():
        raise HTTPException(status_code=503, detail="RAG index not ready. Run build_index.py first.")

    # Retrieve + analyze — both are blocking calls (FAISS search + sentence
    # encoding, then a synchronous Groq HTTP request with retry sleeps), so run
    # them in a thread executor to avoid stalling the event loop / other requests.
    loop = asyncio.get_running_loop()
    retrieval_q = preprocess_query(clean)
    chunks = await loop.run_in_executor(None, retrieve, retrieval_q)

    # Analyze
    result: LegalAnalysis = await loop.run_in_executor(
        None, functools.partial(analyze_with_rag, clean, chunks, language=req.language)
    )

    if result.error:
        raise HTTPException(status_code=500, detail=result.error)

    # Log
    try:
        log_query(
            language=req.language,
            query_text=clean,
            category=result.category,
            risk_level=result.risk_level,
            ai_summary=result.summary[:300] if result.summary else "",
            voice_used=False,
        )
    except Exception:
        pass

    # NGOs shown to real users always come from the verified ngos.json list
    # (NOT the admin-managed DB table, which only ever holds dummy/test data
    # entered through the Admin panel — see ngo_matcher.py "AUTHORITATIVE" note).
    static = recommend_ngos(result.category, city=req.city, max_results=3, risk_level=result.risk_level)
    ngo_list = [
        {"name": n.get("name",""), "category": n.get("category",""), "city": n.get("city",""),
         "phone": n.get("phone",""), "email": n.get("email",""),
         "website": n.get("website",""), "description": n.get("description","")}
        for n in (static or [])
    ]

    urgent = get_urgent_helplines(result.category, result.risk_level)

    return {
        "category": result.category,
        "risk_level": result.risk_level,
        "risk_reason": result.risk_reason,
        "confidence": result.confidence,
        "summary": result.summary,
        "laws": result.laws or [],
        "rights": result.rights or [],
        "next_steps": result.next_steps or [],
        # Only surface retrieved chunks as sources when the analysis actually cited
        # laws from them — otherwise (e.g. greetings, non-legal queries) the chunks
        # were never grounding anything and showing them is misleading.
        "sources": [
            {
                "law_name": c.get("law_name", ""),
                "section": c.get("section", ""),
                "category": c.get("category", ""),
                "text": c.get("text", "")[:400],
                "score": c.get("score", 0),
            }
            for c in (chunks or [])
        ] if result.laws else [],
        "ngos": ngo_list,
        "urgent_helplines": urgent or [],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CHAT (multi-turn RAG)
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not index_ready():
        raise HTTPException(status_code=503, detail="RAG index not ready.")

    get_or_create_session(req.session_id)

    # chat_service runs RAG retrieval + a synchronous Groq HTTP call — offload it
    # to a thread so a slow LLM response doesn't stall the whole event loop.
    loop = asyncio.get_running_loop()
    result: ChatResponse = await loop.run_in_executor(
        None,
        functools.partial(
            chat_service,
            session_id=req.session_id,
            message=req.message,
            language=req.language,
            case_context=req.case_context,
        ),
    )
    return {
        "reply": result.reply,
        "confidence": result.confidence,
        "session_id": result.session_id,
        "sources": [
            {"title": s.title, "section": s.section, "snippet": s.snippet, "score": s.score}
            for s in result.sources
        ],
        "error": result.error,
    }

@app.delete("/api/chat/{session_id}")
async def clear_chat(session_id: str):
    clear_session(session_id)
    return {"cleared": True, "session_id": session_id}

@app.get("/api/chat/{session_id}/history")
async def chat_history(session_id: str, turns: int = Query(default=10, le=50)):
    history = get_recent_history(session_id, n=turns)
    return {"session_id": session_id, "history": history}


# ═══════════════════════════════════════════════════════════════════════════════
# TRANSCRIPTION (Whisper via Groq)
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    language: str = Form(default="English"),
):
    audio_bytes = await audio.read()
    text, error = transcribe_audio(audio_bytes, language=language)
    if error:
        raise HTTPException(status_code=500, detail=error)
    return {"text": text, "language": language}


# ═══════════════════════════════════════════════════════════════════════════════
# TTS (Text-to-Speech)
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/tts")
async def tts(body: dict):
    text = body.get("text", "")
    language = body.get("language", "English")
    if not text:
        raise HTTPException(status_code=422, detail="text is required")
    if not tts_available():
        raise HTTPException(status_code=503, detail="TTS not available")

    # generate_tts can fall through ElevenLabs → espeak-ng → gTTS, each a blocking
    # network/subprocess call with its own timeout — run off the event loop so a
    # slow/unreachable backend doesn't freeze the whole server.
    loop = asyncio.get_running_loop()
    path = await loop.run_in_executor(None, generate_tts, text, language)
    if not path:
        raise HTTPException(status_code=500, detail="TTS generation failed")
    return FileResponse(path, media_type="audio/mpeg", filename="speech.mp3")


# ═══════════════════════════════════════════════════════════════════════════════
# PDF GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/pdf")
async def generate_pdf(body: dict):
    """Generate a case PDF from analysis result data."""
    language = body.get("language", "English")
    # Reconstruct LegalAnalysis from dict
    result = LegalAnalysis(
        category=body.get("category", ""),
        risk_level=body.get("risk_level", ""),
        risk_reason=body.get("risk_reason", ""),
        confidence=body.get("confidence", ""),
        summary=body.get("summary", ""),
        laws=body.get("laws", []),
        rights=body.get("rights", []),
        next_steps=body.get("next_steps", []),
    )
    path = generate_case_pdf(result, language)
    if not path:
        raise HTTPException(status_code=500, detail="PDF generation failed")
    return FileResponse(path, media_type="application/pdf", filename="legal_report.pdf")


# ═══════════════════════════════════════════════════════════════════════════════
# APPLICATIONS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/applications")
async def create_application(req: ApplicationRequest):
    # Map Pydantic field names → the names submit_application() expects
    data = {
        "name":        req.full_name.strip(),
        "contact":     req.phone.strip(),
        "email":       req.email.strip() if req.email else "",
        "cnic":        req.cnic.strip()  if req.cnic  else "",
        "city":        req.city.strip(),
        "case_type":   req.case_type.strip(),
        "urgency":     req.urgency.strip(),
        "description": req.description.strip(),
        "language":    req.language,
    }
    try:
        application = submit_application(data)
        # Expose app_id at top level so the frontend success screen can display it
        return {"success": True, "app_id": application["application_id"], **application}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Application submission failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Submission failed. Please try again.")

@app.get("/api/applications")
async def list_applications(
    status: str = Query(default=""),
    case_type: str = Query(default=""),
    urgency: str = Query(default=""),
    city: str = Query(default=""),
    limit: int = Query(default=100),
    offset: int = Query(default=0),
):
    apps = get_all_applications(
        filter_status=status or None,
        filter_case_type=case_type or None,
        filter_urgency=urgency or None,
    )
    total = len(apps)
    apps = apps[offset: offset + limit] if limit else apps
    return {"applications": apps, "total": total}

@app.get("/api/applications/stats")
async def application_stats():
    return get_stats()

@app.get("/api/applications/{app_id}")
async def get_application_detail(app_id: str):
    app = get_application(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app

@app.patch("/api/applications/{app_id}/status")
async def update_application_status(app_id: str, req: StatusUpdateRequest):
    ok = update_status(app_id, req.status)
    if not ok:
        raise HTTPException(status_code=404, detail="Application not found or update failed")
    return {"updated": True}

@app.patch("/api/applications/{app_id}/lawyer")
async def assign_application_lawyer(app_id: str, req: AssignLawyerRequest):
    ok = assign_lawyer(app_id, req.lawyer_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Assignment failed")
    return {"assigned": True}

@app.patch("/api/applications/{app_id}/ngo")
async def assign_application_ngo(app_id: str, req: AssignNGORequest):
    ok = assign_ngo(app_id, req.ngo_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Assignment failed")
    return {"assigned": True}

@app.get("/api/applications/{app_id}/routing")
async def application_routing(app_id: str):
    return get_routing_explanation(app_id)

@app.post("/api/applications/{app_id}/reroute")
async def reroute_application_endpoint(app_id: str):
    try:
        result = reroute_application(app_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Reroute failed for %s: %s", app_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/routing/preview")
async def routing_preview(
    city: str = Query(...),
    case_type: str = Query(...),
    urgency: str = Query(default="Medium"),
):
    try:
        return _route_case(city, case_type, urgency)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# NGO REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/ngos")
async def list_ngos(city: str = Query(default=""), category: str = Query(default="")):
    ngos = get_all_ngos(city_filter=city or None, category_filter=category or None)
    return {"ngos": ngos, "total": len(ngos)}

@app.get("/api/ngos/stats")
async def ngo_stats():
    return get_ngo_stats()

@app.get("/api/ngos/{ngo_id}")
async def get_ngo_detail(ngo_id: str):
    ngo = get_ngo(ngo_id)
    if not ngo:
        raise HTTPException(status_code=404, detail="NGO not found")
    return ngo

@app.post("/api/ngos")
async def create_ngo(req: NGOCreateRequest):
    data = {
        "ngo_name":          req.name,
        "categories":        req.categories,
        "city":              req.city,
        "contact_phone":     req.contact,
        "contact_email":     req.email,
        "handles_all_cases": req.handles_all_cases,
        "active":            req.active,
    }
    try:
        record = add_ngo(data)
        return {"success": True, **record}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Failed to create NGO: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create NGO")

@app.put("/api/ngos/{ngo_id}")
async def update_ngo_detail(ngo_id: str, req: NGOCreateRequest):
    data = {
        "ngo_name":          req.name,
        "categories":        req.categories,
        "city":              req.city,
        "contact_phone":     req.contact,
        "contact_email":     req.email,
        "handles_all_cases": req.handles_all_cases,
        "active":            req.active,
    }
    try:
        ok = update_ngo(ngo_id, data)
        if not ok:
            raise HTTPException(status_code=404, detail="NGO not found")
        return {"success": True, "ngo_id": ngo_id}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@app.delete("/api/ngos/{ngo_id}")
async def delete_ngo_endpoint(ngo_id: str):
    ok = delete_ngo(ngo_id)
    if not ok:
        raise HTTPException(status_code=404, detail="NGO not found")
    return {"deleted": True}

@app.patch("/api/ngos/{ngo_id}/deactivate")
async def deactivate_ngo_endpoint(ngo_id: str):
    ok = deactivate_ngo(ngo_id)
    return {"deactivated": ok}

@app.patch("/api/ngos/{ngo_id}/reactivate")
async def reactivate_ngo_endpoint(ngo_id: str):
    ok = reactivate_ngo(ngo_id)
    return {"reactivated": ok}


# ═══════════════════════════════════════════════════════════════════════════════
# LAWYER REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/lawyers")
async def list_lawyers():
    lawyers = get_all_lawyers()
    return {"lawyers": lawyers, "total": len(lawyers)}

@app.get("/api/lawyers/stats")
async def lawyer_stats():
    return get_lawyer_stats()

@app.get("/api/lawyers/{lawyer_id}")
async def get_lawyer_detail(lawyer_id: str):
    lawyer = get_lawyer(lawyer_id)
    if not lawyer:
        raise HTTPException(status_code=404, detail="Lawyer not found")
    return lawyer

@app.post("/api/lawyers")
async def create_lawyer(req: LawyerCreateRequest):
    try:
        record = add_lawyer(req.model_dump())
        return {"success": True, **record}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Failed to create lawyer: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create lawyer")

@app.put("/api/lawyers/{lawyer_id}")
async def update_lawyer_detail(lawyer_id: str, req: LawyerCreateRequest):
    try:
        ok = update_lawyer(lawyer_id, req.model_dump())
        if not ok:
            raise HTTPException(status_code=404, detail="Lawyer not found")
        return {"success": True, "lawyer_id": lawyer_id}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@app.delete("/api/lawyers/{lawyer_id}")
async def delete_lawyer_endpoint(lawyer_id: str):
    ok = delete_lawyer(lawyer_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Lawyer not found")
    return {"deleted": True}

@app.patch("/api/lawyers/{lawyer_id}/availability")
async def set_lawyer_availability(lawyer_id: str, req: SetAvailabilityRequest):
    ok = set_availability(lawyer_id, req.available)
    return {"updated": ok}


# ═══════════════════════════════════════════════════════════════════════════════
# ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/analytics/queries")
async def analytics_queries(limit: int = Query(default=500)):
    logs = fetch_all_logs()
    return {"logs": logs[:limit], "total": len(logs)}

@app.get("/api/analytics/feedback")
async def analytics_feedback():
    fb = fetch_all_feedback()
    return {"feedback": fb, "total": len(fb)}

@app.get("/api/analytics/summary")
async def analytics_summary():
    logs = fetch_all_logs()
    stats = get_stats()

    # Category breakdown
    from collections import Counter
    cats   = Counter(l.get("category", "Unknown") for l in logs)
    risks  = Counter(l.get("risk_level", "Unknown") for l in logs)
    langs  = Counter(l.get("language", "Unknown") for l in logs)
    cities = Counter(l.get("city", "Unknown") for l in logs if l.get("city"))

    return {
        "total_queries": len(logs),
        "categories": dict(cats.most_common(10)),
        "risk_levels": dict(risks),
        "languages": dict(langs),
        "cities": dict(cities.most_common(8)),
        "application_stats": stats,
    }

@app.post("/api/feedback")
async def submit_feedback(req: FeedbackRequest):
    try:
        save_feedback(session_id=req.session_id, rating=req.rating, comment=req.comment)
        return {"saved": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN AUTH (simple password check — stateless)
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/admin/login")
async def admin_login(body: dict):
    password = body.get("password", "")
    expected = os.getenv("ADMIN_PASSWORD", "admin123")
    if password == expected:
        return {"authenticated": True, "token": "admin-session-" + str(uuid.uuid4())}
    raise HTTPException(status_code=401, detail="Invalid password")


# ═══════════════════════════════════════════════════════════════════════════════
# DOCUMENT ANALYSIS — extraction + classification + RAG-grounded Groq analysis
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/analyze-document")
async def analyze_document(
    file: UploadFile = File(...),
    language: str    = Form(default="English"),
):
    """
    Accept a PDF, DOCX, PNG, or JPG upload and return the extracted raw text
    with language detection and extraction confidence.

    Response fields:
        filename              — original upload filename
        file_type             — "pdf" | "docx" | "image"
        size_bytes            — raw upload size in bytes
        extracted_text        — cleaned plain text (UTF-8; Urdu preserved as Unicode)
        detected_language     — "English" | "Urdu" | "Mixed" | "Unknown"
        extraction_confidence — 0.0 – 1.0 quality heuristic
        char_count            — character count of extracted_text
        word_count            — whitespace-token count
        pages                 — page count (0 for DOCX; 1 for images)
        method                — "pdf_text" | "pdf_pdfplumber" | "docx_text" |
                                "ocr" | "ocr_unavailable"
        preprocessing_steps   — OpenCV steps applied to images (empty list for non-image)
        warning               — non-fatal advisory message, or null
        document_type         — classified type: "Legal Notice" | "FIR" | "Court Order" |
                                "Rent Agreement" | "Employment Contract" | "Unknown"
        document_type_confidence — 0.0 – 1.0 classification confidence
        classification_method — "rule_based" | "llm" | "rule_based+llm_confirm"
        matched_rules         — list of matched rule display names
        legal_analysis        — RAG+Groq structured analysis; null if Groq unavailable.
                                Fields: summary, key_legal_points, deadlines,
                                procedural_guidance, risk_indicators, cited_laws,
                                urdu_explanation, confidence, disclaimer, error
    """
    doc: TempDocument | None = None
    result        = None
    classification = None
    doc_analysis   = None
    clean_text     = ""

    try:
        # ── File validation + upload (sync I/O; runs in async context safely) ──
        doc = await load_upload(file)

        # ── Run the blocking pipeline in a thread executor with a timeout ──────
        loop = asyncio.get_running_loop()

        async def _run_pipeline() -> tuple:
            # 1. Extract text from the uploaded file
            _result = await loop.run_in_executor(
                None, extract_text, doc.tmp_path, doc.file_type
            )

            # 2. Sanitize before any downstream processing
            _clean = _sanitize_doc_text(_result.text)

            # 3. Classify document type (even on short text — rules still apply)
            _cls = await loop.run_in_executor(
                None, classify_document, _clean, _result.detected_language
            )

            # 4. Skip LLM analysis when extracted text is too short to be meaningful
            if len(_clean) < _MIN_TEXT_FOR_ANALYSIS:
                logger.warning(
                    "analyze-document: text too short for analysis (%d chars < %d) — "
                    "skipping LLM: %s",
                    len(_clean), _MIN_TEXT_FOR_ANALYSIS, doc.filename,
                )
                return _result, _clean, _cls, None  # legal_analysis → null

            # 5. RAG + Groq analysis
            _analysis = await loop.run_in_executor(
                None, analyze_document_with_rag,
                _clean, _cls.document_type, _result.detected_language, language,
            )
            return _result, _clean, _cls, _analysis

        try:
            result, clean_text, classification, doc_analysis = await asyncio.wait_for(
                _run_pipeline(), timeout=_ANALYSIS_TIMEOUT_SECS
            )
        except asyncio.TimeoutError:
            logger.error(
                "analyze-document timed out after %ds: %s",
                _ANALYSIS_TIMEOUT_SECS, doc.filename if doc else "unknown",
            )
            raise HTTPException(
                status_code=504,
                detail=(
                    f"Document analysis timed out after {_ANALYSIS_TIMEOUT_SECS} seconds. "
                    "Please try a smaller file or retry later."
                ),
            )

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("analyze-document failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Document processing failed.")
    finally:
        if doc:
            cleanup_temp(doc.tmp_path)

    # Build legal_analysis payload — None when analysis was deliberately skipped
    legal_analysis_payload: dict | None = None
    if doc_analysis is not None:
        legal_analysis_payload = {
            "summary":             doc_analysis.summary,
            "key_legal_points":    doc_analysis.key_legal_points,
            "deadlines":           doc_analysis.deadlines,
            "procedural_guidance": doc_analysis.procedural_guidance,
            "risk_indicators":     doc_analysis.risk_indicators,
            "cited_laws":          doc_analysis.cited_laws,
            "urdu_explanation":    doc_analysis.urdu_explanation,
            "confidence":          doc_analysis.confidence,
            "disclaimer":          doc_analysis.disclaimer,
            "error":               doc_analysis.error,
        }

    return {
        "filename":                  doc.filename,
        "file_type":                 doc.file_type,
        "size_bytes":                doc.size_bytes,
        "extracted_text":            result.text,
        "detected_language":         result.detected_language,
        "extraction_confidence":     round(result.extraction_confidence, 3),
        "char_count":                result.char_count,
        "word_count":                result.word_count,
        "pages":                     result.pages,
        "method":                    result.method,
        "preprocessing_steps":       result.preprocessing_steps,
        "warning":                   result.warning or None,
        "document_type":             classification.document_type,
        "document_type_confidence":  round(classification.confidence, 3),
        "classification_method":     classification.method,
        "matched_rules":             classification.matched_rules,
        "legal_analysis":            legal_analysis_payload,
    }


# ── Dev entrypoint ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
