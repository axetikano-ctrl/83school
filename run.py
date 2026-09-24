"""
run.py — запускает сервер и бота
"""
import threading
import uvicorn
import asyncio
from config import SERVER_HOST, SERVER_PORT

def run_server():
    uvicorn.run("server:app", host=SERVER_HOST, port=SERVER_PORT, reload=False)

async def run_bot():
    from bot import main
    await main()

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    asyncio.run(run_bot())