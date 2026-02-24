@echo off
REM Mayo Clinic Validator — one-time setup (Windows)
REM
REM Usage:  npm run setup:win
REM
REM What it does:
REM   1. Checks prerequisites (Docker, Python 3.11, Node)
REM   2. Creates backend Python venv + installs pip deps
REM   3. Starts PostgreSQL+pgvector container
REM   4. Waits for Postgres, then seeds the RAG knowledge base
REM   5. Installs frontend npm dependencies

setlocal enabledelayedexpansion

set "ROOT=%~dp0.."
set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"

echo [setup] Mayo Clinic Validator — one-time setup (Windows)
echo.

REM ── Check prerequisites ──────────────────────────────────────────────────────
echo [setup] Checking prerequisites...

where docker >nul 2>nul
if errorlevel 1 (
    echo   X Docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/
    exit /b 1
)
echo   + Docker found

REM Try python3.11, then py -3.11, then python
set "PYTHON="
where python3.11 >nul 2>nul
if not errorlevel 1 (
    set "PYTHON=python3.11"
    goto :python_found
)
py -3.11 --version >nul 2>nul
if not errorlevel 1 (
    set "PYTHON=py -3.11"
    goto :python_found
)
python --version 2>nul | findstr "3.11" >nul
if not errorlevel 1 (
    set "PYTHON=python"
    goto :python_found
)
echo   X Python 3.11 not found. Install from https://www.python.org/downloads/
exit /b 1

:python_found
echo   + Python 3.11 found: %PYTHON%

where node >nul 2>nul
if errorlevel 1 (
    echo   X Node.js not found. Install from https://nodejs.org/
    exit /b 1
)
echo   + Node.js found

REM ── .env file ────────────────────────────────────────────────────────────────
if not exist "%BACKEND%\.env" (
    if exist "%BACKEND%\.env.example" (
        copy "%BACKEND%\.env.example" "%BACKEND%\.env" >nul
        echo   ! Created backend\.env from .env.example — edit it to add your OPENAI_API_KEY
    ) else (
        echo   ! No backend\.env found — create one with your OPENAI_API_KEY before running
    )
) else (
    echo   + backend\.env exists
)

REM ── Python venv + deps ──────────────────────────────────────────────────────
echo.
echo [setup] Setting up Python backend...

if not exist "%BACKEND%\venv" (
    echo [setup] Creating virtualenv...
    %PYTHON% -m venv "%BACKEND%\venv"
    echo   + Virtualenv created
) else (
    echo   + Virtualenv already exists
)

echo [setup] Installing Python dependencies...
call "%BACKEND%\venv\Scripts\pip" install -r "%BACKEND%\requirements.txt"
echo   + Python dependencies installed

REM ── Docker compose (Postgres + pgvector) ─────────────────────────────────────
echo.
echo [setup] Starting PostgreSQL container...
docker info >nul 2>nul
if errorlevel 1 (
    echo   ! Docker daemon not running — please start Docker Desktop and re-run this script.
    exit /b 1
)

docker compose -f "%BACKEND%\docker-compose.yml" up -d
echo   + PostgreSQL container started

REM ── Wait for Postgres ────────────────────────────────────────────────────────
echo [setup] Waiting for Postgres to accept connections...
set "RETRIES=30"
:pg_wait
docker exec mayo_validator_db pg_isready -U postgres -d mayo_validation >nul 2>nul
if not errorlevel 1 goto :pg_ready
set /a RETRIES-=1
if %RETRIES% leq 0 (
    echo   X Postgres did not become ready in time.
    exit /b 1
)
timeout /t 2 /nobreak >nul
goto :pg_wait

:pg_ready
echo   + Postgres ready

REM ── Seed knowledge base ──────────────────────────────────────────────────────
echo [setup] Seeding RAG knowledge base...
call "%BACKEND%\venv\Scripts\python" "%BACKEND%\scripts\seed_knowledge.py"
echo   + Knowledge base seeded

REM ── Frontend npm install ────────────────────────────────────────────────────
echo.
echo [setup] Installing frontend dependencies...
cd /d "%FRONTEND%"
call npm install
echo   + Frontend dependencies installed

echo.
echo Setup complete!
echo.
echo Run "npm run start:win" to launch the app.
echo.
