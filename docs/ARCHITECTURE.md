# Architecture Overview

## System Design

```
Browser (React SPA)
      │
      │  HTTP / JSON  (Vite proxy in dev, direct in prod)
      ▼
FastAPI Backend (main.py)
      │
      ├── /api/analyze    → groq_client.py + rag_engine.py
      ├── /api/chat       → chat_service.py
      ├── /api/applications → application_service.py
      ├── /api/ngos       → ngo_service.py
      ├── /api/lawyers    → lawyer_service.py
      ├── /api/tts        → tts.py
      ├── /api/pdf        → pdf_generator.py
      ├── /api/transcribe → groq_client.transcribe_audio()
      └── /api/analytics  → db.py
```

## RAG Pipeline

1. User submits query (React) → POST /api/analyze
2. FastAPI validates + sanitizes via `validator.py`
3. `rag_engine.preprocess_query()` expands the query
4. `rag_engine.retrieve()` → FAISS cosine-similarity search over law chunks
5. Top-K chunks passed to `groq_client.analyze_with_rag()`
6. Groq Llama 3.3 70B generates grounded response
7. `ngo_matcher.recommend_ngos()` suggests relevant NGOs
8. Full structured response returned to React frontend

## Data Flow

```
Law PDFs (data/laws/)
    │
    ▼ build_index.py
Chunks (data/chunks.json)
    │
    ▼ sentence-transformers
Embeddings (data/embeddings_cache.npz)
    │
    ▼ faiss
FAISS Index (data/faiss_index/)
    │
    ▼ rag_engine.retrieve()
Context chunks → Groq LLM → Structured JSON response
```

## Frontend Architecture

- **Zustand** store with persistence for language, city, admin auth, chat session
- **React Router v6** for client-side navigation
- **Axios** with Vite proxy for API calls (no CORS issues in dev)
- **Framer Motion** for page transitions and micro-animations
- **Tailwind CSS** with custom design tokens matching the HTML design spec
- **Recharts** for analytics visualizations
- **React Hook Form + Zod** for form validation

## Key Design Decisions

1. **Thin API layer**: `main.py` is purely a FastAPI wrapper. All business logic stays in `app/utils/`
2. **No LLM rebuilds**: The original Groq/RAG pipeline is reused 100%
3. **Streamlit removed**: Only the 2–3 `@st.cache_resource` decorators were replaced with `@functools.lru_cache`
4. **Persistent state**: Zustand persists language and admin auth to localStorage
5. **RTL support**: `dir="rtl"` applied at container level for Urdu, Tailwind handles layout
