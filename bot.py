"""bot.py — GRAM: регистрация контактом, нули, маркет после 24h"""
import asyncio, logging
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
                           MenuButtonWebApp, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove)
from aiogram.utils.markdown import hbold
from config import BOT_TOKEN, WEBAPP_URL

API = WEBAPP_URL.rstrip('/')
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('gram-bot')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
flow = {}

async def api_get(path):
    async with aiohttp.ClientSession() as s:
        async with s.get(API + path) as r:
            return await r.json()

async def api_post(path, data):
    async with aiohttp.ClientSession() as s:
        async with s.post(API + path, json=data) as r:
            return await r.json()

def kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Открыть GRAM Wallet", web_app=WebAppInfo(url=API))],
        [InlineKeyboardButton(text="🎁 Маркет подарков", web_app=WebAppInfo(url=API))],
        [InlineKeyboardButton(text="🚀 Питч для инвесторов", web_app=WebAppInfo(url=API))],
    ])

CONTACT_KB = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True,
                                 keyboard=[[KeyboardButton(text="📱 Отправить контакт", request_contact=True)]])

async def welcome(m: types.Message):
    await m.answer(
        f"🔷 {hbold(m.from_user.first_name or 'друг')}, ты в GRAM.\n\n"
        "💎 Кошелёк: баланс 0 TON / 0 ⭐ на старте\n"
        "🎁 Маркет: откроется, когда аккаунту станет 24 часа (защита от скама)\n"
        "📦 Офферы: демо-визуал будущих честных сделок с эскроу\n\n"
        "⚖️ Учебный демо-проект: бот не имитирует системные сообщения Telegram.\n\n👇 Открывай:",
        parse_mode="HTML", reply_markup=kb())

@dp.message(CommandStart())
async def start(m: types.Message):
    uid = str(m.from_user.id)
    try:
        me = await api_get(f"/api/gram/me?id={uid}")
        reg = me.get("registered", False)
    except Exception:
        reg = False
    if not reg:
        flow[uid] = {'step': 'reg'}
        await m.answer("🔷 Добро пожаловать в GRAM.\n\n📱 Для регистрации отправь свой контакт кнопкой ниже — без него кошелёк не откроем. После регистрации всё по нулям, маркет откроется через 24 часа:",
                       reply_markup=CONTACT_KB)
    else:
        await welcome(m)

@dp.message(F.contact)
async def on_contact(m: types.Message):
    uid = str(m.from_user.id)
    await api_post("/api/gram/register", {"id": uid, "phone": m.contact.phone_number,
                                          "name": m.from_user.first_name or "user"})
    flow.pop(uid, None)
    await m.answer("✅ Контакт принят.\n💎 Баланс: 0 TON / 0 ⭐\n🔒 Маркет откроется через 24 часа.",
                   reply_markup=ReplyKeyboardRemove())
    await welcome(m)

@dp.message(Command("help"))
async def help(m: types.Message):
    await m.answer(
        "🔷 GRAM — демо кошелёк + маркетплейс подарков.\n\n"
        "/start — главное меню (нужна регистрация контактом)\n"
        "/market — правила маркета (24h lock)\n\n"
        "Продавец сам выставляет свой подарок (ссылка, цена, контакт). "
        "Покупатель пишет ему в личку, сделка идёт официально через Telegram.")

@dp.message(Command("market"))
async def market(m: types.Message):
    await m.answer(
        "🎁 Правила маркета GRAM:\n\n"
        "🔒 Торговля открывается через 24 часа после регистрации — свежие аккаунты скамеров не проходят\n"
        "1. Выставляешь СВОЙ подарок: ссылка, цена ⭐, контакт\n"
        "2. Покупатель пишет в личку → сделка официально через Telegram\n"
        "3. В рабочей версии: верификация, отзывы, эскроу\n\n"
        "Без имитации системных сообщений — только прозрачные объявления.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="💎 GRAM", web_app=WebAppInfo(url=API)))
        log.info('menu button set')
    except Exception as e:
        log.warning('menu button failed: %s', e)
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())