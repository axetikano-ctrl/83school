"""bot.py — sTONks Shop: регистрация по контакту, менеджер, админ-команды"""
import asyncio, logging
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
                           MenuButtonWebApp, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove)
from aiogram.utils.markdown import hbold
from config import BOT_TOKEN, WEBAPP_URL

API = WEBAPP_URL.rstrip('/')
CHANNEL = 'https://t.me/sTONks_shopuzb'
MANAGER_LINK = 'https://t.me/logistickon'
MANAGER_USERNAME = 'logistickon'
ADMIN_ID = 8062748340
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('stonks-bot')
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
        [InlineKeyboardButton(text="Открыть магазин", web_app=WebAppInfo(url=API))],
        [InlineKeyboardButton(text="Канал", url=CHANNEL),
         InlineKeyboardButton(text="Менеджер", url=MANAGER_LINK)],
    ])

CONTACT_KB = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True,
                                 keyboard=[[KeyboardButton(text="Отправить контакт", request_contact=True)]])

async def welcome(m: types.Message):
    await m.answer(
        f"🟢 {hbold(m.from_user.first_name or 'друг')}, ты в sTONks Shop!\n\n"
        "⭐ Stars · Premium · Карточка Грамм · Подарки\n"
        "🧰 Кейсы и колесо фортуны — в мини-аппе\n"
        "📦 Заказы улетают менеджеру автоматически\n\n"
        "⚖️ Программа лояльности: баллы за активность и подписку, шансы открыты в профиле.\n\n👇 Открывай:",
        parse_mode="HTML", reply_markup=kb())

@dp.message(CommandStart())
async def start(m: types.Message):
    uid = str(m.from_user.id)
    # авто-подключение менеджера
    if (m.from_user.username or "").lower() == MANAGER_USERNAME:
        await api_post("/api/shop/setmanager", {"id": uid}, admin=True)
        await m.answer("✅ Ты подключён как менеджер заказов: теперь все заказы из магазина приходят тебе сюда.")
        return
    try:
        me = await api_get(f"/api/shop/me?id={uid}")
        reg = me.get("registered", False)
    except Exception:
        reg = False
    if not reg:
        flow[uid] = {'step': 'reg'}
        await m.answer("🟢 Добро пожаловать в sTONks Shop!\n\n📱 Для регистрации отправь контакт кнопкой ниже — он нужен для оформления заказов:",
                       reply_markup=CONTACT_KB)
    else:
        await welcome(m)

@dp.message(F.contact)
async def on_contact(m: types.Message):
    uid = str(m.from_user.id)
    await api_post("/api/shop/register", {
        "id": uid,
        "phone": m.contact.phone_number,
        "name": m.from_user.first_name or "user",
        "username": m.from_user.username or ""})
    flow.pop(uid, None)
    await m.answer("✅ Регистрация пройдена. Баллы: 0. Фри-кейс доступен после подписки на канал.",
                   reply_markup=ReplyKeyboardRemove())
    await welcome(m)

@dp.message(Command("help"))
async def help(m: types.Message):
    await m.answer(
        "🟢 sTONks Shop — программа лояльности.\n\n"
        "/start — регистрация (контакт)\n"
        "/subcheck — диагностика подписки\n\n"
        "🛠 Админ:\n/addstars [id] N\n"
        "/prob list | /prob case_free 25 25 25 25\n"
        "/setmanager <id> — кто принимает заказы")

@dp.message(Command("subcheck"))
async def subcheck(m: types.Message):
    async with aiohttp.ClientSession() as s:
        async with s.get(API + "/api/shop/me", params={"id": str(m.from_user.id)}) as r:
            d = await r.json()
    diag = d.get("sub_diag", {})
    await m.answer(
        f"🔍 Подписка: {'✅ да' if d.get('subscribed') else '❌ нет'}\n"
        f"Статус: <code>{diag.get('status', '?')}</code>\n"
        f"Регистрация: {'✅' if d.get('registered') else '❌'}\n\n"
        f"member/creator/administrator/restricted = подписан.\nleft/kicked = не подписан.",
        parse_mode="HTML")

@dp.message(Command("addstars"))
async def addstars(m: types.Message):
    if m.from_user.id != ADMIN_ID: return await m.answer("⛔ Только админ")
    parts = (m.text or "").split()
    uid, amount = str(m.from_user.id), 100
    if len(parts) == 3: uid, amount = parts[1], int(parts[2])
    elif len(parts) == 2: amount = int(parts[1])
    _, d = await api_post("/api/shop/addstars", {"id": uid, "amount": amount})
    await m.answer(f"✅ Начислено, баланс: {d.get('stars')}")

@dp.message(Command("setmanager"))
async def setmanager(m: types.Message):
    if m.from_user.id != ADMIN_ID: return await m.answer("⛔ Только админ")
    parts = (m.text or "").split()
    mid = parts[1] if len(parts) > 1 else str(m.from_user.id)
    status, _ = await api_post("/api/shop/setmanager", {"id": mid}, admin=True)
    await m.answer("✅ Менеджер заказов установлен" if status == 200 else "⚠️ Ошибка")

@dp.message(Command("prob"))
async def prob(m: types.Message):
    if m.from_user.id != ADMIN_ID: return await m.answer("⛔ Только админ")
    parts = (m.text or "").split()
    if len(parts) < 2: return await m.answer("Формат: /prob list | /prob case_free 25 25 25 25")
    if parts[1] == "list":
        async with aiohttp.ClientSession() as s:
            async with s.get(API + "/api/shop/prob") as r:
                d = await r.json()
        lines = []
        for k in ("case_free", "case_50", "wheel"):
            lines.append(f"• {k}:")
            for it in d[k]:
                name = "NFT" if it["prize"] == "NFT" else f'{it["prize"]}⭐'
                lines.append(f"    {name} → {it['chance']}%")
        return await m.answer("📊 Шансы:\n\n" + "\n".join(lines))
    key = parts[1]
    if key not in ("case_free", "case_50", "wheel"): return await m.answer("Ключ: case_free / case_50 / wheel")
    try: vals = [int(x) for x in parts[2:]]
    except ValueError: return await m.answer("Числами")
    status, d = await api_post("/api/shop/setprob", {"key": key, "chances": vals}, admin=True)
    if status == 200:
        await m.answer(f"✅ {key}:\n" + "\n".join(f"{it['prize']}⭐ → {it['chance']}%" for it in d["table"]))
    else:
        await m.answer(f"⚠️ {d}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="sTONks Shop", web_app=WebAppInfo(url=API)))
        log.info('menu button set')
    except Exception as e:
        log.warning('menu button failed: %s', e)
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())