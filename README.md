# ⚖️ Pakistan AI Legal Aid Assistant

> RAG-powered multilingual legal guidance for Pakistan  
> **React 18 · FastAPI · Groq LLM · FAISS · English / اردو**

A full-stack AI legal aid application that helps Pakistani citizens understand their legal rights. Users describe a legal problem in English or Urdu and receive a risk assessment, applicable law citations, rights summary, recommended NGOs, and a matched lawyer list — all driven by retrieval-augmented generation over a corpus of Pakistani law documents.

---
Live Demo: https://legal-aid-react.vercel.app/

## Features

| Feature | Description |
|---|---|
| **AI Legal Analysis** | Describes case in natural language; Groq Llama 3.3 70B classifies, retrieves relevant law chunks via FAISS, and generates a structured report |
| **RAG Pipeline** | FAISS cosine-similarity search over sentence-transformer embeddings of Pakistani law PDFs |
| **Multilingual UI** | Full English and Urdu support; Urdu mode is RTL-aware throughout (chat bubbles, cards, filters, forms) |
| **Voice Input** | Microphone recording + Groq Whisper transcription; .wav/.mp3 file upload also supported |
| **Text-to-Speech** | Listen to AI response via ElevenLabs (if key provided) or gTTS fallback |
| **PDF Export** | Download full analysis report as PDF (ReportLab, Urdu-compatible via arabic-reshaper + bidi) |
| **Multi-turn Chat** | Contextual follow-up questions on the current analysis result |
| **NGO Directory** | Searchable, filterable registry of legal aid NGOs with city + practice area filters |
| **Lawyer Directory** | Registry of lawyers with expertise, city, availability, and bar license |
| **Case Applications** | Citizens submit formal case applications routed to matching NGOs |
| **Admin Dashboard** | Password-protected panel for managing NGOs, lawyers, applications, and viewing analytics |
| **Emergency Page** | Step-by-step guidance and emergency hotlines (Police 15, Rescue 1122, Edhi 115, etc.) |
| **Document Analysis** | Upload a legal document (PDF, DOCX, image) — AI extracts text via OCR, classifies the document type, retrieves relevant law, and returns a structured legal breakdown with key obligations, deadlines, risks, and citations |

---

## Tech Stack

### Frontend

| Library | Purpose |
|---|---|
| React 18 + Vite 5 | UI framework + build tool (SWC plugin) |
| TailwindCSS | Utility-first styling with custom CSS variables for light/dark tokens |
| Framer Motion | Page transitions, card animations, RTL-aware slide-in effects |
| Zustand | Global state (language, theme, chat messages, analysis result, session ID) |
| Recharts | Admin analytics charts |
| React Hook Form + Zod | Case application form validation |
| lucide-react | Icon library |
| pdfjs-dist + mammoth | Client-side PDF and .docx text extraction for document upload |
| axios | HTTP client with `/api` proxy to backend |

### Backend

| Library | Purpose |
|---|---|
| FastAPI + Uvicorn | ASGI web framework |
| Groq SDK | Llama 3.3 70B (chat + analysis) + Whisper (speech-to-text) |
| FAISS (CPU) | Vector similarity search over law document embeddings |
| Sentence Transformers | `all-MiniLM-L6-v2` embeddings for RAG retrieval |
| SQLite | Persistent storage for NGOs, lawyers, applications, chat sessions |
| ReportLab | PDF generation with full Urdu/Arabic text support |
| arabic-reshaper + python-bidi | Proper Urdu ligature shaping for PDFs |
| ElevenLabs / gTTS | Text-to-speech synthesis (ElevenLabs preferred, gTTS fallback) |
| pdfplumber + pypdf | Server-side PDF text extraction for document analysis |
| python-docx | DOCX text extraction for document analysis |
| Pillow | Image loading and preprocessing for OCR |
| pytesseract | Tesseract OCR wrapper — extracts text from scanned documents and images |
| opencv-python-headless | Image preprocessing (deskew, threshold, denoise) before OCR |

---

## Repository Structure

