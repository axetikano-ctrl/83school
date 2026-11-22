"""run.py — веб в главном потоке, бот в потоке с авто-рестартом"""
import os, time, threading, logging
import uvicorn

logging.basicConfig(level=logging.INFO)
log = logging.getLogger('run')

def bot_thread():
    import asyncio
    while True:
        try:
            from bot import main as bot_main
            asyncio.run(bot_main())
        except Exception as e:
            log.error('BOT CRASHED: %r — перезапуск через 15 сек', e)
            time.sleep(15)

if __name__ == '__main__':
    threading.Thread(target=bot_thread, daemon=True).start()
    port = int(os.getenv('PORT', '8000'))
    log.info('starting web on port %s', port)
    uvicorn.run('server:app', host='0.0.0.0', port=port, log_level='info')