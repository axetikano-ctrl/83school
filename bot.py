"""bot.py — sTONks Shop: витрина, кейсы, колесо (демо)"""
import asyncio, logging
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, MenuButtonWebApp
from aiogram.utils.markdown import hbold
from config import BOT_TOKEN, WEBAPP_URL

API = WEBAPP_URL.rstrip('/')
CHANNEL = 'https://t.me/sTONks_shopuzb'
MANAGER = 'https://t.me/logistickon'
ADMIN_ID = 8062748340
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('stonks-bot')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Открыть магазин", web_app=WebAppInfo(url=API))],
        [InlineKeyboardButton(text="📢 Канал", url=CHANNEL),
         InlineKeyboardButton(text="📦 Заказать", url=MANAGER)],
    ])

@dp.message(CommandStart())
async def start(m: types.Message):
    await m.answer(
        f"🟢 {hbold(m.from_user.first_name or 'друг')}, добро пожаловать в sTONks Shop!\n\n"
        "⭐ Telegram Stars, Premium, подарки и Карточка Грамм\n"
        "🧰 Кейсы и 🎡 колесо фортуны — внутри мини-аппа\n\n"
        "⚖️ ДЕМО-режим: звёзды в кейсах и колесе демонстрационные, шансы подписаны честно на каждом призе. "
        "Заказы реальных товаров — через менеджера.\n\n👇 Открывай:",
        parse_mode="HTML", reply_markup=kb())

@dp.message(Command("help"))
async def help(m: types.Message):
    await m.answer(
        "🟢 sTONks Shop — демо-магазин.\n\n"
        "🧰 ФРИ-кейс: раз в 24ч, нужна подписка на канал\n"
        "🧰 Кейс за 50⭐ и 🎡 колесо: крутятся на демо-звёздах\n"
        "🛒 Реальные товары заказываются у менеджера\n\n"
        "Шансы всех призов открыты в интерфейсе. Это демо: никаких реальных ставок.")

@dp.message(Command("addstars"))
async def addstars(m: types.Message):
    """Админ: /addstars [id] количество"""
    if m.from_user.id != ADMIN_ID:
        return await m.answer("⛔ Только админ")
    parts = (m.text or "").split()
    uid = str(m.from_user.id)
    amount = 100
    if len(parts) == 3:
        uid, amount = parts[1], int(parts[2])
    elif len(parts) == 2:
        amount = int(parts[1])
    async with aiohttp.ClientSession() as s:
        async with s.post(API + "/api/shop/addstars", json={"id": uid, "amount": amount}) as r:
            d = await r.json()
    await m.answer(f"✅ Начислено демо-звёзд: {d.get('stars')}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="🟢 sTONks Shop", web_app=WebAppInfo(url=API)))
        log.info('menu button set')
    except Exception as e:
        log.warning('menu button failed: %s', e)
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())