"""bot.py — GRAM: регистрация (контакт + юзернейм), смена юзернейма, 24h lock, /offer для админа"""
import asyncio, logging, re
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
                           MenuButtonWebApp, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove)
from aiogram.utils.markdown import hbold
from config import BOT_TOKEN, WEBAPP_URL

API = WEBAPP_URL.rstrip('/')
ADMIN_ID = 8062748340
UNAME_RE = re.compile(r"[a-z0-9_]{3,32}")
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('gram-bot')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
flow = {}

async def api_get(path):
    async with aiohttp.ClientSession() as s:
        async with s.get(API + path) as r:
            return await r.json()

async def api_post(path, data, admin=False):
    h = {'X-Admin-Id': str(ADMIN_ID)} if admin else {}
    async with aiohttp.ClientSession() as s:
        async with s.post(API + path, json=data, headers=h) as r:
            return r.status, await r.json()

def kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Открыть GRAM Wallet", web_app=WebAppInfo(url=API))],
        [InlineKeyboardButton(text="🎁 Маркет подарков", web_app=WebAppInfo(url=API))],
        [InlineKeyboardButton(text="📦 Мои офферы", web_app=WebAppInfo(url=API))],
    ])

CONTACT_KB = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True,
                                 keyboard=[[KeyboardButton(text="📱 Отправить контакт", request_contact=True)]])

async def welcome(m: types.Message):
    await m.answer(
        f"🔷 {hbold(m.from_user.first_name or 'друг')}, ты в GRAM.\n\n"
        "💎 Баланс: 0 TON / 0 ⭐\n"
        "🔒 Маркет откроется через 24 часа после регистрации\n"
        "📦 Офферы приходят на твой юзернейм внутри мини-аппа\n"
        "✏️ /username — сменить свой юзернейм\n\n"
        "⚖️ Проет созданый с помощью инвестеров Telegram.\n\n👇 Открывай:",
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
        await m.answer("🔷 Добро пожаловать в GRAM.\n\n📱 Шаг 1: отправь контакт кнопкой ниже.",
                       reply_markup=CONTACT_KB)
    else:
        await welcome(m)

@dp.message(F.contact)
async def on_contact(m: types.Message):
    uid = str(m.from_user.id)
    flow.setdefault(uid, {})['phone'] = m.contact.phone_number
    flow[uid]['step'] = 'username'
    await m.answer("✅ Контакт принят.\n\n📝 Шаг 2: придумай свой юзернейм в GRAM (латиницей, без пробелов, напр. arslan01). Потом его можно сменить командой /username:",
                   reply_markup=ReplyKeyboardRemove())

@dp.message(Command("username"))
async def username_cmd(m: types.Message):
    uid = str(m.from_user.id)
    try:
        me = await api_get(f"/api/gram/me?id={uid}")
    except Exception:
        return await m.answer("⚠️ Сервер недоступен, попробуй позже")
    if not me.get("registered"):
        return await m.answer("Сначала зарегистрируйся: /start")
    flow[uid] = {'step': 'change_username'}
    cur = me.get('username') or 'не задан'
    await m.answer(f"✏️ Сейчас твой юзернейм: {cur}\n\nПришли новый (латиница/цифры/_, 3-32 символа):")

@dp.message(F.text)
async def text_flow(m: types.Message):
    uid = str(m.from_user.id)
    f = flow.get(uid)
    if not f:
        return
    step = f.get('step')
    if step == 'username':
        uname = m.text.strip().lstrip('@').lower()
        if not UNAME_RE.fullmatch(uname):
            return await m.answer("⚠️ Юзернейм: 3-32 символа, латиница/цифры/_ , без пробелов.")
        status, _ = await api_post("/api/gram/register", {"id": uid, "phone": f.get('phone', ''),
                                                          "name": m.from_user.first_name or "user", "username": uname})
        flow.pop(uid, None)
        await m.answer(f"✅ Готово, твой юзернейм в GRAM: @{uname}\n💎 Баланс: 0 TON / 0 ⭐\n🔒 Маркет откроется через 24 часа.")
        await welcome(m)
    elif step == 'change_username':
        uname = m.text.strip().lstrip('@').lower()
        if not UNAME_RE.fullmatch(uname):
            return await m.answer("⚠️ Юзернейм: 3-32 символа, латиница/цифры/_ , без пробелов.")
        status, data = await api_post("/api/gram/username", {"id": uid, "username": uname})
        if status == 409:
            return await m.answer("❌ Такой юзернейм уже занят. Пришли другой:")
        if status != 200:
            return await m.answer("⚠️ Не сохранилось, попробуй ещё раз")
        flow.pop(uid, None)
        await m.answer(f"✅ Юзернейм обновлён: @{uname}\n📦 Новые офферы будут приходить на него. Старые офферы останутся на прежнем юзе.")

@dp.message(Command("offer"))
async def offer_cmd(m: types.Message):
    """Админ: /offer username цена ссылка_на_подарок"""
    if m.from_user.id != ADMIN_ID:
        return await m.answer("⛔ Только админ")
    parts = (m.text or "").split(maxsplit=3)
    if len(parts) != 4:
        return await m.answer("Формат: /offer username 1000 t.me/nft/SnakeBox-14046")
    _, uname, price, link = parts
    try:
        price = int(price)
    except ValueError:
        return await m.answer("Цена числом")
    status, _ = await api_post("/api/gram/offers", {"to_username": uname, "gift_link": link,
                                                    "price": price, "buyer": "@" + (m.from_user.username or 'admin')}, admin=True)
    if status == 200:
        await m.answer(f"📦 оффер создан для @{uname.lstrip('@')}: {price} ⭐")
    else:
        await m.answer("⚠️ Не создалось: проверь ссылку (t.me/nft/Name-123)")

@dp.message(Command("help"))
async def help(m: types.Message):
    await m.answer("🔷 GRAM — демо кошелёк + маркетплейс подарков.\n\n"
                   "/start — регистрация (контакт + юзернейм)\n"
                   "/username — сменить свой юзернейм\n"
                   "/market — правила маркета и 24h lock\n\n"
                   "Все офферы обмен идёт через эскроу GRAM.")

@dp.message(Command("market"))
async def market(m: types.Message):
    await m.answer("🎁 Правила маркета GRAM:\n\n"
                   "🔒 Торговля открывается через 24 часа после регистрации\n"
                   "1. Выставляешь СВОЙ подарок: ссылка, цена ⭐, контакт\n"
                   "2. Сделка идёт через эскроу: подарок и звёзды блокируются одновременно\n"
                   "3. Односторонняя передача подарка в личку без эскроу = признак мошенничества\n\n"
                   "⚖️ Демо: ничего не проводится.")

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