```
legal-aid-react/
├── frontend/                        ← React + Vite application
│   ├── src/
│   │   ├── pages/
│   │   │   ├── HomePage.jsx         ← Main analysis page (voice, file, text input)
│   │   │   ├── ChatPage.jsx         ← Full-page multi-turn chat
│   │   │   ├── ApplyPage.jsx        ← Case application submission form
│   │   │   ├── EmergencyPage.jsx    ← Emergency numbers + step-by-step guidance
│   │   │   ├── AboutPage.jsx        ← Project overview
│   │   │   ├── NGOPage.jsx          ← NGO directory with filters
│   │   │   ├── LawyersPage.jsx      ← Lawyer directory with filters
│   │   │   ├── DocumentAnalysisPage.jsx ← Upload + AI analysis of legal documents
│   │   │   ├── LanguagePicker.jsx   ← Entry screen (English / Urdu selection)
│   │   │   └── admin/               ← Admin dashboard pages (protected)
│   │   ├── components/
│   │   │   ├── chat/
│   │   │   │   ├── AIAssistantDrawer.jsx  ← Sliding chat panel (overlay)
│   │   │   │   ├── ChatAssistant.jsx      ← Inline chat component
│   │   │   │   └── SourcesPanel.jsx       ← Retrieved law sources sidebar
│   │   │   ├── analytics/
│   │   │   │   └── NGOList.jsx            ← NGO result cards in analysis output
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.jsx
│   │   │   │   └── TopBar.jsx
│   │   │   └── ui/
│   │   │       ├── index.jsx              ← SectionHeader, Card, Badge, Spinner, EmptyState
│   │   │       └── FloatingAIButton.jsx   ← FAB to open AI drawer
│   │   └── services/
│   │       ├── api.js               ← All backend API calls (axios)
│   │       ├── store.js             ← Zustand global store
│   │       └── i18n.js              ← Translation strings (160+ keys) + translateCategory()
│   ├── vite.config.js               ← /api proxy → http://localhost:8000
│   └── package.json
│
├── backend/                         ← FastAPI server
│   ├── main.py                      ← API routes entry point
│   ├── build_index.py               ← FAISS index builder (run once)
│   ├── app/
│   │   └── utils/                   ← Business logic modules
│   │       ├── groq_client.py       ← Groq LLM calls + Whisper transcription
│   │       ├── rag_engine.py        ← FAISS search + chunk retrieval
│   │       ├── chat_service.py      ← Multi-turn chat with session memory
│   │       ├── pdf_generator.py     ← PDF export with Urdu support
│   │       ├── ngo_service.py       ← NGO CRUD + SQLite
│   │       ├── lawyer_service.py    ← Lawyer CRUD + SQLite
│   │       ├── application_service.py ← Case application routing
│   │       ├── tts.py               ← ElevenLabs / gTTS text-to-speech
│   │       ├── document_loader.py   ← Upload validation, type detection, temp file management
│   │       ├── text_extractor.py    ← PDF / DOCX / image text extraction (OCR)
│   │       ├── document_classifier.py ← Rule-based + LLM fallback document type classification
│   │       ├── image_preprocessor.py  ← OpenCV preprocessing for OCR (deskew, threshold)
│   │       └── ...                  ← Additional utility modules
│   ├── data/
│   │   ├── faiss_index/             ← Built by build_index.py
│   │   ├── Laws/                    ← Pakistani law PDF corpus
│   │   ├── chunks.json              ← Processed law text chunks
│   │   ├── helplines.json           ← Emergency helpline data
│   │   └── ngos.json                ← Initial NGO seed data
│   ├── .env.example
│   └── requirements.txt
│
├── start_all.bat                    ← One-click start: sets up venv, builds index, opens both servers
├── start_backend.bat                ← Start backend only (activates venv, checks index, runs main.py)
├── start_frontend.bat               ← Start frontend only (npm install if needed, npm run dev)
├── run_project.bat                  ← Legacy launcher (use start_all.bat instead)
├── run_project.sh                   ← One-click start (macOS / Linux)
└── README.md
```

---

## Setup — Windows

### Prerequisites

| Requirement | Version | Download |
|---|---|---|
| Python | 3.11.x | https://www.python.org/downloads/ |
| Node.js | 20 LTS | https://nodejs.org/en/download |
| Groq API Key | — | https://console.groq.com |
| Tesseract OCR | 5.x (optional) | Required for scanned PDFs and image uploads — see Troubleshooting |

> **Python install tip:** Check **"Add Python to PATH"** during installation.

### 1 — Clone and enter the project

```cmd
git clone <repo-url>
cd legal-aid-react
```

### 2 — Backend setup

```cmd
cd backend
python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
```

Copy and fill in environment variables:

```cmd
copy .env.example .env
notepad .env
```

