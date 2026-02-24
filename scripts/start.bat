@echo off
REM Mayo Clinic Validator — full-stack startup (Windows)
REM
REM Usage:  npm run start:win
REM
REM What it does:
REM   1. Checks Docker is running
REM   2. Starts the PostgreSQL+pgvector container (docker compose up -d)
REM   3. Waits for Postgres to accept connections
REM   4. Starts FastAPI backend   → http://localhost:8000
REM   5. Starts Next.js frontend  → http://localhost:3000
REM   6. Ctrl-C shuts everything down

setlocal enabledelayedexpansion

set "ROOT=%~dp0.."
set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"

echo [startup] Mayo Clinic Validator — starting all services (Windows)
echo.

REM ── Check Docker ────────────────────────────────────────────────────────────
docker info >nul 2>nul
if errorlevel 1 (
    echo [startup] Docker daemon not running. Please start Docker Desktop and try again.
    exit /b 1
)
echo [startup] Docker is running

REM ── Start Postgres container ────────────────────────────────────────────────
echo [db] Starting PostgreSQL container...
docker compose -f "%BACKEND%\docker-compose.yml" up -d

REM ── Wait for Postgres ───────────────────────────────────────────────────────
echo [db] Waiting for Postgres to be ready...
set "RETRIES=30"
:pg_wait
docker exec mayo_validator_db pg_isready -U postgres -d mayo_validation >nul 2>nul
if not errorlevel 1 goto :pg_ready
set /a RETRIES-=1
if %RETRIES% leq 0 (
    echo [db] Postgres did not become ready in time.
    exit /b 1
)
timeout /t 2 /nobreak >nul
goto :pg_wait

:pg_ready
echo [db] Postgres ready

REM ── Start FastAPI backend ───────────────────────────────────────────────────
echo [backend] Starting FastAPI backend on :8000...
start "mayo-backend" /d "%BACKEND%" cmd /c "call venv\Scripts\activate && uvicorn main:app --host 0.0.0.0 --port 8000"

REM Wait a bit for backend to bind
timeout /t 3 /nobreak >nul

REM ── Start Next.js frontend ─────────────────────────────────────────────────
echo [frontend] Starting Next.js frontend on :3000...
start "mayo-frontend" /d "%FRONTEND%" cmd /c "npm run dev"

echo.
echo   All services started.
echo   Backend  -^> http://localhost:8000/api/health
echo   Frontend -^> http://localhost:3000
echo.
echo   Close the "mayo-backend" and "mayo-frontend" windows to stop services.
echo   Or press Ctrl-C here (containers stay running).
echo.
pause
