"""
run.py — один процесс: FastAPI + бот.
Локально — polling, в облаке — webhook.
"""
import asyncio
import threading
import logging
import sys
import uvicorn
from config import SERVER_HOST, SERVER_PORT, BOT_MODE

# Fix для Windows: psycopg async требует SelectorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(level=logging.INFO)

async def serve_api():
    cfg = uvicorn.Config("server:app", host=SERVER_HOST, port=SERVER_PORT, log_level="info")
    await uvicorn.Server(cfg).serve()

def thread_server():
    asyncio.run(serve_api())

async def run_polling():
    from bot import dp, bot
    from database import init_db
    await init_db()
    await dp.start_polling(bot, skip_updates=True)

async def run_webhook():
    from bot import setup_webhook
    from database import init_db
    await init_db()
    await setup_webhook()
    await serve_api()

if __name__ == "__main__":
    print("=" * 50)
    print("  83 SCHOOL — mode:", BOT_MODE)
    print("=" * 50)
    if BOT_MODE == "webhook":
        asyncio.run(run_webhook())
    else:
        threading.Thread(target=thread_server, daemon=True).start()
        asyncio.run(run_polling())
