"""
run.py — Запускает и бота, и сервер в одном процессе (для локальной разработки)
"""
import asyncio
import threading
import uvicorn
from config import SERVER_HOST, SERVER_PORT


def run_server():
    uvicorn.run(
        "server:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=False,  # Cannot reload in thread mode
        log_level="info",
    )


async def run_bot():
    from bot import dp, bot, init_db
    from aiogram import Bot
    await init_db()
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    # Start FastAPI in background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    print("=" * 50)
    print("  ANTIGRAVITY — Running (Bot + Server)")
    print(f"  API / Frontend: http://localhost:{SERVER_PORT}")
    print("=" * 50)

    # Run bot in main event loop
    asyncio.run(run_bot())
