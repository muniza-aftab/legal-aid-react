# Localhost, Vercel and Render

Use Python 3.11 and Node 22.13 or newer. Keep API keys and databases out of Git. The frontend and backend must be released together because chat now uses server-issued session tokens.

## Local setup

From the repository root, in PowerShell:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env # only when .env does not already exist
# Edit .env: configure GROQ_API_KEY and a unique ADMIN_PASSWORD.
.\venv\Scripts\python.exe build_index.py # when the index is missing
.\venv\Scripts\python.exe main.py
```

In a second terminal:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open `http://localhost:5173`. Vite forwards `/api` to `http://127.0.0.1:8000`. Set `BACKEND_URL` if using another backend port, for example `$env:BACKEND_URL='http://127.0.0.1:8001'`. Leave `VITE_API_URL` unset for the proxy. The Windows `start_all.bat` and legacy `run_project.bat` also launch the app; run the dependency installation commands above after pulling updates.

For a local production build, run `npm.cmd run build`, then `npm.cmd run preview` in `frontend` while the backend is running. Preview uses port 4173 and the same API proxy. The backend also serves `frontend/dist` when that directory exists alongside it.

## Vercel frontend

The connected Git repository is `muniza-aftab/legal-aid-react`. Production is `https://legal-aid-react.vercel.app`.

- Framework: Vite; Node 22.x.
- If Root Directory is `frontend`: Install `npm ci`, Build `npm run build`, Output `dist`. `frontend/vercel.json` applies.
- If Root Directory is the repository root: root `vercel.json` sets the frontend install/build/output paths.
- Leave `VITE_API_URL` unset to use the `/api` rewrite to `https://legal-aid-react.onrender.com`. An existing explicit value may use that same backend origin, without a trailing `/api`.
- Both configurations include the SPA rewrite so direct visits to `/home`, `/document-analysis` and other React routes work. See [Vercel's Vite deployment guidance](https://vercel.com/docs/frameworks/frontend/vite).

## Render backend and existing data

Use the existing service `https://legal-aid-react.onrender.com`. Docker configuration: root directory `backend`, Dockerfile `Dockerfile`, health path `/api/health`. The image installs native English/Urdu Tesseract and builds the FAISS index; build errors stop the deploy. Startup honors Render's `PORT`. Use one worker: chat history is currently held in process memory.

Before deploying over an existing service, verify and back up its current SQLite database. Set `DATABASE_PATH` to the path that actually contains the existing database on the mounted disk. Changing the path to a new empty file will create an empty registry. If moving data, copy the backup into the new disk path before starting the new version. Do not replace the hosted database with a development database.

Required settings:

| Setting | Value |
| --- | --- |
| `GROQ_API_KEY` | Existing valid Groq key |
| `ADMIN_PASSWORD` | Unique password; no default password is accepted |
| `DATABASE_PATH` | Existing persistent database path, e.g. `/var/data/legal-aid/database.db` |
| `STORE_QUERY_TEXT` | `false` for aggregate analytics without new raw query/summary storage |
| `GROQ_LLM_MODEL` | `openai/gpt-oss-120b`, or a model available to your Groq account |
| `GROQ_FAST_MODEL` | `openai/gpt-oss-20b` |
| `CORS_ORIGINS` | Production Vercel origin plus the specific preview/local origins used for direct API access |
| `ELEVENLABS_API_KEY` | Optional; speech has a gTTS fallback |

Render's default filesystem loses changes on redeploy/restart. Persistent disks require a paid service; only files inside the mount path persist. See [Render disk documentation](https://render.com/docs/disks). Adding a disk itself triggers deployment, so take a backup first. This project does not silently provision paid resources.

The backend creates missing tables and adds columns to existing databases. It preserves historical cases, NGOs, lawyers and logs. Historical raw logs are retained; `STORE_QUERY_TEXT=false` affects new entries. A new database starts with an empty admin-managed directory; populate and validate the registry before relying on automatic case assignment.

## Release verification

1. Confirm Render's database backup, mount path and admin setting; deploy the backend commit and watch build/runtime logs.
2. Wait for `/api/health` to show `rag_ready: true` and `groq_ready: true`. Basic health can respond while the embedding model warms.
3. Verify unauthenticated application/analytics reads return 401 and admin login works using the configured password. Confirm existing record counts are preserved without copying private records into test output.
4. Deploy the matching frontend commit. Open and refresh every public route directly, including `/home` and `/document-analysis`.
5. Check public directories and one synthetic English/Urdu analysis, document, chat and speech request. Run production mutation tests only in a disposable staging database; the browser suite creates synthetic applications and registry entries.

For a rollback, use the hosts' previous known-good deployments while keeping the database backup. Do not discard case data as part of rollback.
