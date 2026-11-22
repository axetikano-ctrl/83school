"""run.py v3 — веб и бот в ОДНОМ главном потоке (Render/Linux ok)"""
import os, asyncio, logging
import uvicorn

logging.basicConfig(level=logging.INFO)
log = logging.getLogger('run')

async def bot_supervisor():
    from bot import main as bot_main
    while True:
        try:
            await bot_main()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.error('BOT CRASHED: %r — перезапуск через 15 сек', e)
            await asyncio.sleep(15)

async def main():
    log.info('RUN.PY V3 single-loop started')
    port = int(os.getenv('PORT', '8000'))
    config = uvicorn.Config('server:app', host='0.0.0.0', port=port, log_level='info')
    server = uvicorn.Server(config)
    bot_task = asyncio.create_task(bot_supervisor())
    try:
        await server.serve()
    finally:
        bot_task.cancel()

if __name__ == '__main__':
    asyncio.run(main())