Required `.env` values:

```
GROQ_API_KEY=gsk_your_key_here
ELEVENLABS_API_KEY=                  # optional — gTTS used if blank
ADMIN_PASSWORD=choose_a_password
MAX_QUERY_LENGTH=2000
MIN_QUERY_LENGTH=15
```

### 3 — Build the RAG index

**Skip this step if you already have a `data/faiss_index/` folder.**

```cmd
python build_index.py
```

Processes all PDFs in `data/Laws/` and writes the FAISS index. Takes 5–15 minutes on first run.

### 4 — Start the backend

```cmd
python main.py
```

API is available at http://localhost:8000  
Interactive docs: http://localhost:8000/api/docs

### 5 — Frontend setup

Open a second terminal:

```cmd
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 in your browser.

### One-click start (Windows)

`start_all.bat` handles the full setup and startup automatically — including venv creation, package installation, FAISS index building (first run only), and opening both servers:

```cmd
start_all.bat            # recommended — handles everything, opens browser automatically
```

Or launch each service individually:

```cmd
start_backend.bat        # backend only  (FastAPI on port 8000)
start_frontend.bat       # frontend only (Vite on port 5173)
```

---

## Setup — macOS / Linux

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env with your values
python build_index.py    # skip if faiss_index/ already exists
python main.py &

cd ../frontend
npm install
npm run dev
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | Yes | — | Groq API key for Llama 3.3 70B and Whisper |
| `ELEVENLABS_API_KEY` | No | — | ElevenLabs TTS key; gTTS fallback used if omitted |
| `ADMIN_PASSWORD` | Yes | `admin123` | Password for the admin dashboard |
| `MAX_QUERY_LENGTH` | No | `2000` | Maximum characters for a legal query |
| `MIN_QUERY_LENGTH` | No | `15` | Minimum characters for a legal query |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/analyze` | Analyze a legal case (text) → classification, risk, laws, NGOs |
| `POST` | `/api/transcribe` | Transcribe audio file via Groq Whisper |
| `POST` | `/api/chat` | Multi-turn chat with session memory |
| `GET` | `/api/tts` | Generate TTS audio for a text string |
| `POST` | `/api/export-pdf` | Generate and download analysis PDF |
| `GET` | `/api/ngos` | List NGOs (supports `city` and `category` query params) |
| `POST` | `/api/ngos` | Create NGO (admin) |
| `PUT` | `/api/ngos/{id}` | Update NGO (admin) |
| `DELETE` | `/api/ngos/{id}` | Delete NGO (admin) |
| `GET` | `/api/lawyers` | List lawyers |
| `POST` | `/api/lawyers` | Create lawyer (admin) |
| `PUT` | `/api/lawyers/{id}` | Update lawyer (admin) |
| `DELETE` | `/api/lawyers/{id}` | Delete lawyer (admin) |
| `POST` | `/api/analyze-document` | Upload a document (PDF/DOCX/image) → extract text, classify type, retrieve law, return structured legal analysis |
| `POST` | `/api/apply` | Submit a case application |
| `GET` | `/api/applications` | List applications (admin) |
| `GET` | `/api/analytics` | Dashboard analytics data (admin) |
| `POST` | `/api/admin/login` | Admin authentication |

---

## Multilingual / RTL Support

The application ships with full English and Urdu support. Language is chosen on the landing screen and persists in Zustand state.

**How it works:**

- `src/services/i18n.js` holds 250+ translation keys per language
- `useT()` hook returns the correct string for the active language
- `isRTL(language)` returns `true` for Urdu
- `translateCategory(name, language)` maps English backend enum values to Urdu display names — backend values are always English
- Page containers: `dir={rtl ? 'rtl' : 'ltr'}`
- English data rows (NGO names, lawyer names, bar licenses, phone numbers, URLs): always `dir="ltr"`
- Chat bubble rows: always `dir="ltr"` so user (right) / assistant (left) positions are consistent
- Description fields with mixed content: `dir="auto"`
- Animation slide direction: `x: rtl ? 6 : -6` pattern

**Supported practice area categories (bilingual):**

| English | Urdu |
|---|---|
| Family Law | خاندانی قانون |
| Criminal Law | فوجداری قانون |
| Labour Law | مزدور قانون |
| Property Law | جائیداد قانون |
| Inheritance Law | وراثت قانون |
| Cybercrime | سائبر کرائم |
| Harassment | ہراساں کرنا |
| Civil Law / Procedure | دیوانی قانون |
| Contract Law | معاہدہ قانون |
| Consumer Rights | صارف کے حقوق |
| Constitutional Law | آئینی قانون |
| General / Other | عمومی / دیگر |

