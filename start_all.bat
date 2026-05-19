@echo off
title Legal Aid — Launcher
color 0E
setlocal

set "ROOT=%~dp0"

echo.
echo  ========================================
echo   Pakistan AI Legal Aid Assistant
echo   Starting all services...
echo  ========================================
echo.

:: ── Check Python ────────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found.
    echo [FIX]   Install from https://python.org  ^(check "Add Python to PATH"^)
    pause
    exit /b 1
)

:: ── Check Node.js ────────────────────────────────────────────────
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found.
    echo [FIX]   Install from https://nodejs.org
    pause
    exit /b 1
)

echo [OK] Python and Node.js detected.
echo.

:: ── Set up Python virtual environment (first run only) ───────────
if not exist "%ROOT%backend\venv\Scripts\activate.bat" (
    echo [INFO] Creating Python virtual environment for the first time...
    cd /d "%ROOT%backend"
    python -m venv venv
    call venv\Scripts\activate
    echo [INFO] Installing Python packages ^(may take several minutes^)...
    pip install -r requirements.txt
    cd /d "%ROOT%"
)

:: ── Create .env from template if missing ─────────────────────────
if not exist "%ROOT%backend\.env" (
    echo [WARN] backend\.env not found. Creating from template...
    copy "%ROOT%backend\.env.example" "%ROOT%backend\.env" >nul
    echo.
    echo  *** ACTION REQUIRED ***
    echo  Open backend\.env and fill in your GROQ_API_KEY.
    echo  Get a free key at:  https://console.groq.com
    echo.
    notepad "%ROOT%backend\.env"
    echo  Press any key once you have saved your API key...
    pause >nul
)

:: ── Install frontend packages (first run only) ───────────────────
if not exist "%ROOT%frontend\node_modules" (
    echo [INFO] Installing frontend packages ^(first time only — 1-3 min^)...
    cd /d "%ROOT%frontend"
    npm install
    cd /d "%ROOT%"
)

:: ── Check FAISS index ────────────────────────────────────────────
set "INDEX_OK=0"
if exist "%ROOT%backend\data\faiss_index\index.bin" (
    if exist "%ROOT%backend\data\faiss_index\metadata.json" (
        set "INDEX_OK=1"
    )
)

if "%INDEX_OK%"=="0" (
    echo [INFO] FAISS index not found. Building now ^(5-15 min first run^)...
    cd /d "%ROOT%backend"
    call venv\Scripts\activate
    python build_index.py
    cd /d "%ROOT%"
) else (
    echo [OK] FAISS index found.
)

echo.
echo [START] Launching backend in a new window...
start "Legal Aid — Backend (port 8000)" cmd /k "%ROOT%start_backend.bat"

echo [WAIT]  Giving backend 5 seconds to start up...
timeout /t 5 /nobreak >nul

echo [START] Launching frontend in a new window...
start "Legal Aid — Frontend (port 5173)" cmd /k "%ROOT%start_frontend.bat"

timeout /t 4 /nobreak >nul

echo.
echo  ========================================
echo   All services running!
echo.
echo   Frontend  →  http://localhost:5173
echo   Backend   →  http://localhost:8000
echo   API Docs  →  http://localhost:8000/api/docs
echo   Health    →  http://localhost:8000/api/health
echo  ========================================
echo.
echo  Two windows have opened — one for each server.
echo  Keep both windows open while using the app.
echo  Close them (or press Ctrl+C inside each) to stop the servers.
echo.
start http://localhost:5173
pause
endlocal
