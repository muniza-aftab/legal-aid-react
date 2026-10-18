# Architecture — Pakistan AI Legal Aid System

> Historical architecture reference. The October 2026 repairs add server-validated sessions, private analytics by default, segmented document review, configurable Groq models, and Vercel SPA/API rewrites. See [VERIFICATION.md](VERIFICATION.md) and [DEPLOYMENT.md](DEPLOYMENT.md) for current behavior and operational limits. The diagrams below predate those repairs; retrieval checks reduce unsupported output but cannot guarantee legal accuracy.

**Revision**: 2026-05-18  
**Stack**: React 18 · FastAPI · Groq Llama 3.3 70B · FAISS · SQLite  
**Languages**: English / اردو (RTL)

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Repository Layout](#2-repository-layout)
3. [End-to-End Data Flows](#3-end-to-end-data-flows)
4. [Frontend Architecture](#4-frontend-architecture)
5. [Backend Architecture](#5-backend-architecture)
6. [Database Schema](#6-database-schema)
7. [RAG Pipeline (Deep)](#7-rag-pipeline-deep)
8. [Internationalization & RTL](#8-internationalization--rtl)
9. [Design System & Theming](#9-design-system--theming)
10. [Security Model](#10-security-model)
11. [Performance Characteristics](#11-performance-characteristics)
12. [Key Architectural Decisions](#12-key-architectural-decisions)
13. [Known Limitations & Trade-offs](#13-known-limitations--trade-offs)

> Sections updated in this revision: 1 (diagram), 2 (layout), 3.6 (new flow), 4.1, 4.3, 5.1, 5.9 (new), 7.9 (new), 11, 12, 13

---

## 1. System Overview

Pakistan AI Legal Aid is a full-stack RAG (Retrieval-Augmented Generation) application that helps Pakistani citizens understand their legal rights. Users submit a legal query in English or Urdu and receive a structured response — case classification, risk level, applicable law citations, rights summary, next steps, matched NGOs, and a matched lawyer — all derived from a corpus of Pakistani law PDFs through semantic search, not parametric LLM knowledge.

### Architecture Principles

| Principle | Implementation |
|---|---|
| **No hallucination by default** | 5-gate anti-hallucination pipeline; LLM is blocked if FAISS retrieval yields no qualifying chunks |
| **RAG-first, LLM-second** | LLM only rephrases and structures retrieved text; all legal facts must come from the FAISS index |
| **Multilingual & RTL** | All UI text localised in English/Urdu; Urdu mode applies RTL directional rules per-element |
| **Deterministic routing** | NGO/lawyer assignment uses rule-based scoring; no LLM in routing path |
| **Single binary** | Backend is a single FastAPI process; no microservices, no queues, no external DB |
| **Offline capability** | FAISS index + SQLite run fully offline; only Groq API calls need internet |

### High-Level Component Diagram

```
Browser
  │
  ├── React 18 (Vite 5, port 5173)
  │     ├── Zustand store (language, theme, chat, analysisResult, admin)
  │     ├── i18n service (160+ keys, translateCategory, isRTL)
  │     └── axios (/api/* → proxy → :8000)
  │
  └── /api proxy (vite.config.js)
        │
        ▼
  FastAPI (Uvicorn, port 8000)
        │
        ├── chat_api.py (POST /chat, DELETE /chat, GET /chat/history)
        ├── main.py     (all other routes: /analyze, /ngos, /lawyers, /apply, /tts, /pdf, /transcribe, /admin/*)
        │
        ├── app/utils/
        │     ├── rag_engine.py          — FAISS search
        │     ├── embeddings.py          — sentence-transformers encode
        │     ├── chat_service.py        — session + 5-gate pipeline
        │     ├── groq_client.py         — Groq LLM + Whisper + document analysis
        │     ├── pdf_generator.py
        │     ├── tts.py
        │     ├── ngo_service.py         — CRUD
        │     ├── lawyer_service.py
        │     ├── application_service.py
        │     ├── ngo_matcher.py
        │     ├── db.py                  — SQLite
        │     ├── document_loader.py     — upload validation + temp file management
        │     ├── text_extractor.py      — PDF/DOCX/image text extraction (OCR)
        │     ├── document_classifier.py — rule-based + LLM document type classification
        │     ├── image_preprocessor.py  — OpenCV preprocessing for OCR
        │     └── ...
        │
        ├── data/faiss_index/     — index.bin + metadata.json
        ├── data/Laws/            — Pakistani law PDFs
        └── database.db           — SQLite (NGOs, lawyers, applications, logs)
```

---

## 2. Repository Layout

```
legal-aid-react/
│
├── frontend/
│   ├── src/
│   │   ├── main.jsx                          Entry point — BrowserRouter + React.StrictMode
│   │   ├── App.jsx                           Route definitions + app init (GET /api/config)
│   │   │
│   │   ├── pages/
│   │   │   ├── LanguagePicker.jsx            Route: /  — language selection landing
│   │   │   ├── HomePage.jsx                  Route: /home — main analysis UI (598 lines)
│   │   │   ├── ApplyPage.jsx                 Route: /apply — application form
│   │   │   ├── EmergencyPage.jsx             Route: /emergency — emergency contacts
│   │   │   ├── AboutPage.jsx                 Route: /about — project info
│   │   │   ├── NGOPage.jsx                   Route: /ngos — NGO directory
│   │   │   ├── LawyersPage.jsx               Route: /lawyers — lawyer directory
│   │   │   ├── DocumentAnalysisPage.jsx      Route: /document-analysis — upload + AI analysis
│   │   │   ├── AnalyticsPage.jsx             Route: /admin/analytics
│   │   │   └── AdminPage.jsx                 Route: /admin/* — password-gated dashboard
│   │   │
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   └── AppLayout.jsx             Sidebar + Topbar + content shell
│   │   │   ├── chat/
│   │   │   │   ├── AIAssistantDrawer.jsx     Overlay drawer (right/left in RTL) — 516 lines
│   │   │   │   ├── ChatAssistant.jsx         Inline chat panel — 314 lines
│   │   │   │   └── SourcesPanel.jsx          Law source citations panel
│   │   │   ├── analytics/
│   │   │   │   └── NGOList.jsx               NGO result cards in analysis output
│   │   │   └── ui/
│   │   │       ├── index.jsx                 13 shared components (Badge, Card, Spinner …)
│   │   │       ├── FloatingAIButton.jsx      FAB → open chat drawer
│   │   │       └── CitySelector.jsx          City + Language dropdowns (combined file)
│   │   │
│   │   ├── services/
│   │   │   ├── api.js                        Axios client — 23 API functions
│   │   │   ├── store.js                      Zustand store — 17 state fields, 15 actions
│   │   │   ├── i18n.js                       Translation strings + translateCategory
│   │   │   └── fileParser.js                 Client-side TXT/DOCX/PDF text extraction
│   │   │
│   │   └── styles/
│   │       └── globals.css                   CSS custom properties, component classes, RTL rules
│   │
│   ├── vite.config.js                        Vite build config (proxy, @/ alias, port 5173)
│   ├── tailwind.config.js                    Tailwind theme extensions
│   ├── postcss.config.js
│   └── package.json                          18 prod + 9 dev dependencies
│
├── backend/
│   ├── main.py                               FastAPI app — all routes except /chat
│   ├── chat_api.py                           FastAPI router — /chat endpoints
│   ├── build_index.py                        CLI — 5 phases: chunks/embed/faiss/auto/status/purge
│   │
│   ├── app/
│   │   └── utils/
│   │       ├── config.py                     All constants (models, paths, thresholds, maps)
│   │       ├── rag_engine.py                 FAISS index loader + retrieval pipeline
│   │       ├── embeddings.py                 Sentence-transformers wrapper (lazy load)
│   │       ├── embedding_cache.py            SHA-1 content-addressed embedding cache
│   │       ├── chat_service.py               Stateful session store + 5-gate pipeline (core)
│   │       ├── groq_client.py                Groq LLM (Llama 3.3 70B) + Whisper + document analysis
│   │       ├── ingest.py                     PDF scanner + legal chunker
│   │       ├── parser.py                     PDF text extractor (handles spaced OCR)
│   │       ├── validator.py                  Input sanitization + injection guard
│   │       ├── legal_taxonomy.py             12 case types + urgency levels + sub-areas
│   │       ├── db.py                         SQLite schema bootstrap + CRUD helpers
│   │       ├── ngo_service.py                NGO CRUD (DB-backed)
│   │       ├── lawyer_service.py             Lawyer CRUD (DB-backed)
│   │       ├── application_service.py        Case application submission + deterministic routing
│   │       ├── ngo_matcher.py                Smart NGO recommendation engine
│   │       ├── pdf_generator.py              ReportLab PDF export (English + Urdu/RTL)
│   │       ├── tts.py                        TTS: ElevenLabs → espeak-ng → gTTS fallback chain
│   │       ├── document_loader.py            Upload validation, MIME/magic-byte detection, temp file I/O
│   │       ├── text_extractor.py             PDF/DOCX/image text extraction; OCR via Tesseract
│   │       ├── document_classifier.py        Rule-based + Groq LLM fallback document type classifier
│   │       └── image_preprocessor.py         OpenCV grayscale / threshold / denoise pipeline for OCR
│   │
│   ├── data/
│   │   ├── Laws/                             Pakistani law PDFs (7 subdirs, 30+ PDFs)
│   │   │   ├── Core/                         Constitution, PPC, Education Act
│   │   │   ├── Criminal/                     CrPC, Arms Act, Prisoners Act + 5 more
│   │   │   ├── Family/                       Muslim Family Laws, Dissolution, DV Act + 5 more
│   │   │   ├── Civil/                        Contract Act, Transfer of Property + 5 more
│   │   │   ├── Labour/                       Industrial Relations Act, Payment of Wages + 5 more
│   │   │   ├── Cybercrime/                   PECA 2016
│   │   │   └── Harassment/                   Protection Against Harassment Act 2010
│   │   ├── faiss_index/
│   │   │   ├── index.bin                     FAISS IndexFlatIP (cosine on L2-normed vectors)
│   │   │   └── metadata.json                 Parallel chunk metadata array
│   │   ├── chunks.json                       Parsed + chunked law text (phase 1 output)
│   │   ├── embeddings_cache.npz              Float32 vectors stacked (N × 384 dims)
│   │   ├── embeddings_cache.json             Sidecar: model_name + SHA-1 hash list
│   │   ├── ngos.json                         Seed NGO data
│   │   └── helplines.json                    Emergency helpline data
│   │
│   ├── database.db                           SQLite (5 tables)
│   ├── requirements.txt                      Python dependencies
│   └── .env.example                          Environment variable template
│
├── start_all.bat                             Full launcher: venv setup, npm install, FAISS build, opens both servers
├── start_backend.bat                         Backend only: activates venv, FAISS check, runs main.py
├── start_frontend.bat                        Frontend only: npm install if needed, npm run dev
├── run_project.bat                           Legacy launcher (superseded by start_all.bat)
├── run_project.sh                            One-click start (macOS/Linux)
├── README.md
└── architecture.md                           ← this file
```

---

## 3. End-to-End Data Flows

### 3.1 Legal Analysis Flow (Primary)

```
User types legal query in textarea (min 15 chars, max 2000)
  │
  ▼
[Frontend] analyzeCase(query, language, city)
  POST /api/analyze { query, language, city }
  │
  ▼
[Backend: main.py /api/analyze]
  1. validate input length (config.py MIN/MAX_QUERY_LENGTH)
  2. log_query() → users_logs table
  3. rag_engine.retrieve(query, top_k=8)
     ├── preprocess_query (Urdu→English synonyms, abbreviation expansion)
     ├── encode_query → 1×384 float32 vector
     ├── FAISS search (5× over-fetch pool)
     ├── score boost (category affinity +0.06, keyword overlap +0.04)
     ├── schedule chunk penalty (-0.12)
     ├── threshold filter (primary ≥0.40, fallback ≥0.28)
     ├── diversity cap (max 3 chunks per law)
     └── return top_k chunks with raw display scores
  4. groq_client.analyze_case(query, chunks, language, city)
     └── Groq Llama 3.3 70B → structured JSON
  5. ngo_matcher.recommend_ngos(category, city)
  6. ngo_matcher.get_urgent_helplines(category, risk_level)
  │
  ▼
[Frontend] setAnalysisResult(response)
  Renders:
  ├── Category badge + Risk badge + Confidence bar
  ├── Summary text + Listen (TTS) button
  ├── Tabs: Laws | Rights | Steps | Sources
  ├── Urgent helplines (red banner if present)
  └── NGOs section (collapsible)
```

### 3.2 Chat Flow (5-Gate Pipeline)

```
User sends message in chat panel/drawer
  │
  ▼
[Frontend] sendChatMessage(sessionId, message, language, caseContext)
  POST /api/chat { session_id, message, language }
  │
  ▼
[Backend: chat_api.py → chat_service.process()]
  │
  ├── GATE 1: sanitize(message)
  │     Strip non-printables, length check, injection blocklist
  │     → reject: ValidationError
  │
  ├── GATE 0: _is_on_topic(message, case_context)  [if case_context exists]
  │     Token overlap with category/summary/keywords
  │     Queries ≤12 tokens auto-pass (avoid false rejections)
  │     → off-topic: "Please ask about your legal case"
  │
  ├── GATE 2: _is_too_vague(message)
  │     Reject if <4 words or single generic word
  │     → vague: "Could you share more detail?"
  │
  ├── GATE 3a [HARD]: retrieve(query, top_k=12) via rag_engine
  │     Filter: score < 0.42 → discard
  │     Filter: Section 1/2 definitional sections → discard
  │     → empty after filter: return NO_CONTEXT_REPLY, LLM NOT called
  │
  ├── GATE 3b: weak context check
  │     avg_score < 0.50 OR < 2 qualified chunks
  │     → inject WEAK_CONTEXT_WARNING into prompt
  │
  ├── Query expansion: _expand_query_keywords()
  │     "evict" → "eviction tenant landlord lease termination"
  │     "talaq" → "divorce talaq dissolution marriage khula"
  │
  ├── Domain priority reranking
  │     Labour case → Labour Law chunks +0.08, cross-domain chunks -0.05
  │
  ├── GATE 4: System prompt v5 (240 lines)
  │     NEVER invent laws/sections/rulings
  │     DERIVE ALL legal facts from retrieved context
  │     Mark inferences "In practice…" (once only)
  │     End with lawyer caveat
  │     SUPPRESS banned phrases
  │     Banned: "The retrieved laws don't directly address…"
  │             "Typically in Pakistan…"
  │             "Based on the laws provided in the context…"
  │
  ├── GATE 5: Groq call
  │     Model: llama-3.3-70b-versatile
  │     Temperature: 0.15
  │     max_tokens: 900
  │
  ├── Confidence scoring (v5, 4-factor):
  │     F1 — avg retrieval score: ≥0.72→high, 0.52–0.72→medium, <0.52→low
  │     F2 — top-2 chunks cross-domain → penalise one tier
  │     F3 — ≥2 inference hedges ("typically") → penalise one tier
  │     F4 — any refusal marker → force "low"
  │
  ├── Case facts extraction (regex, no LLM)
  │     Detects: salary slips, WhatsApp messages, witnesses, contracts,
  │              medical reports, Urdu evidence keywords (تنخواہ, گواہ…)
  │     Accumulated across session (max 12 facts, injected into every prompt)
  │
  └── Session persistence
        Append user + assistant turns to in-memory _store[session_id].history
        Session TTL: 3600s from last_active
  │
  ▼
ChatApiResponse { reply, sources, confidence, session_id, error }
  │
  ▼
[Frontend] addChatMessage({ role:'assistant', content: reply, confidence, sources })
  Renders bubble + confidence badge + source chips + TTS button
```

### 3.3 Index Build Flow (One-time)

```
python build_index.py [auto|chunks|embed|faiss|status|purge]
  │
  ├── Phase 1: chunks
  │     Scan data/Laws/ (root + all subdirs)
  │     For each PDF:
  │       parser.extract_pdf() → ParsedDocument
  │         Detect spaced OCR → de-space algorithm (iterative regex)
  │         Clean headers (Page X of Y), normalize whitespace
  │       ingest._chunk_document()
  │         Detect section boundaries (Article X., Section X., CHAPTER X, bare "54.")
  │         Split at boundaries; if block > 800 chars, split at sentences with 150-char overlap
  │         Fallback: split on triple-newlines
  │         Filter: < 120 chars or > 40% boilerplate ratio → skip
  │         Infer category: FILENAME_CATEGORY_MAP → FOLDER_CATEGORY_MAP
  │     Write data/chunks.json [{id, law_name, category, section, text, source, page_start}]
  │
  ├── Phase 2: embed
  │     Load chunks.json
  │     For each chunk: SHA-1(text) → check embeddings_cache.json
  │       Hit → reuse vector from embeddings_cache.npz
  │       Miss → encode via sentence-transformers (batch_size=64)
  │     Prune stale cache entries
  │     Write data/embeddings_cache.npz (N×384 float32)
  │     Write data/embeddings_cache.json (model_name, dim, hashes[])
  │
  ├── Phase 3: faiss
  │     Read chunks.json + embeddings cache
  │     Create FAISS IndexFlatIP
  │     L2-normalize all vectors (cosine = inner product on unit vectors)
  │     Build index; add all vectors
  │     Write data/faiss_index/index.bin
  │     Write data/faiss_index/metadata.json (parallel to FAISS internal IDs)
  │
  └── Smoke tests (auto phase only)
        4 queries: "unpaid salary", "divorce wife rights",
                   "FIR police arrest", "tenant landlord deposit"
        Validates expected category match for each
```

### 3.4 Application Submission Flow

```
User fills ApplyPage form (react-hook-form + zod validation)
  POST /api/applications
  { name, contact, email, city, case_type, urgency, description, language }
  │
  ▼
[Backend: application_service.submit_application()]
  1. Generate application_id (UUID)
  2. Map urgency string → priority int (Low=1, Medium=2, High=3, Critical=4)
  3. DB routing (Phase 2):
     a. Query ngos table for category + city match → assign_ngo_id
     b. Query lawyers table for expertise_main match + available=1 → suggest_lawyer
  4. Static fallback (if DB empty): hardcoded NGO → category name map
  5. INSERT into applications table (status='pending')
  6. Return { application_id, assigned_ngo, suggested_lawyer, status }
  │
  ▼
[Frontend] Show success screen with application_id reference
```

### 3.6 Document Analysis Flow

```
User selects a file (PDF / DOCX / PNG / JPG) on DocumentAnalysisPage
  POST /api/analyze-document  (multipart/form-data: file, language)
  │
  ▼
[Backend: main.py /api/analyze-document]
  1. document_loader.load_upload(upload)
     ├── MIME detection → "pdf" | "docx" | "image"
     ├── Extension fallback for generic MIME types
     ├── Read all bytes (max 10 MB)
     ├── Magic-byte validation (PDF: %PDF, DOCX: PK\x03\x04, PNG: \x89PNG, JPEG: \xff\xd8\xff)
     │     Warning logged on mismatch; libraries are authoritative fail-safe
     └── Write to OS temp file (suffix = original extension for images)
  │
  ▼  asyncio.wait_for(_run_pipeline(), timeout=120 s)
  │
  2. text_extractor.extract_text(tmp_path, file_type)
     ├── PDF: pdfplumber primary → pypdf fallback; page-by-page extraction
     ├── DOCX: python-docx paragraph join
     ├── Image: image_preprocessor → Tesseract OCR
     │   Preprocessing chain: EXIF-rotate → grayscale → adaptive threshold → denoise
     ├── NFC Unicode normalisation (Arabic/Urdu decomposed chars)
     ├── Null-byte + control-char strip
     └── Hard cap: 100 000 chars (logged; truncated before classifier)
  │
  ▼
  3. document_classifier.classify_document(text, language)
     ├── Rule-based scoring — regex patterns (English + Urdu) over first 3000 chars
     │     Types: Legal Notice | FIR | Court Order | Rent Agreement | Employment Contract | Unknown
     ├── confidence ≥ 0.40 → return rule result
     └── confidence < 0.40 → Groq Llama 3.3 70B fallback classification
  │
  ▼  (skipped if extracted text < 20 chars → legal_analysis: null in response)
  │
  4. groq_client.analyze_document_with_rag(text, document_type, detected_lang, ui_lang)
     ├── Input: NFC-normalise, null-strip, cap at 50 000 chars
     ├── rag_engine.retrieve(retrieval_query, top_k=8)
     ├── _filter_chunks_for_document(chunks, document_type)  — post-retrieval filter
     │     Gate 1: score ≥ 0.45 (floor higher than general 0.40)
     │     Gate 2: off-category chunk must score ≥ 0.55 to survive
     │     Gate 3: max 2 chunks per unique law_name (diversity cap)
     │     Allowlists: FIR → Criminal + Procedural only
     │                 Rent Agreement → Property + Contract only
     │                 Employment Contract → Labour + Contract only
     │                 Court Order → Criminal + Civil + Procedural + Family + Property + Labour
     │                 Legal Notice → all six main categories
     ├── _DOC_ANALYSIS_SYSTEM_PROMPT — anti-speculation rules:
     │     FORBIDDEN: infer consequences not stated in document
     │     FORBIDDEN: cite laws not in RAG context
     │     FORBIDDEN: invent section numbers or amounts
     │     REQUIRED: every obligation must trace to "The document states:" prefix
     │     REQUIRED: every law reference must trace to "Under [Law]:" prefix
     └── Groq Llama 3.3 70B → structured JSON
  │
  5. Cleanup: os.unlink(tmp_path)
  │
  ▼
Response JSON:
  {
    "filename": "...",
    "file_type": "pdf | docx | image",
    "size_bytes": 123456,
    "extraction": { "text_preview", "char_count", "word_count", "detected_language", "ocr_used" },
    "classification": { "document_type", "confidence", "method" },
    "legal_analysis": {               ← null if text < 20 chars
      "document_summary",
      "key_points",
      "obligations_and_deadlines",
      "risk_indicators",
      "cited_laws",
      "recommended_actions",
      "confidence_note"
    } | null
  }
  │
  ▼
[Frontend: DocumentAnalysisPage.jsx]
  ├── Upload zone (drag-and-drop or browse; 10 MB limit shown)
  ├── Language toggle (English / Urdu)
  ├── Extraction card (preview, char/word count, language, OCR flag)
  ├── Classification badge (document type + confidence %)
  ├── legal_analysis === null → info alert ("text too short for AI analysis")
  └── legal_analysis present:
        ├── Key Points (collapsible)
        ├── Obligations & Deadlines (collapsible)
        ├── Risk Indicators (collapsible)
        └── Cited Laws (collapsible)
```

### 3.5 Voice Input Flow

```
User clicks Record button → navigator.mediaDevices.getUserMedia({audio:true})
  │
  MediaRecorder stream → pushes chunks to audioChunksRef[]
  │
User clicks Stop → mediaRecorder.stop()
  → Blob(chunks, {type:'audio/webm'})
  │
  POST /api/transcribe (FormData: audio file, language)
  │
[Backend: groq_client.transcribe()]
  Model: whisper-large-v3-turbo
  Returns: { text: "transcribed content" }
  │
[Frontend] Fill textarea with transcribed text
  User can review and click Analyze
```

---

## 4. Frontend Architecture

### 4.1 Entry Point & Routing

**`src/main.jsx`** — Renders `<App />` wrapped in `<React.StrictMode>` and `<BrowserRouter>`.

**`src/App.jsx`** — Defines all routes and loads app config on mount via `GET /api/config`.

| Route | Component | Layout | Notes |
|---|---|---|---|
| `/` | LanguagePicker | None | Standalone landing; no sidebar |
| `/home` | HomePage | AppLayout | Primary interface |
| `/chat` | — | — | Redirects to `/home` |
| `/apply` | ApplyPage | AppLayout | |
| `/emergency` | EmergencyPage | AppLayout | |
| `/about` | AboutPage | AppLayout | |
| `/ngos` | NGOPage | AppLayout | |
| `/lawyers` | LawyersPage | AppLayout | |
| `/document-analysis` | DocumentAnalysisPage | AppLayout | Upload + AI document analysis |
| `/admin/*` | AdminPage | AppLayout | Soft-gated by password |
| `/analytics` | — | — | Redirects to `/admin/analytics` |
| `*` | — | — | Redirects to `/` |

**App Shell Pattern**: Routes inside `<AppShell />` render `<AppLayout><Outlet /></AppLayout>`. Only `/` bypasses this.

**Loading screen**: While `GET /api/config` is in-flight, App renders a solid `#0d1f3d` background with a centered emoji — prevents flash of unstyled layout.

### 4.2 State Management

**`src/services/store.js`** — Zustand v4.5.2 with `persist` middleware.  
Persistence key: `legal-aid-store` in `localStorage`.

#### State Fields

| Field | Type | Persisted | Description |
|---|---|---|---|
| `language` | `'English' \| 'Urdu'` | YES | Active UI language |
| `languageChosen` | `boolean` | NO | Set by `chooseLanguage()` only (currently unused) |
| `city` | `string` | YES | Selected city for NGO routing ('' = any) |
| `appConfig` | `object` | NO | Server-side config from `/api/config` |
| `analysisResult` | `object \| null` | NO | Full analysis response (category, risk, laws, sources, ngos) |
| `chatSessionId` | `string \| null` | NO | Active chat session UUID |
| `chatMessages` | `array` | NO | `[{role, content, id, confidence, sources}]` |
| `queryHistory` | `array` | NO | Last 10 queries (FIFO ring buffer) |
| `adminAuthenticated` | `boolean` | YES | Admin login flag |
| `adminToken` | `string \| null` | YES | Token sent as `X-Admin-Token` header |
| `sidebarOpen` | `boolean` | NO | Mobile sidebar visibility |
| `aiDrawerOpen` | `boolean` | NO | Chat drawer open state |
| `theme` | `'dark' \| 'light'` | YES | Global theme |

#### Actions

```
setLanguage(lang)          — change language (no side effects)
chooseLanguage(lang)       — set language + languageChosen=true
setCity(city)
setAppConfig(config)
setAnalysisResult(result) / clearAnalysis()
setChatSessionId(id) / clearChat()
addChatMessage(msg)
addToHistory(entry)        — push to queryHistory, keep last 10
setAdminAuth(token)        — sets adminAuthenticated=true + adminToken
clearAdminAuth()
toggleSidebar()
toggleAiDrawer() / openAiDrawer() / closeAiDrawer()
toggleTheme()
```

### 4.3 API Service Layer

**`src/services/api.js`** — Axios v1.7.2 client.

**Base URL**: `import.meta.env.VITE_API_URL || ''` (empty in dev → goes through Vite proxy).  
**Timeout**: 60 000 ms.

**Request Interceptor**: Reads `adminToken` from `localStorage['legal-aid-store'].state.adminToken` and injects it as `X-Admin-Token` header on every request.

#### All 23+ API Functions

| Function | Method | Path | Purpose |
|---|---|---|---|
| `analyzeCase(query, language, city)` | POST | `/api/analyze` | Core legal analysis |
| `analyzeDocument(file, language)` | POST | `/api/analyze-document` | Upload + AI document analysis (multipart) |
| `sendChatMessage(sessionId, msg, language, ctx)` | POST | `/api/chat` | Multi-turn chat |
| `clearChatSession(sessionId)` | DELETE | `/api/chat/{id}` | Clear session history |
| `submitApplication(data)` | POST | `/api/applications` | Submit case application |
| `getApplications(params)` | GET | `/api/applications` | List applications (admin) |
| `getApplicationStats()` | GET | `/api/applications/stats` | Stats for dashboard |
| `updateApplicationStatus(id, status)` | PATCH | `/api/applications/{id}/status` | |
| `assignLawyer(id, lawyerId)` | PATCH | `/api/applications/{id}/lawyer` | Admin override |
| `assignNGO(id, ngoId)` | PATCH | `/api/applications/{id}/ngo` | Admin override |
| `getNGOs(params)` | GET | `/api/ngos` | List NGOs |
| `createNGO(data)` | POST | `/api/ngos` | Create (admin) |
| `updateNGO(id, data)` | PUT | `/api/ngos/{id}` | Update (admin) |
| `deactivateNGO(id)` | PATCH | `/api/ngos/{id}/deactivate` | |
| `reactivateNGO(id)` | PATCH | `/api/ngos/{id}/reactivate` | |
| `deleteNGO(id)` | DELETE | `/api/ngos/{id}` | |
| `getLawyers(params)` | GET | `/api/lawyers` | List lawyers |
| `createLawyer(data)` | POST | `/api/lawyers` | Create (admin) |
| `updateLawyer(id, data)` | PUT | `/api/lawyers/{id}` | |
| `deleteLawyer(id)` | DELETE | `/api/lawyers/{id}` | |
| `setLawyerAvailability(id, available)` | PATCH | `/api/lawyers/{id}/availability` | Toggle |
| `getAnalyticsSummary()` | GET | `/api/analytics/summary` | Dashboard analytics |
| `getQueryLogs(limit)` | GET | `/api/analytics/queries` | Query history |
| `getTTSUrl(text, language)` | — | `/api/tts?text=…` | Build URL for `<audio>` src |
| `generateTTS(text, language)` | POST | `/api/tts` | Returns audio blob |
| `downloadPDF(data, language)` | POST | `/api/pdf` | Returns PDF blob |
| `transcribeAudio(blob, language)` | POST | `/api/transcribe` | Groq Whisper |
| `adminLogin(password)` | POST | `/api/admin/login` | Returns `{token}` |
| `checkHealth()` | GET | `/api/health` | Liveness check |
| `rerouteApplication(appId)` | POST | `/api/applications/{id}/reroute` | Admin re-route |
| `getRoutingPreview(city, caseType, urgency)` | GET | `/api/routing/preview` | Preview routing |

### 4.4 File Parser Service

**`src/services/fileParser.js`** — Client-side text extraction (no backend call).

| Format | Library | Notes |
|---|---|---|
| `.txt` | `File.text()` (native) | UTF-8, Urdu-safe |
| `.docx` | `mammoth.extractRawText()` | Plain text only, no formatting |
| `.pdf` | `pdfjs-dist` | Iterates all pages; uses CDN CMap for CJK/Arabic glyphs; handles `hasEOL` flag for paragraph breaks |

Error messages use `t('file_no_text')` / `t('file_error')` from i18n.

### 4.5 Page Components

#### HomePage (`/home`) — 598 lines, most complex page

**Left panel** (input):
- Textarea (max 2000 chars, char counter)
- 8 quick-category buttons (pre-fill textarea): Property, Family, Employment, Cybercrime, Criminal, Inheritance, Contract, Harassment
- Record button → `MediaRecorder` → `transcribeAudio()` → fill textarea
- Upload button → `fileParser.extractTextFromFile()` → fill textarea  
- Analyze / Clear / Download PDF buttons

**Right panel** (results):
- Renders `analysisResult` from Zustand store
- Urgent helplines: red alert banner with `tel:` links
- Category + Risk + Confidence bar
- Summary + Listen (TTS) button
- 4 tabs: Laws · Rights · Steps · Sources
- NGO section (collapsible, uses `NGOList` component)
- Workflow stepper (always visible: 4 static steps)

**Local state**: `query`, `loading`, `error`, `activeTab`, `showNGOs`, `ttsTarget`, `recording`, `recordLoading`, `recordError`

#### ApplyPage (`/apply`)

Form fields and Zod schema:

| Field | Validation |
|---|---|
| `full_name` | required, min 2 chars |
| `cnic` | optional |
| `phone` | required, min 7 chars |
| `email` | optional, valid email if provided |
| `city` | required, one of 9 cities |
| `case_type` | required, one of 12 legal categories (must match backend enum exactly) |
| `urgency` | required, radio: Low / Medium / High / Critical |
| `description` | required, min 30 chars |

On success: shows reference ID from `application_id` + "Submit Another" button.

#### AdminPage (`/admin/*`) — Password-gated

Admin login: `adminLogin(password)` → `{token}` → `setAdminAuth(token)` → store.  
Tab sections: Dashboard · NGO Registry · Lawyers · Case Routing · Analytics.  
All admin CRUD operations require `X-Admin-Token` header (injected by Axios interceptor).

### 4.6 Layout & UI Components

#### AppLayout (`src/components/layout/AppLayout.jsx`)

```
<div flex>
  <Sidebar dir="ltr" always>        ← 242px, always dark, always LTR
  <div flex-1>
    <Topbar sticky>                  ← 52px
    <main dir={rtl && !isAdmin ? 'rtl' : 'ltr'}>
      <Outlet />                     ← page content
    </main>
  </div>
  <AIAssistantDrawer />              ← overlay, z-50
  <FloatingAIButton />               ← bottom-right, z-30
</div>
```

RTL direction is applied to the main content area **only** for non-admin routes. The sidebar is hard-locked LTR by CSS rule `.sidebar { direction: ltr; }`.

#### Shared UI Components (`src/components/ui/index.jsx`)

| Component | Props | Purpose |
|---|---|---|
| `Badge` | `variant` (neutral/success/warning/danger/critical/primary) | Inline status chips |
| `RiskBadge` | `level` | Semantic risk levels (Low→green, High→red) |
| `StatusBadge` | `status` | Application workflow status |
| `Card` | `padding`, `className` | Glassmorphic container |
| `KPICard` | `label`, `value`, `sub`, `icon`, `accent` | Dashboard metric cards |
| `Skeleton` / `CardSkeleton` | — | Shimmer loading placeholders |
| `Alert` | `type` (info/success/warning/danger) | Banner messages |
| `Spinner` | `size` | SVG loading indicator |
| `EmptyState` | `icon`, `title`, `description`, `action` | Centered empty placeholder |
| `ProgressBar` | `value`, `max`, `color`, `height` | Animated progress bar |
| `SectionHeader` | `eyebrow`, `title`, `description`, `actions` | Page headers with gradient eyebrow |

#### Chat Components

**`AIAssistantDrawer`** — overlay panel, full height, 100% wide on mobile / 420px on desktop. Position: right in LTR, left in RTL. Contains:
- Header with context label + Clear + Close
- Yellow disclaimer banner
- Scrollable messages area (typing indicator: 3 animated dots)
- Auto-expanding textarea (42–120px), Send button
- Keyboard hint: Enter = send, Shift+Enter = newline

**Chat bubble row**: always `dir="ltr"` — critical so `flex-row-reverse` positions user bubbles on the right regardless of page RTL direction.

**`SourcesPanel`** — header (law name left, score % right), section label (monospace), excerpt (always `dir="ltr"`, `text-align:left` — English legal text).

---

## 5. Backend Architecture

### 5.1 Entry Points

**`main.py`** — FastAPI application with all routes except `/chat`.

Key routes:
- `POST /api/analyze` — full legal analysis pipeline
- `POST /api/analyze-document` — document upload, OCR, classification, and RAG-grounded legal analysis
- `POST /api/transcribe` — Groq Whisper transcription
- `POST /api/tts` — text-to-speech
- `POST /api/pdf` — PDF report generation
- `GET /api/ngos`, `POST /api/ngos`, `PUT /api/ngos/{id}`, `DELETE /api/ngos/{id}`
- `GET /api/lawyers`, `POST /api/lawyers`, etc.
- `POST /api/applications`, `GET /api/applications`, `PATCH /api/applications/{id}/status`
- `GET /api/analytics/summary`, `GET /api/analytics/queries`
- `POST /api/admin/login`
- `GET /api/health`
- `GET /api/config`

**`chat_api.py`** — FastAPI router, mounted at `/chat`.

| Endpoint | Method | Input | Output |
|---|---|---|---|
| `/chat` | POST | `ChatRequest(session_id, message, language)` | `ChatApiResponse` |
| `/chat` | DELETE | `ClearRequest(session_id)` | `{cleared: bool}` |
| `/chat/history` | GET | `?session_id=…&turns=5` | `{history: [{role, content}]}` |
| `/chat/health` | GET | — | `HealthResponse(status, rag_ready, groq_ready, timestamp)` |

**Pydantic v2 validation**:
- `session_id`: regex `^[\w\-]{1,128}$` — prevents path traversal
- `message`: 1–2000 chars
- `language`: enum `'English' | 'Urdu'` only

**CORS**: `allow_origins=["*"]` (restrict to frontend domain in production).

**Startup event**: checks `index_ready()` + `GROQ_API_KEY`; logs warnings if missing.

**HTTP status codes**:
- `200` — success (including NO_CONTEXT_REPLY — still a 200)
- `422` — Pydantic validation error
- `503` — RAG index not built
- `500` — uncaught server error

### 5.2 Configuration (`app/utils/config.py`)

All runtime constants in one place. Key values:

| Category | Constant | Value |
|---|---|---|
| Models | `GROQ_LLM_MODEL` | `llama-3.3-70b-versatile` |
| Models | `GROQ_FAST_MODEL` | `llama-3.1-8b-instant` |
| Models | `GROQ_WHISPER_MODEL` | `whisper-large-v3-turbo` |
| Models | `EMBED_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` |
| Chunking | `CHUNK_SIZE` | 800 chars |
| Chunking | `CHUNK_OVERLAP` | 150 chars |
| Retrieval | `TOP_K_RETRIEVAL` | 8 chunks |
| Retrieval | `SIMILARITY_THRESHOLD` | 0.25 (base; chat_service uses 0.42 for its hard gate) |
| Input | `MAX_QUERY_LENGTH` | 2000 chars |
| Input | `MIN_QUERY_LENGTH` | 15 chars |
| Prompt injection | `INJECTION_PATTERNS` | ~10 banned phrases |

Category-to-folder mappings, filename-override maps, emergency contacts, and risk color tokens are all defined here. This is the single source of truth for all category strings — `legal_taxonomy.py` re-exports them.

### 5.3 Legal Taxonomy (`app/utils/legal_taxonomy.py`)

Defines and re-exports the canonical 12-category enum used throughout the system:

```
Family Law · Criminal Law · Labour Law · Property Law
Inheritance Law · Cybercrime · Harassment · Civil Law / Procedure
Contract Law · Consumer Rights · Constitutional Law · General / Other
```

Also defines `URGENCY_LEVELS` (`Low / Medium / High / Critical`) and `EXPERTISE_SUBAREAS` mapping each main category to 5–6 sub-specializations.

**This enum is the shared contract between frontend and backend**. The frontend i18n `CATEGORY_TRANSLATIONS` map and the backend `LEGAL_CASE_TYPES` list must stay in sync.

### 5.4 Groq Client (`app/utils/groq_client.py`)

Two functions:

**`analyze_case(query, chunks, language, city) → dict`**
- Constructs system prompt emphasising RAG-grounded answers
- Calls `llama-3.3-70b-versatile` with retrieved law chunks as context
- Returns structured JSON: `{category, risk_level, summary, applicable_laws[], rights[], next_steps[], confidence}`

**`transcribe(audio_bytes, language) → str`**
- Sends audio to Groq Whisper (`whisper-large-v3-turbo`)
- Returns transcribed text string

### 5.5 NGO Matcher (`app/utils/ngo_matcher.py`)

Used by the `/api/analyze` endpoint to recommend NGOs alongside the legal analysis.

**`recommend_ngos(category, city, max_results=3, risk_level) → list[dict]`**
- Queries DB for NGOs matching category + optional city
- Scores by: keyword relevance, priority field, city match
- High/Critical risk: prioritises NGOs tagged as emergency or legal aid type
- Returns ranked list (max `max_results`)

**`get_urgent_helplines(category, risk_level) → list[dict]`**
- Loads `data/helplines.json` if present, else uses inline `URGENT_HELPLINES` dict
- Returns `[{icon, label, number}]` for the case category + risk combination

### 5.6 PDF Generator (`app/utils/pdf_generator.py`)

**`generate_case_pdf(result, language) → str`** — returns temp file path.

ReportLab generates a multi-section PDF:
1. Header (title + date)
2. Metadata (category + confidence, translated if Urdu)
3. Case summary
4. Risk level (coloured badge: green/orange/red/dark-red)
5. Relevant laws (bulleted)
6. Your rights (bulleted)
7. Next steps (bulleted)
8. Disclaimer

**Urdu RTL rendering challenge**: `python-bidi.get_display()` reverses an entire paragraph. Solution: split into sentences first, bidi-flip each sentence independently, emit as separate ReportLab `Paragraph` objects. Word-wrap uses 0.92× safety factor (pdfmetrics vs rendered glyph widths differ for Nastaliq).

Fonts: DejaVuSans (Latin) + NotoNastaliqUrdu (Urdu). Missing fonts degrade silently.

### 5.7 TTS (`app/utils/tts.py`)

**`generate_tts(text, language) → str | None`** — returns path to audio file or None.

Tries backends in order:

| Priority | Backend | Format | Condition |
|---|---|---|---|
| 1 | ElevenLabs API | MP3 | `ELEVENLABS_API_KEY` set and reachable |
| 2 | espeak-ng | WAV | Binary installed on system |
| 3 | gTTS | MP3 | Network available |

**Cache**: MD5(`language:text`) → `/tmp/legal_aid_tts/` — reuses file if present.  
**Truncation**: Input capped at 2000 chars.

### 5.8 Application Service (`app/utils/application_service.py`)

Deterministic routing — no LLM in this path.

**Routing strategy** (tried in order):
1. **DB-driven**: query `ngos` table for `category` match + optional `city` match → assign `ngo_id`
2. **Lawyer suggestion**: query `lawyers` table for `expertise_main` match + `available=1` → suggest lawyer
3. **Static fallback**: hardcoded `{category → ngo_name}` map used when DB tables are empty (first-run)

This layered approach means routing works immediately on a fresh install before any NGOs/lawyers are added to the DB.

**Application lifecycle states**: `pending → approved → assigned → in_progress → completed | rejected`

### 5.9 Document Analysis Modules

Four utility modules cooperate to serve `POST /api/analyze-document`. None of these modules touch the existing query-analysis or chat pipelines.

#### `document_loader.py` — Upload Validation & Temp File Management

**`load_upload(upload: UploadFile) → TempDocument`**

1. **Type detection**: MIME map first (`application/pdf` → `"pdf"`, image MIME types → `"image"`, etc.), then filename extension fallback for browsers that send `application/octet-stream`.
2. **Size check**: rejects files > 10 MB (`MAX_FILE_BYTES`).
3. **Magic-byte validation** (defence-in-depth, logs warning — does not raise):
   - PDF: `%PDF`
   - DOCX: `PK\x03\x04` (ZIP container)
   - PNG: `\x89PNG`; JPEG: `\xff\xd8\xff`
4. **Temp file**: written with original extension so Pillow / Tesseract detect format correctly. Caller must call `cleanup_temp(path)` when done.

**`cleanup_temp(path)`** — idempotent delete; logs warning on failure instead of raising.

#### `image_preprocessor.py` — OpenCV OCR Preprocessing

**`preprocess_for_ocr(image: PIL.Image) → PIL.Image`**

Pipeline applied before Tesseract:
1. EXIF orientation correction
2. Grayscale conversion
3. Adaptive Gaussian threshold (binarisation)
4. Median blur (salt-and-pepper noise removal)

Returns a binarised PIL Image. Called only for `file_type == "image"`.

#### `text_extractor.py` — Multi-Format Text Extraction

**`extract_text(tmp_path, file_type) → ExtractionResult`** — dispatches to:

| Format | Primary | Fallback | Notes |
|---|---|---|---|
| PDF | pdfplumber | pypdf | pdfplumber handles complex layouts; pypdf handles encrypted-but-readable |
| DOCX | python-docx | — | Joins all paragraph texts |
| Image | Tesseract (via pytesseract) | — | Preprocessed by image_preprocessor first |

Post-extraction:
- NFC Unicode normalisation (handles decomposed Arabic/Urdu)
- Null-byte strip
- Hard text cap: 100 000 chars (logged and truncated)

**`ExtractionResult`** dataclass:
```python
@dataclass
class ExtractionResult:
    text: str
    char_count: int
    word_count: int
    detected_language: str   # "English" | "Urdu" | "Mixed"
    ocr_used: bool
    pages_processed: int
```

Language detection: fraction of Urdu-range Unicode codepoints in the extracted text.

#### `document_classifier.py` — Document Type Classification

**`classify_document(text, language) → ClassificationResult`**

Two-stage pipeline:

**Stage 1 — Rule-based scoring** (scans first 3000 chars):
- Regex patterns weighted by specificity for each of 5 document types
- English patterns + equivalent Urdu patterns for each type
- Confidence = normalised weighted score

**Stage 2 — LLM fallback** (triggered when rule confidence < 0.40):
- Groq Llama 3.3 70B with a compact classification prompt
- Returns document type as a constrained enum string
- Imported dynamically to avoid hard dependency on GROQ_API_KEY

**`ClassificationResult`** dataclass:
```python
@dataclass
class ClassificationResult:
    document_type: str      # "Legal Notice" | "FIR" | "Court Order" |
                            # "Rent Agreement" | "Employment Contract" | "Unknown"
    confidence: float       # 0.0 – 1.0
    method: str             # "rule_based" | "llm_fallback"
```

#### `groq_client.py` — `analyze_document_with_rag()`

**New function** added alongside the existing `analyze_case()` and `transcribe()`.

```python
analyze_document_with_rag(
    document_text: str,
    document_type: str,
    detected_language: str,
    ui_language: str,
) → dict
```

Steps:
1. Input sanitisation: NFC normalise, null-strip, cap at 50 000 chars
2. `rag_engine.retrieve(retrieval_query, top_k=8)` — standard FAISS retrieval
3. `_filter_chunks_for_document(chunks, document_type)` — document-specific post-filter (see §7.9)
4. `_DOC_ANALYSIS_SYSTEM_PROMPT` — separate from chat/analysis prompt; includes ANTI-SPECULATION block
5. Groq Llama 3.3 70B call → JSON response with fields:
   `document_summary`, `key_points[]`, `obligations_and_deadlines[]`, `risk_indicators[]`, `cited_laws[]`, `recommended_actions[]`, `confidence_note`

**Anti-speculation rules in `_DOC_ANALYSIS_SYSTEM_PROMPT`**:
- FORBIDDEN: infer consequences not stated in the document
- FORBIDDEN: cite laws not present in RAG context
- FORBIDDEN: invent section numbers, amounts, or dates not found in the document
- Every obligation → must start with `"The document states:"`
- Every law reference → must start with `"Under [Law]:"`

---

## 6. Database Schema

**Engine**: SQLite 3, file `backend/database.db`  
**Init**: `db.init_db()` — idempotent, runs on every backend startup; uses `CREATE TABLE IF NOT EXISTS` + column migration for additive schema changes.

### users_logs

```sql
CREATE TABLE users_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp    TEXT    NOT NULL,
    language     TEXT    NOT NULL,           -- 'English' | 'Urdu'
    query_text   TEXT    NOT NULL,
    category     TEXT    DEFAULT '',         -- detected legal category
    risk_level   TEXT    DEFAULT '',
    ai_summary   TEXT    DEFAULT '',
    voice_used   INTEGER DEFAULT 0           -- 0 | 1 boolean
);
```

Written by every `/api/analyze` call. Powers analytics dashboard.

### feedback

```sql
CREATE TABLE feedback (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT    NOT NULL,
    rating    INTEGER NOT NULL,             -- 1–5 stars
    comment   TEXT
);
```

### ngos

```sql
CREATE TABLE ngos (
    ngo_id            TEXT    PRIMARY KEY,                      -- UUID
    ngo_name          TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    category          TEXT    NOT NULL DEFAULT 'General / Other',  -- primary
    categories        TEXT    NOT NULL DEFAULT '[]',            -- JSON array string
    city              TEXT    DEFAULT '',
    contact_email     TEXT    DEFAULT '',
    contact_phone     TEXT    DEFAULT '',
    handles_all_cases INTEGER NOT NULL DEFAULT 0,
    active            INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT    NOT NULL
);
CREATE INDEX idx_ngos_active   ON ngos(active);
CREATE INDEX idx_ngos_category ON ngos(category);
CREATE INDEX idx_ngos_city     ON ngos(city);
```

`categories` is stored as a JSON array string (e.g., `'["Family Law","Labour Law"]'`) and parsed to a Python list on retrieval. `category` is kept as the primary/first value for backward-compatible routing queries.

### lawyers

```sql
CREATE TABLE lawyers (
    lawyer_id      TEXT    PRIMARY KEY,                 -- UUID
    full_name      TEXT    NOT NULL,
    bar_license    TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    ngo_id         TEXT    DEFAULT '',                  -- FK → ngos.ngo_id
    city           TEXT    DEFAULT '',
    expertise_main TEXT    NOT NULL,                    -- one of 12 categories
    expertise_sub  TEXT    DEFAULT '',                  -- comma-separated sub-areas
    active_cases   INTEGER NOT NULL DEFAULT 0,
    available      INTEGER NOT NULL DEFAULT 1,          -- 0 | 1 boolean
    created_at     TEXT    NOT NULL
);
CREATE INDEX idx_lawyers_ngo       ON lawyers(ngo_id);
CREATE INDEX idx_lawyers_expertise ON lawyers(expertise_main);
CREATE INDEX idx_lawyers_available ON lawyers(available);
CREATE INDEX idx_lawyers_city      ON lawyers(city);
```

### applications

```sql
CREATE TABLE applications (
    application_id     TEXT    PRIMARY KEY,
    timestamp          TEXT    NOT NULL,
    name               TEXT    NOT NULL,
    contact            TEXT    NOT NULL,
    email              TEXT    DEFAULT '',
    city               TEXT    NOT NULL,
    case_type          TEXT    NOT NULL,
    urgency            TEXT    NOT NULL,               -- Low | Medium | High | Critical
    priority           INTEGER NOT NULL,               -- 1 | 2 | 3 | 4
    description        TEXT    NOT NULL,
    status             TEXT    DEFAULT 'pending',
    assigned_ngo       TEXT    DEFAULT '',             -- NGO name (display)
    assigned_ngo_id    TEXT    DEFAULT '',             -- FK → ngos.ngo_id
    suggested_lawyer   TEXT    DEFAULT '',             -- lawyer name (display)
    assigned_lawyer_id TEXT    DEFAULT '',             -- FK → lawyers.lawyer_id
    notes              TEXT    DEFAULT ''
);
```

---

## 7. RAG Pipeline (Deep)

### 7.1 Document Parsing (`parser.py`)

Two PDF types are handled:

| Type | Detection | Treatment |
|---|---|---|
| Normal (digitally-born) | Baseline | Extract as-is, clean headers |
| Spaced OCR | `>10` regex matches of `X space X` pattern in first 5 pages | Iterative de-spacing regex (up to 10 passes) |

Cleaning steps: remove "Page X of Y" headers, collapse whitespace, strip non-printables (keep Arabic/Urdu Unicode range).

### 7.2 Chunking Strategy (`ingest.py`)

Section boundary detection uses regex patterns in priority order:

1. `Article 25.` / `Article 25A.` — constitutional style
2. `Section 54.` / `Section 54A.` — statutory style
3. `CHAPTER III` / `CHAPTER 3` — chapter headings
4. `PART IV` / `PART 4` — part headings
5. `54.` (bare number at line start) — most common in Pakistani laws

Chunk construction:
- Blocks ≤ 800 chars → emit as single chunk
- Blocks > 800 chars → split at sentence boundaries, carry 150-char overlap
- Fallback (no boundaries): split on triple-newlines

Filtering:
- Blocks < 120 chars → skip (too short)
- Blocks with > 40% boilerplate ratio → skip (amendment notes, repealed clauses)
- Urdu-only PDFs → skip (model can't embed Urdu script)

Category inference order: `FILENAME_CATEGORY_MAP` → `FOLDER_CATEGORY_MAP` → `'General / Other'`

### 7.3 Embedding Cache (`embedding_cache.py`)

Content-addressed cache keyed by SHA-1 of chunk text.

```
chunks.json     →   SHA-1 each chunk text
                         ↓
               embeddings_cache.json (hash list + model_name)
                         ↓
         Hit?  reuse row from embeddings_cache.npz
         Miss? encode via sentence-transformers, write to cache
                         ↓
               embeddings_cache.npz (N × 384 float32)
```

Cache is invalidated entirely if `EMBED_MODEL` name changes. Stale entries (chunks removed from source) are pruned at save time. On a corpus of 10k chunks, incremental rebuild after editing one PDF takes ~5 seconds instead of ~1 hour.

### 7.4 FAISS Index Structure

**Index type**: `IndexFlatIP` — exact inner-product (brute-force). Cosine similarity = inner product on L2-normalised vectors. No quantisation; deterministic results.

**Parallel structure**:
```
data/faiss_index/index.bin        FAISS internal IDs: 0, 1, 2, … N-1
data/faiss_index/metadata.json    [{id, law_name, category, section, text, source, page_start}, …]
```
FAISS internal ID maps 1:1 to `metadata.json` array index.

**Embedding dimensions**: 384 (all-MiniLM-L6-v2).

### 7.5 Retrieval Pipeline (`rag_engine.py`)

```
query string
  │
  ▼ preprocess_query()
  ├── Detect Urdu script (>30% Urdu chars) → append English synonyms
  │     تنخواہ → "salary wages payment"
  │     طلاق   → "divorce talaq"
  │     وراثت  → "inheritance succession"
  └── Expand abbreviations
        FIR → "FIR first information report"
        PPC → "PPC Pakistan Penal Code"
        CrPC/CPC similarly
  │
  ▼ encode_query() → 1×384 float32 (L2-normalised)
  │
  ▼ FAISS IndexFlatIP.search(vector, top_k × 5)
  │   Over-fetch 5× candidate pool to enable re-ranking
  │
  ▼ Score adjustment per candidate chunk:
  ├── +0.06 if chunk.category matches inferred query category
  ├── +0.04 × (query/chunk keyword overlap ratio)
  └── −0.12 if chunk is annotated as a schedule/appendix (non-operative)
  │
  ▼ Two-pass threshold:
  ├── Pass 1: keep boosted_score ≥ 0.40
  └── Pass 2 (if <3 results): relax to ≥ 0.28 (fallback)
      Floor: never below 0.20
  │
  ▼ Diversity cap: max 3 chunks per unique law_name
  │
  ▼ Return top_k results
      Score returned to caller: ORIGINAL (un-boosted) cosine score
      Boosted score was internal ranking only
```

### 7.6 Category Affinity Map

Used by `rag_engine.py` to infer query category from keywords for the +0.06 boost:

| Category | Trigger Keywords |
|---|---|
| Family Law | divorce, talaq, nikah, marriage, custody, khula, mehr |
| Labour Law | salary, wages, employer, employee, fired, termination |
| Property Law | rent, eviction, tenant, landlord, land, property |
| Criminal Law | fir, arrest, bail, police, murder, assault |
| Harassment | harassment, stalking, blackmail, threat |
| Inheritance Law | inheritance, wirasat, وراثت |
| Cybercrime | cyber, online fraud, hacking |

### 7.7 Chat Service Session Store

In-memory only. No database persistence.

```python
_store: dict[str, _Session]   # session_id → _Session

@dataclass
class _Session:
    session_id: str
    history: list[{role, content}]   # last PROMPT_HISTORY_TURNS exchanges
    last_active: float               # time.time() — for TTL
    case_facts: list[str]            # accumulated regex-extracted evidence
```

Sessions expire automatically after 3600 seconds of inactivity. The TTL is checked on each access, not via a background task.

### 7.8 Domain Priority Reranking

Applied **inside** `chat_service.py` after initial retrieval (separate from `rag_engine.py`'s boost):

| Case Category | Primary Law Fragments (substring match on `law_name`) |
|---|---|
| Labour Law | payment of wages, factories act, industrial relations, shops act |
| Family Law | muslim family, dissolution of marriage, guardians, child |
| Criminal Law | pakistan penal, criminal procedure, crpc |
| Property Law | transfer of property, rent, tenancy |
| Cybercrime | electronic crimes, peca |
| Harassment | harassment, workplace |

Chunks whose `law_name` matches the case category get `+0.08`; cross-domain chunks get `−0.05`. This prevents a labour dispute from citing PPC sections ahead of the Payment of Wages Act.

### 7.9 Document-Specific RAG Relevance Filtering (`groq_client.py`)

The standard `rag_engine.retrieve()` thresholds (primary ≥ 0.40, fallback ≥ 0.28) are designed for open-ended legal queries. Uploaded documents have a known type, so irrelevant law domains should be suppressed more aggressively.

`_filter_chunks_for_document()` is a post-retrieval filter applied **only** in the document analysis path. It does not modify `rag_engine.py`.

**Three-gate filter**:

| Gate | Constant | Value | Effect |
|---|---|---|---|
| Score floor | `_DOC_CHUNK_MIN_SCORE` | 0.45 | Drops any chunk scoring below this (higher than the general 0.40 primary threshold) |
| Off-category threshold | `_DOC_OFF_CATEGORY_THRESHOLD` | 0.55 | Chunks from outside the document type's allowed law categories must score ≥ 0.55 to survive |
| Diversity cap | `_DOC_MAX_PER_LAW` | 2 | At most 2 chunks from any single law name |

**Per-document-type category allowlists** (`_DOC_TYPE_CATEGORIES`):

| Document Type | Allowed Law Categories |
|---|---|
| FIR | Criminal Law, Procedural Law |
| Rent Agreement | Property Law, Contract Law |
| Employment Contract | Labour Law, Contract Law |
| Court Order | Criminal Law, Civil Law, Procedural Law, Family Law, Property Law, Labour Law |
| Legal Notice | All six main categories |
| Unknown | No allowlist (off-category gate still applies via 0.55 threshold) |

A chunk from an unallowed category is not immediately rejected — it must clear the higher `_DOC_OFF_CATEGORY_THRESHOLD` (0.55) to survive. This avoids over-filtering when a document straddles two law domains.

The filter logs: `doc-filter: N → M chunks (type='...' floor=0.45 off-cat=0.55 laws=K)`

---

## 8. Internationalization & RTL

### 8.1 Translation System (`src/services/i18n.js`)

```javascript
// Usage
const t = useT()
t('hero_title')   // → "Know Your Legal Rights" | "اپنے قانونی حقوق جانیں"

// Category translation (backend enum → display)
translateCategory('Family Law', 'Urdu')  // → "خاندانی قانون"
translateCategory('Family Law', 'English')  // → "Family Law"

// RTL detection
isRTL('Urdu')    // → true
isRTL('English') // → false
```

**Fallback chain**: `strings[language][key]` → `strings['English'][key]` → `key` itself.

**Key count**: 160+ keys across 14 functional groups.

### 8.2 Category Translation Map

All 12 legal categories have Urdu display names. The English backend enum value is **never translated at API boundary** — only at the display layer.

| English Enum | Urdu Display |
|---|---|
| Family Law | خاندانی قانون |
| Criminal Law | فوجداری قانون |
| Labour Law | محنت کش قانون |
| Property Law | جائیداد قانون |
| Inheritance Law | وراثتی قانون |
| Cybercrime | سائبر کرائم |
| Harassment | ہراسانی |
| Civil Law / Procedure | دیوانی قانون |
| Contract Law | معاہداتی قانون |
| Consumer Rights | صارف حقوق |
| Constitutional Law | آئینی قانون |
| General / Other | عمومی / دیگر |

### 8.3 RTL Application Rules

RTL is applied **per-element**, not to the whole document.

| Element | Rule |
|---|---|
| Page container | `dir={rtl ? 'rtl' : 'ltr'}` |
| Sidebar | Always `dir="ltr"` (CSS safety rule) |
| Admin routes | Always LTR (tables, forms must not mirror) |
| Chat bubble rows | Always `dir="ltr"` — positions user/assistant independently of language |
| Bubble text content | `direction: rtl ? 'rtl' : 'ltr'`, `textAlign: rtl ? 'right' : 'left'` |
| English data rows (NGO names, phone, bar license, URLs) | Always `dir="ltr"` |
| Legal source excerpts | Always `dir="ltr"`, `textAlign:'left'` |
| Description fields (mixed content) | `dir="auto"` — browser detects script |
| CSS: RTL border flip | `[dir="rtl"] .border-l-4 { border-left: 0; border-right: 4px solid }` |
| Animation slide direction | `x: rtl ? 6 : -6` (slide from correct edge) |

**Font switching**: `[dir="rtl"] { font-family: var(--font-urdu) }` — Noto Nastaliq Urdu for RTL content.

---

## 9. Design System & Theming

### 9.1 Vite & Build Config

**`vite.config.js`**:
```javascript
resolve: { alias: { '@': path.resolve(__dirname, './src') } }
server: { port: 5173, proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } } }
```

The `@/` alias is used throughout the codebase for all imports from `src/`.

### 9.2 CSS Custom Properties (Design Tokens)

All visual values are defined as CSS custom properties in `:root` (dark defaults) and overridden by `[data-theme="light"]`.

**Colour tokens (dark mode)**:

| Token | Value | Usage |
|---|---|---|
| `--grad-primary` | `linear-gradient(135deg, #7C3AED 0%, #3B82F6 100%)` | Primary buttons, FAB |
| `--primary` | `#7C3AED` | Brand violet |
| `--accent` | `#22D3EE` | Cyan highlight |
| `--success` | `#10B981` | Green (available, success) |
| `--warning` | `#F59E0B` | Amber |
| `--danger` | `#EF4444` | Red |
| `--bg-page` | `#0B1120` | Page background |
| `--bg-surface` | `#111827` | Card backgrounds |
| `--bg-sidebar` | `#070d1a` | Sidebar (always dark) |
| `--text-primary` | `#F1F5F9` | Body text |
| `--text-secondary` | `rgba(241,245,249,0.75)` | Secondary text |
| `--text-muted` | `rgba(241,245,249,0.42)` | Hints, placeholders |
| `--border-default` | `rgba(255,255,255,0.10)` | Card borders |

**Light theme** (applied via `<html data-theme="light">`):

| Token | Light Override |
|---|---|
| `--bg-page` | `#F1F5F9` |
| `--bg-surface` | `#FFFFFF` |
| `--text-primary` | `#0F172A` |
| `--border-default` | `rgba(0,0,0,0.10)` |

The sidebar (`#070d1a`) and floating button remain dark in light mode.

**Theme toggle**: `toggleTheme()` in Zustand store → `AppLayout` applies `data-theme` attribute to `<html>`.

### 9.3 Glassmorphism Card Pattern

```css
.card {
  border-radius: 16px;
  background: rgba(255,255,255,0.05);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255,255,255,0.10);
  box-shadow: 0 4px 24px rgba(0,0,0,0.38),
              inset 0 1px 0 rgba(255,255,255,0.06);
}
```

KPI cards add hover lift: `translateY(-3px)` + enhanced glow border.

### 9.4 Animation Catalogue

| Name | Trigger | Effect |
|---|---|---|
| `shimmer` (1.6s ∞) | Skeleton loading | Gradient slide across placeholder |
| `pulse-glow` (2.5s ∞) | FAB pulsing ring | Box-shadow oscillation (#7C3AED) |
| `float` (4s ∞) | Hero decorative | translateY ±10px |
| `fade-in` (0.4s) | Page/component mount | opacity 0→1, y 8→0 |
| Framer Motion entrance | List items, cards | `opacity 0 + y/x` stagger (delay: i × 0.05) |
| Framer Motion hover | Buttons, cards | `scale(1.06)` + shadow |

### 9.5 Tailwind Config Highlights

**Dark mode**: class-based (`darkMode: ['class']`)  
**Custom font families**: `sans` (Inter), `mono` (system), `urdu` (Noto Nastaliq)  
**Custom breakpoints**: inherits Tailwind defaults (sm:640, md:768, lg:1024)  
**Category colour palette**: defined in `globals.css` as named constants (not Tailwind tokens) — EC4899, EF4444, F59E0B, 8B5CF6, 7C3AED, 06B6D4, F97316, 3B82F6, 10B981, 84CC16, 6366F1, 64748B

---

## 10. Security Model

### 10.1 Input Validation

**Backend** (`validator.py`):
- Strip non-printable characters (keep Arabic/Urdu Unicode)
- Length gate: `MIN_QUERY_LENGTH` ≤ len ≤ `MAX_QUERY_LENGTH` (from `.env`, defaults 15/2000)
- Injection blocklist: regex patterns for `"ignore previous"`, `"you are now"`, `"jailbreak"`, `"dan mode"`, and ~6 more
- Pydantic v2 validates session ID format (`^[\w\-]{1,128}$`) and language enum

**Frontend** (`ApplyPage`):
- Zod schema validates all form fields before submission
- Additional server error displayed inline from `err.response.data.detail`

### 10.2 Admin Authentication

- Admin login: `POST /api/admin/login` with password → returns opaque token
- Token stored in Zustand (persisted to localStorage)
- Injected as `X-Admin-Token` header via Axios interceptor on every request
- Server validates token on all admin endpoints
- No JWT; token format is server-defined (implementation in `main.py`)
- Frontend shows admin badge in topbar when `adminAuthenticated === true`

### 10.3 Prompt Injection Defence

Multi-layer:
1. **Input validation** — blocklist of common injection phrases (Gate 1)
2. **System prompt** — v5 prompt with explicit instructions not to change role or follow user instructions overriding it
3. **Low temperature** — 0.15 reduces creative reinterpretation of the system prompt
4. **No tool use** — LLM has no function-calling access; cannot exfiltrate or execute
5. **Context isolation** — session histories are in-memory per session_id; no cross-session leakage

### 10.4 CORS

Currently `allow_origins=["*"]`. For production deployment, restrict to the actual frontend domain.

### 10.5 Data Privacy

- Query logs stored in `users_logs` with no user identifier (anonymous)
- No session data written to disk (in-memory only, 1-hour TTL)
- CNIC field in applications is optional; no verification performed
- No cookies; auth via `Authorization`-style header

---

## 11. Performance Characteristics

### Build-time (one-off)

| Phase | Duration | Bottleneck |
|---|---|---|
| PDF parsing (all laws) | 30–60 s | pdfplumber I/O |
| Chunking | ~30 s | CPU (regex, string ops) |
| Embedding (first run, ~10k chunks) | 45–60 min | sentence-transformers CPU inference |
| Embedding (incremental, cache hit) | ~5 s | Only missed chunks re-encoded |
| FAISS index build | ~5 s | Vectors already in memory |
| Total first run | ~75 min | Embedding dominates |
| Total with warm cache | ~40 s | Parse + chunk |

### Runtime (per request)

| Operation | p50 | Bottleneck |
|---|---|---|
| Query embedding | ~50 ms | sentence-transformers (model cached in `lru_cache`) |
| FAISS search (5× over-fetch) | ~10 ms | In-memory, no I/O |
| Score boosting + filtering | ~20 ms | Python CPU |
| Groq LLM call | 2–5 s | Network + token generation |
| Chat endpoint (full) | 3–6 s | Groq call dominates |
| Analysis endpoint (full) | 4–8 s | Groq call dominates |
| TTS (ElevenLabs) | 1–3 s | Network |
| PDF generation | ~500 ms | ReportLab CPU |
| NGO list query | <10 ms | SQLite in-memory index |
| Document analysis (native PDF/DOCX) | 5–10 s | Groq call dominates; extraction is <200 ms |
| Document analysis (scanned image) | 8–20 s | Tesseract OCR + Groq call |
| Document analysis pipeline timeout | 120 s | `asyncio.wait_for` hard ceiling; returns HTTP 504 |

### Frontend

| Operation | Notes |
|---|---|
| Initial bundle | Vite production build with tree-shaking; pdfjs-dist is largest dep |
| Page transitions | Framer Motion (GPU-accelerated transform/opacity) |
| Filtering | `useMemo` in LawyersPage for client-side filter of loaded lawyer list |
| Analytics charts | Recharts SVG; no virtualisation needed for typical data size |

---

## 12. Key Architectural Decisions

### ADR-001: FAISS IndexFlatIP over approximate indexes

**Decision**: Use exact brute-force inner-product index, not HNSW or IVF.  
**Rationale**: Legal corpus is ~10k chunks — small enough that exhaustive search takes <10ms. Approximate indexes introduce non-determinism and require tuning parameters. At this scale the accuracy/speed trade-off does not justify added complexity.

### ADR-002: 5-gate anti-hallucination pipeline

**Decision**: Implement five sequential gates before the LLM is called; Gate 3a is a hard block.  
**Rationale**: Legal advice from invented statutes is harmful. The hard retrieval gate (3a) is the critical control: if FAISS returns no chunks scoring ≥0.42, the LLM is never invoked. Weak-context detection (3b) adds transparency without blocking (warns the LLM and user that context is thin).

### ADR-003: Separate index build phases with SHA-1 cache

**Decision**: Split `build_index.py` into chunks/embed/faiss phases; cache embeddings by SHA-1.  
**Rationale**: Embedding 10k chunks takes ~1 hour. If only law text changes (not chunking config), only changed chunks need re-encoding. The cache makes iterative corpus updates practical.

### ADR-004: In-memory session store with TTL

**Decision**: Chat session histories live in Python process memory, not in SQLite.  
**Rationale**: Sessions are short-lived (conversational) and do not need to survive server restart. Persisting to SQLite would add serialisation overhead and require periodic cleanup jobs. 1-hour TTL is enforced lazily on access.

### ADR-005: Deterministic NGO/lawyer routing (no LLM)

**Decision**: Application routing uses rule-based scoring against the DB; LLM is not consulted.  
**Rationale**: Routing decisions must be auditable and reproducible. An LLM would add latency, cost, and non-determinism to a path that requires no language understanding.

### ADR-006: Sidebar always LTR in RTL mode

**Decision**: The sidebar never flips direction even when Urdu is active.  
**Rationale**: Navigation and controls are positionally fixed for usability. Sidebar content (nav labels) is already localised via `t()`; physical position does not need to mirror. A CSS rule `.sidebar { direction: ltr; }` enforces this.

### ADR-007: English data rows inside RTL pages

**Decision**: NGO names, lawyer names, bar licenses, phone numbers, URLs, and law source excerpts always render `dir="ltr"` even in Urdu mode.  
**Rationale**: This data is English proper nouns/identifiers. Rendering them RTL produces garbled character order. Per-element LTR locks prevent this while surrounding Urdu UI text remains RTL.

### ADR-008: Chat bubble rows always LTR

**Decision**: The `<div>` wrapping each chat bubble row has `dir="ltr"` regardless of page language.  
**Rationale**: Chat layout uses `flex-row-reverse` to put user messages on the right. In an RTL container, `flex-row` already starts from the right, so `flex-row-reverse` would put user bubbles on the left — the opposite of intent. Row-level LTR lock ensures consistent left (assistant) / right (user) positions.

### ADR-009: TTS fallback chain

**Decision**: Three TTS backends tried in priority order (ElevenLabs → espeak-ng → gTTS).  
**Rationale**: High-quality TTS (ElevenLabs) is optional and API-key gated. The system must still function without it. espeak-ng provides offline capability; gTTS provides a network fallback. The chain ensures TTS degrades gracefully without hard-failing the chat feature.

### ADR-010: SQLite over PostgreSQL

**Decision**: SQLite for all persistent data (NGOs, lawyers, applications, logs).  
**Rationale**: Single-server deployment with no horizontal scaling requirement. SQLite eliminates an external service dependency and simplifies deployment (single file). WAL mode would be needed for concurrent writes at higher load.

### ADR-011: `translateCategory()` is display-only

**Decision**: Backend enum values (`'Family Law'`, `'Criminal Law'`, etc.) are never translated at the API boundary — only in the React display layer.  
**Rationale**: All backend logic (routing, filtering, DB queries, RAG category boosting) operates on English enum values. Translating at the API would require every backend service to handle Urdu strings, massively increasing coupling.

### ADR-012: Document analysis pipeline runs in `run_in_executor` under `asyncio.wait_for`

**Decision**: The three synchronous pipeline steps (extract_text, classify_document, analyze_document_with_rag) are wrapped in `loop.run_in_executor(None, fn, *args)` and the whole pipeline is guarded by `asyncio.wait_for(..., timeout=120)`.  
**Rationale**: All pipeline functions are synchronous (pdfplumber, python-docx, pytesseract, Groq SDK). Calling them directly in an `async def` endpoint would block the event loop. `run_in_executor` offloads them to a thread pool while keeping the endpoint awaitable and timeout-safe. The 120-second ceiling prevents runaway OCR or slow Groq calls from holding a worker indefinitely.

### ADR-013: `legal_analysis: null` sentinel instead of error object for short-text documents

**Decision**: When extracted text is fewer than 20 characters, the endpoint returns `legal_analysis: null` (not an error object or an empty `DocumentAnalysis`).  
**Rationale**: Returning an error object would cause the frontend to display a warning banner alongside empty "None found" sections, confusing the user. `null` allows the frontend to render a clean info alert ("text too short for AI analysis") that is visually distinct from both success and failure states. The distinction is: `null` = analysis deliberately skipped; `{"error": "..."}` = analysis attempted but failed.

### ADR-014: Document-type allowlists in `groq_client.py`, not `rag_engine.py`

**Decision**: The per-document-type category allowlists and higher score floors are implemented as a post-retrieval filter (`_filter_chunks_for_document`) scoped entirely to `groq_client.py`. `rag_engine.retrieve()` is not modified.  
**Rationale**: `rag_engine.retrieve()` is shared by the chat pipeline, the main analysis pipeline, and the document analysis pipeline. Adding document-type-specific logic there would require conditional branching across unrelated callers and could regress existing behaviour. A post-retrieval filter is a minimal, isolated change that cannot affect any other pipeline.

---

## 13. Known Limitations & Trade-offs

| Limitation | Impact | Mitigation / Future Work |
|---|---|---|
| **No Urdu PDF embedding** | Urdu-script law texts skipped by `ingest.py` | Would require a multilingual embedding model (e.g., `paraphrase-multilingual-mpnet-base-v2`) or translation pipeline |
| **In-memory sessions** | Chat history lost on server restart | Move to Redis or SQLite-backed sessions for production |
| **Single Groq model** | All requests share one API key; Groq rate limits apply | Implement request queuing or multi-key rotation |
| **No streaming responses** | Chat reply appears after full Groq response | Add SSE/WebSocket streaming for perceived responsiveness |
| **CORS allows all origins** | Security risk in production | Restrict to specific frontend domain in `.env` |
| **Admin password in `.env`** | Plain-text; no RBAC | Move to JWT with expiry; add multi-admin support |
| **SHA-1 embedding cache** | SHA-1 not collision-resistant | Acceptable for non-security use; could upgrade to SHA-256 |
| **Lazy FAISS load** | First request after restart waits for index load (~2–5 s) | Pre-load index at startup in `@app.on_event("startup")` |
| **PDF Urdu bidi rendering** | Complex glyphs may mis-wrap at edge cases | Custom Nastaliq word-shaping library would improve fidelity |
| **`languageChosen` flag unused** | Dead state in Zustand store | Remove in cleanup or implement redirect-to-picker logic |
| **`LanguageSelector` re-exports CitySelector** | Confusing module organisation | Separate into distinct files |
| **No content moderation** | Users could submit harmful queries that pass injection filter | Add secondary moderation layer for sensitive categories |
| **SQLite write contention** | Heavy concurrent writes to `users_logs` could queue | Enable WAL mode (`PRAGMA journal_mode=WAL`) |
| **Chunk size fixed at 800 chars** | Long sections split at non-ideal points | Experiment with semantic chunking (split on sentence similarity drop) |
| **Tesseract required for OCR** | Image / scanned-PDF uploads fail silently if Tesseract is not installed as a system binary | Bundle Tesseract in a Docker image; document install steps clearly |
| **No multi-page image support** | Image uploads are treated as single pages; multi-page scanned documents must be uploaded as PDF | Add PDF-from-images conversion (Pillow `save(..., format='PDF')`) |
| **Document analysis text capped at 50 000 chars** | Very long contracts or court orders may be truncated before LLM analysis | Implement sliding-window chunked analysis with result merging |
| **No document analysis PDF export** | Users can't download the document analysis report | Add a `/api/analyze-document-pdf` endpoint using the existing PDF generator |
| **Magic-byte check is warn-only** | A mismatched magic header logs a warning but does not reject the file; actual rejection relies on the extraction library | Promote to a rejecting gate for stricter security hardening |
