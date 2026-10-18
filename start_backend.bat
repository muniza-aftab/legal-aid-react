@echo off
title Legal Aid — Backend
color 0B
setlocal

cd /d "%~dp0backend"

echo.
echo  ========================================
echo   Starting Backend (FastAPI)
echo   http://localhost:8000
echo   http://localhost:8000/api/docs
echo  ========================================
echo.

:: ── Check virtual environment ────────────────────────────────────
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found.
    echo [FIX]   Run the following commands in a Command Prompt:
    echo.
    echo         cd backend
    echo         python -m venv venv
    echo         venv\Scripts\activate
    echo         pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

:: ── Check .env ───────────────────────────────────────────────────
if not exist ".env" (
    echo [ERROR] .env file not found.
    echo [FIX]   Copy .env.example to .env and add your GROQ_API_KEY.
    echo.
    echo         copy .env.example .env
    echo         notepad .env
    echo.
    pause
    exit /b 1
)

:: ── Check FAISS index ────────────────────────────────────────────
if not exist "data\faiss_index\index.bin" (
    echo [WARN] FAISS index not found. Building now ^(may take 5-15 min^)...
    call venv\Scripts\activate
    python build_index.py
    if errorlevel 1 exit /b 1
)

:: ── Start server ─────────────────────────────────────────────────
call venv\Scripts\activate
echo [OK] Virtual environment activated.
echo [OK] Starting FastAPI server on port 8000...
echo.
python main.py
pause
endlocal