---

## Application Routes

| Path | Component | Description |
|---|---|---|
| `/` | LanguagePicker | Entry screen — choose English or Urdu |
| `/home` | HomePage | Main legal analysis tool |
| `/chat` | ChatPage | Full-page multi-turn AI chat |
| `/apply` | ApplyPage | Case application form |
| `/emergency` | EmergencyPage | Emergency contacts + guidance steps |
| `/about` | AboutPage | Project information |
| `/ngos` | NGOPage | NGO directory |
| `/lawyers` | LawyersPage | Lawyer directory |
| `/document-analysis` | DocumentAnalysisPage | Upload and AI-analyse a legal document |
| `/admin` | Admin (protected) | Admin dashboard |

---

## RAG Pipeline

```
User Query (text or voice)
        │
        ▼
Groq Whisper (if audio)
        │
        ▼
Sentence Transformer embeddings
        │
        ▼
FAISS cosine-similarity search over law chunks
        │
        ├── Top-K relevant law passages
        │
        ▼
Groq Llama 3.3 70B
  · System prompt with retrieved context
  · Output: category, risk level, rights, next steps
        │
        ▼
Structured JSON response
  ├── category (English enum)
  ├── risk_level
  ├── summary
  ├── applicable_laws[]
  ├── rights[]
  ├── next_steps[]
  ├── ngos[] (matched by category + city)
  └── sources[] (FAISS chunk references + similarity scores)
```

---

## Production Build

```cmd
cd frontend
npm run build                        # outputs to frontend/dist/

cd ../backend
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

The FastAPI backend serves the built `dist/` static files in production mode.

---

## Troubleshooting

**`GROQ_API_KEY is not set`**  
→ Fill in the key in `backend/.env` and restart the backend.

**`RAG index not ready. Run build_index.py first.`**  
→ Run `python build_index.py` from inside `backend/` with venv activated. Ensure law PDFs exist in `data/Laws/`.

**`Module not found` errors**  
→ Confirm you are inside `backend/` and venv is active (`venv\Scripts\activate`).  
→ Try `pip install -r requirements.txt --upgrade`.

**Backend port 8000 already in use**  
→ Change port: `uvicorn main:app --port 8001`  
→ Update `frontend/vite.config.js` proxy target to match.

**Frontend cannot reach backend**  
→ Confirm backend is running at http://localhost:8000.  
→ Check `frontend/vite.config.js` has `proxy: { '/api': 'http://localhost:8000' }`.

**`pip` not recognized**  
→ Python was not added to PATH. Reinstall Python and check "Add to PATH".

**`npm` not recognized**  
→ Node.js was not installed. Reinstall from nodejs.org.

**Urdu text garbled in exported PDF**  
→ Ensure `arabic-reshaper` and `python-bidi` are installed: `pip install arabic-reshaper python-bidi`

**`TesseractNotFoundError` / OCR not working in Document Analysis**  
→ Tesseract OCR must be installed separately — it is a system binary, not a pip package.  
→ Windows: download the installer from https://github.com/UB-Mannheim/tesseract/wiki and add the install directory (e.g. `C:\Program Files\Tesseract-OCR`) to your PATH.  
→ macOS: `brew install tesseract`  
→ Ubuntu / Debian: `sudo apt install tesseract-ocr`  
→ OCR is only required for scanned PDFs and image uploads; native PDFs and DOCX files work without Tesseract.

**Audio / voice not working**  
→ Browser microphone permission must be granted.  
→ `.wav` and `.mp3` file upload works via the upload button as an alternative.  
→ Transcription requires a valid `GROQ_API_KEY`.

---

## Quick Reference

```cmd
# Backend
cd backend
venv\Scripts\activate
python build_index.py              # build RAG index (first time or after adding new PDFs)
python main.py                     # start server
uvicorn main:app --reload          # dev mode with auto-reload

# Frontend
cd frontend
npm install                        # first time
npm run dev                        # development server (http://localhost:5173)
npm run build                      # production build
npm run preview                    # preview production build locally
```

---

## License

This project is built for educational and legal aid purposes.  
⚠️ Always consult a qualified legal professional for case-specific advice.
