@echo off
title Legal Aid — Frontend
color 0A
setlocal

cd /d "%~dp0frontend"

echo.
echo  ========================================
echo   Starting Frontend (React + Vite)
echo   http://localhost:5173
echo  ========================================
echo.

:: ── Check Node.js ────────────────────────────────────────────────
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found.
    echo [FIX]   Install from https://nodejs.org
    pause
    exit /b 1
)

:: ── Install packages if missing ──────────────────────────────────
if not exist "node_modules" (
    echo [INFO] node_modules not found. Running npm install first...
    echo [INFO] This takes 1-3 minutes. Please wait...
    echo.
    npm install
    if %errorlevel% neq 0 (
        echo [ERROR] npm install failed.
        echo [FIX]   Make sure Node.js is installed: https://nodejs.org
        pause
        exit /b 1
    )
    echo.
)

:: ── Start dev server ─────────────────────────────────────────────
echo [OK] Starting Vite development server on port 5173...
echo.
npm run dev
pause
endlocal
