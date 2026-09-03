@echo off
echo ============================================
echo   ANTIGRAVITY — Starting Game Server
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Install Python 3.11+ from python.org
    pause
    exit /b 1
)

REM Install dependencies if needed
if not exist ".venv" (
    echo [SETUP] Creating virtual environment...
    python -m venv .venv
    echo [SETUP] Installing dependencies...
    .venv\Scripts\pip install -r requirements.txt
)

REM Check .env
if not exist ".env" (
    echo [WARNING] .env file not found! Copying from .env.example...
    copy .env.example .env
    echo [ACTION] Please edit .env and set your BOT_TOKEN and WEBAPP_URL
    echo          Then run this script again.
    notepad .env
    pause
    exit /b 0
)

echo [START] Starting FastAPI server on http://localhost:8000
start "Antigravity API Server" .venv\Scripts\uvicorn server:app --host 0.0.0.0 --port 8000 --reload

timeout /t 2 >nul

echo [INFO] Server started. Open http://localhost:8000 in browser to test.
echo [INFO] To start the bot separately, run: start_bot.bat
echo.
pause
