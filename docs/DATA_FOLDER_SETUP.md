# Data Folder Setup

## Your existing `data/` folder goes here:

```
legal-aid-react/
└── backend/
    └── data/                ← PLACE YOUR DATA FOLDER HERE
        ├── faiss_index/     ← your existing faiss_index/ folder
        │   ├── index.bin
        │   └── metadata.json
        ├── Laws/            ← your existing Laws/ folder (PDF datasets)
        ├── chunks.json      ← your existing file
        ├── embeddings_cache.json  ← your existing file
        ├── embeddings_cache.npz   ← your existing file
        ├── helplines.json   ← your existing file (already included)
        └── ngos.json        ← your existing file (already included)
```

## Steps

1. Copy your entire `data/` folder from the old project into `backend/`
2. The folder structure must be exactly as shown above
3. Because your `faiss_index/`, `chunks.json`, and `embeddings_cache.*` already exist,
   you do NOT need to run `build_index.py` again — skip straight to running the backend.

## If you DO need to rebuild the index

Only necessary if you add new law PDFs to `data/Laws/`:

```cmd
cd backend
venv\Scripts\activate
python build_index.py
```

## Verification

After placing the data folder, start the backend and check:

    http://localhost:8000/api/health

You should see:
```json
{
  "status": "ok",
  "rag_ready": true,
  "groq_ready": true
}
```

If `rag_ready` is `false`, the `faiss_index/` folder is missing or in the wrong location.
