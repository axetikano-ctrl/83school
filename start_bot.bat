@echo off
echo ============================================
echo   ANTIGRAVITY — Starting Telegram Bot
echo ============================================
echo.

if not exist ".venv" (
    echo [ERROR] Virtual environment not found! Run start_server.bat first.
    pause
    exit /b 1
)

if not exist ".env" (
    echo [ERROR] .env file not found! Copy .env.example to .env and set BOT_TOKEN
    pause
    exit /b 1
)

echo [START] Starting Telegram Bot...
.venv\Scripts\python bot.py
pause
