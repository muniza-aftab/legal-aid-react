@echo off
title Pakistan AI Legal Aid - Launcher
color 0A

echo.
echo  ========================================
echo   Pakistan AI Legal Aid Assistant
echo   React + FastAPI Edition
echo  ========================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install from https://python.org
    pause
    exit /b 1
)

:: Check Node
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Install from https://nodejs.org
    pause
    exit /b 1
)

echo [OK] Python and Node.js found.
echo.

:: Check .env
if not exist "backend\.env" (
    echo [WARN] backend\.env not found. Copying from .env.example...
    copy "backend\.env.example" "backend\.env"
    echo [ACTION] Please edit backend\.env and add your GROQ_API_KEY
    notepad "backend\.env"
    echo Press any key after saving .env to continue...
    pause
)

:: Setup venv
if not exist "backend\venv" (
    echo [INFO] Creating Python virtual environment...
    cd backend
    python -m venv venv
    call venv\Scripts\activate
    echo [INFO] Installing Python dependencies (this may take a few minutes)...
    pip install -r requirements.txt
    cd ..
)

:: Build index ONLY if faiss_index folder is missing or empty
set INDEX_MISSING=0
if not exist "backend\data\faiss_index" set INDEX_MISSING=1
if %INDEX_MISSING%==0 (
    dir /b "backend\data\faiss_index\*" >nul 2>&1
    if %errorlevel% neq 0 set INDEX_MISSING=1
)

if %INDEX_MISSING%==1 (
    echo [INFO] FAISS index not found. Building legal document index...
    echo [INFO] This takes 5-15 minutes on first run. Please wait...
    cd backend
    call venv\Scripts\activate
    python build_index.py
    cd ..
) else (
    echo [OK] FAISS index found. Skipping build_index.py.
)

:: Install npm deps
if not exist "frontend\node_modules" (
    echo [INFO] Installing frontend dependencies...
    cd frontend
    npm install
    cd ..
)

echo.
echo [INFO] Starting backend server...
start "Legal Aid Backend" cmd /k "cd backend && venv\Scripts\activate && python main.py"

timeout /t 4 /nobreak >nul

echo [INFO] Starting frontend dev server...
start "Legal Aid Frontend" cmd /k "cd frontend && npm run dev"

timeout /t 4 /nobreak >nul

echo.
echo  ========================================
echo   Application started!
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173
echo   API Docs: http://localhost:8000/api/docs
echo   Health:   http://localhost:8000/api/health
echo  ========================================
echo.
echo  Opening browser...
start http://localhost:5173

pause
