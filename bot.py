"""bot.py — sTONks Shop: команды ДО текстового хендлера, безопасные api-вызовы"""
import asyncio, logging, re
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.exceptions import SkipHandler
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
PHONE_RE = re.compile(r"^\+?\d{9,15}$")
TIMEOUT = aiohttp.ClientTimeout(total=15)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('stonks-bot')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
flow = {}

async def api_get(path):
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(API + path) as r:
                if r.status != 200: return None
                return await r.json()
    except Exception:
        log.exception('api_get failed: %s', path)
        return None

async def api_post(path, data, admin=False):
    try:
        h = {'X-Admin-Id': str(ADMIN_ID)} if admin else {}
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.post(API + path, json=data, headers=h) as r:
                try: body = await r.json()
                except Exception: body = {}
                return r.status, body
    except Exception:
        log.exception('api_post failed: %s', path)
        return 0, {}

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

# ========== КОМАНДЫ (обязательно ДО текстового хендлера) ==========
@dp.message(CommandStart())
async def start(m: types.Message):
    uid = str(m.from_user.id)
    if (m.from_user.username or "").lower() == MANAGER_USERNAME:
        await api_post("/api/shop/setmanager", {"id": uid}, admin=True)
        await m.answer("✅ Ты подключён как менеджер заказов: теперь все заказы из магазина приходят тебе сюда.")
    me = await api_get(f"/api/shop/me?id={uid}")
    reg = bool(me and me.get("registered"))
    if not reg:
        flow[uid] = {'step': 'reg'}
        await m.answer("🟢 Остался шаг: регистрация.\n\n📱 Отправь контакт КНОПКОЙ ниже или просто напиши номер текстом (+998XXXXXXXXX):",
                       reply_markup=CONTACT_KB)
    else:
        await welcome(m)

@dp.message(Command("help"))
async def help(m: types.Message):
    await m.answer(
        "🟢 sTONks Shop — программа лояльности.\n\n"
        "/start — регистрация (контакт или номер текстом)\n"
        "/id — свой ID\n"
        "/subcheck — диагностика подписки\n\n"
        "🛠 Админ:\n/addstars [id] N\n"
        "/prob list | /prob case_free 25 25 25 25\n"
        "/setmanager <id> · /moveid old new\n"
        "Переслал сообщение — получил ID отправителя.")

@dp.message(Command("id"))
async def my_id(m: types.Message):
    await m.answer(f"🆔 Твой ID: <code>{m.from_user.id}</code>\nЮзернейм: @{m.from_user.username or 'нет'}", parse_mode="HTML")

@dp.message(Command("subcheck"))
async def subcheck(m: types.Message):
    d = await api_get(f"/api/shop/me?id={m.from_user.id}")
    if not d:
        return await m.answer("⚠️ Сервер недоступен, попробуй через минуту")
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
    status, d = await api_post("/api/shop/addstars", {"id": uid, "amount": amount})
    if status == 0: return await m.answer("⚠️ Сервер недоступен")
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
        d = await api_get("/api/shop/prob")
        if not d: return await m.answer("⚠️ Сервер недоступен")
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
    elif status == 0:
        await m.answer("⚠️ Сервер недоступен")
    else:
        await m.answer(f"⚠️ Ошибка: {d}")

@dp.message(Command("moveid"))
async def moveid(m: types.Message):
    if m.from_user.id != ADMIN_ID: return await m.answer("⛔ Только админ")
    parts = (m.text or "").split()
    if len(parts) != 3: return await m.answer("Формат: /moveid старый_id новый_id")
    status, d = await api_post("/api/shop/moveid", {"old": parts[1], "new": parts[2]}, admin=True)
    if status == 200: await m.answer("✅ Данные перенесены")
    elif status == 0: await m.answer("⚠️ Сервер недоступен")
    else: await m.answer(f"⚠️ Ошибка: {d}")

# ========== РЕГИСТРАЦИЯ ==========
@dp.message(F.contact)
async def on_contact(m: types.Message):
    uid = str(m.from_user.id)
    status, d = await api_post("/api/shop/register", {
        "id": uid, "phone": m.contact.phone_number,
        "name": m.from_user.first_name or "user",
        "username": m.from_user.username or ""})
    if status == 0:
        return await m.answer("⚠️ Сервер недоступен. Попробуй через минуту или напиши админу.")
    if status != 200:
        return await m.answer(f"⚠️ Ошибка регистрации: {d}")
    flow.pop(uid, None)
    await m.answer("✅ Регистрация пройдена. Открывай магазин — гейт пустит.", reply_markup=ReplyKeyboardRemove())
    await welcome(m)

@dp.message(F.forward_from)
async def fwd_id(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        raise SkipHandler
    await m.answer(f"🆔 ID отправителя пересланного: <code>{m.forward_from.id}</code>\nИмя: {m.forward_from.first_name}", parse_mode="HTML")

@dp.message(F.text)
async def text_reg(m: types.Message):
    uid = str(m.from_user.id)
    f = flow.get(uid)
    if not f or f.get('step') != 'reg':
        raise SkipHandler
    t = m.text.strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if not PHONE_RE.match(t):
        return await m.answer("⚠️ Нажми кнопку контакта или напиши номер целиком: +998XXXXXXXXX")
    status, d = await api_post("/api/shop/register", {
        "id": uid, "phone": t,
        "name": m.from_user.first_name or "user",
        "username": m.from_user.username or ""})
    if status == 0:
        return await m.answer("⚠️ Сервер недоступен. Попробуй через минуту.")
    if status != 200:
        return await m.answer(f"⚠️ Ошибка регистрации: {d}")
    flow.pop(uid, None)
    await m.answer("✅ Регистрация пройдена. Открывай магазин — гейт пустит.")
    await welcome(m)

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