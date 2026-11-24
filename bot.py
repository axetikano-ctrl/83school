"""bot.py — sTONks Shop: менеджер = стафф, промокоды, команды"""
import asyncio, logging, re
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
                return await r.json() if r.status == 200 else None
    except Exception:
        log.exception('api_get %s', path); return None

async def api_post(path, data, staff_id=None, admin=False):
    try:
        h = {}
        if admin: h['X-Admin-Id'] = str(ADMIN_ID)
        elif staff_id: h['X-Staff-Id'] = str(staff_id)
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.post(API + path, json=data, headers=h) as r:
                try: body = await r.json()
                except Exception: body = {}
                return r.status, body
    except Exception:
        log.exception('api_post %s', path); return 0, {}

async def staff_id(m: types.Message):
    if m.from_user.id == ADMIN_ID: return ('admin', str(ADMIN_ID))
    mgr = await api_get('/api/shop/manager')
    if mgr and str(m.from_user.id) == mgr.get('id'): return ('staff', str(m.from_user.id))
    return (None, None)

def kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Открыть магазин", web_app=WebAppInfo(url=API))],
        [InlineKeyboardButton(text="Канал", url=CHANNEL),
         InlineKeyboardButton(text="Менеджер", url=MANAGER_LINK)]])

CONTACT_KB = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True,
                                 keyboard=[[KeyboardButton(text="Отправить контакт", request_contact=True)]])

async def welcome(m: types.Message):
    await m.answer(
        f"🟢 {hbold(m.from_user.first_name or 'друг')}, ты в sTONks Shop!\n\n"
        "⭐ Stars · Premium · Карточка Грамм · Подарки\n"
        "🧰 Кейсы и колесо фортуны — в мини-аппе\n"
        "🎟 Промокоды и пополнение баланса — внутри\n"
        "📦 Заказы улетают менеджеру автоматически\n\n👇 Открывай:",
        parse_mode="HTML", reply_markup=kb())

@dp.message(CommandStart())
async def start(m: types.Message):
    uid = str(m.from_user.id)
    if (m.from_user.username or "").lower() == MANAGER_USERNAME:
        await api_post("/api/shop/setmanager", {"id": uid}, admin=True)
        await m.answer("✅ Ты подключён как менеджер заказов: заказы приходят сюда, и тебе доступны команды стаффа (/help).")
    me = await api_get(f"/api/shop/me?id={uid}")
    if not (me and me.get("registered")):
        flow[uid] = {'step': 'reg'}
        await m.answer("🟢 Остался шаг: регистрация.\n\n📱 Отправь контакт КНОПКОЙ ниже или напиши номер текстом (+998XXXXXXXXX):",
                       reply_markup=CONTACT_KB)
    else:
        await welcome(m)

@dp.message(Command("help"))
async def help(m: types.Message):
    role, _ = await staff_id(m)
    txt = ("🟢 sTONks Shop\n\n/start — регистрация\n/id — свой ID\n/subcheck — подписка\n\n")
    if role:
        txt += ("🛠 Стафф (админ + менеджер):\n"
                "/addstars [id] N — начислить баллы\n"
                "/prob list | /prob case_free 0 1 1 98\n"
                "/prob case_paid 1 0 0 0 49 50 | /prob wheel 0 1 0 0 99\n"
                "/promo add CODE 500 10 — создать промокод (награда, лимит)\n"
                "/promo list — список промокодов\n")
    if m.from_user.id == ADMIN_ID:
        txt += "\n👑 Админ:\n/setmanager <id>\n/moveid old new\nПересланное сообщение → ID отправителя"
    await m.answer(txt)

@dp.message(Command("id"))
async def my_id(m: types.Message):
    await m.answer(f"🆔 Твой ID: <code>{m.from_user.id}</code>\nЮзернейм: @{m.from_user.username or 'нет'}", parse_mode="HTML")

@dp.message(Command("subcheck"))
async def subcheck(m: types.Message):
    d = await api_get(f"/api/shop/me?id={m.from_user.id}")
    if not d: return await m.answer("⚠️ Сервер недоступен")
    diag = d.get("sub_diag", {})
    await m.answer(f"🔍 Подписка: {'✅' if d.get('subscribed') else '❌'} · статус <code>{diag.get('status','?')}</code>\nРегистрация: {'✅' if d.get('registered') else '❌'}", parse_mode="HTML")

@dp.message(Command("addstars"))
async def addstars(m: types.Message):
    role, sid = await staff_id(m)
    if not role: return await m.answer("⛔ Только стафф")
    parts = (m.text or "").split()
    uid, amount = str(m.from_user.id), 100
    if len(parts) == 3: uid, amount = parts[1], int(parts[2])
    elif len(parts) == 2: amount = int(parts[1])
    st, d = await api_post("/api/shop/addstars", {"id": uid, "amount": amount}, staff_id=sid, admin=(role == 'admin'))
    if st == 0: return await m.answer("⚠️ Сервер недоступен")
    await m.answer(f"✅ Баланс {uid}: {d.get('stars')}")

@dp.message(Command("prob"))
async def prob(m: types.Message):
    role, sid = await staff_id(m)
    if not role: return await m.answer("⛔ Только стафф")
    parts = (m.text or "").split()
    if len(parts) < 2: return await m.answer("Формат: /prob list | /prob case_paid 1 0 0 0 49 50")
    if parts[1] == "list":
        d = await api_get("/api/shop/prob")
        if not d: return await m.answer("⚠️ Сервер недоступен")
        lines = []
        for k in ("case_free", "case_paid", "wheel"):
            lines.append(f"• {k}:")
            for it in d[k]:
                nm = "NFT" if it["prize"] == "NFT" else f'{it["prize"]}⭐'
                lines.append(f"    {nm} → {it['chance']}%")
        return await m.answer("📊 Шансы:\n\n" + "\n".join(lines))
    key = parts[1]
    if key not in ("case_free", "case_paid", "wheel"): return await m.answer("Ключ: case_free / case_paid / wheel")
    try: vals = [int(x) for x in parts[2:]]
    except ValueError: return await m.answer("Числами")
    st, d = await api_post("/api/shop/setprob", {"key": key, "chances": vals}, staff_id=sid, admin=(role == 'admin'))
    if st == 200:
        await m.answer(f"✅ {key} (нормализовано до 100%):\n" + "\n".join(f"{it['prize']} → {it['chance']}%" for it in d["table"]))
    elif st == 0: await m.answer("⚠️ Сервер недоступен")
    else: await m.answer(f"⚠️ {d}")

@dp.message(Command("promo"))
async def promo(m: types.Message):
    role, sid = await staff_id(m)
    if not role: return await m.answer("⛔ Только стафф")
    parts = (m.text or "").split()
    if len(parts) >= 2 and parts[1] == "list":
        st, d = await api_post("/api/shop/promo_list", {}, staff_id=sid, admin=(role == 'admin'))
        if st != 200: return await m.answer(f"⚠️ {d}")
        if not d.get("promos"): return await m.answer("Промокодов пока нет")
        return await m.answer("🎟 Промокоды:\n" + "\n".join(f"{p['code']} · +{p['reward']} · {p['uses']}/{p['max_uses']}" for p in d["promos"]))
    if len(parts) == 5 and parts[1] == "add":
        st, d = await api_post("/api/shop/promo_create", {"code": parts[2], "reward": int(parts[3]), "max_uses": int(parts[4])}, staff_id=sid, admin=(role == 'admin'))
        return await m.answer(f"✅ Промокод {d.get('code')} создан" if st == 200 else f"⚠️ {d}")
    await m.answer("Формат: /promo add CODE 500 10 | /promo list")

@dp.message(Command("setmanager"))
async def setmanager(m: types.Message):
    if m.from_user.id != ADMIN_ID: return await m.answer("⛔ Только админ")
    parts = (m.text or "").split()
    mid = parts[1] if len(parts) > 1 else str(m.from_user.id)
    st, _ = await api_post("/api/shop/setmanager", {"id": mid}, admin=True)
    await m.answer("✅ Менеджер установлен" if st == 200 else "⚠️ Ошибка")

@dp.message(Command("moveid"))
async def moveid(m: types.Message):
    if m.from_user.id != ADMIN_ID: return await m.answer("⛔ Только админ")
    parts = (m.text or "").split()
    if len(parts) != 3: return await m.answer("Формат: /moveid old new")
    st, d = await api_post("/api/shop/moveid", {"old": parts[1], "new": parts[2]}, admin=True)
    await m.answer("✅ Перенесено" if st == 200 else f"⚠️ {d}")

@dp.message(F.contact)
async def on_contact(m: types.Message):
    uid = str(m.from_user.id)
    st, d = await api_post("/api/shop/register", {"id": uid, "phone": m.contact.phone_number,
        "name": m.from_user.first_name or "user", "username": m.from_user.username or ""})
    if st == 0: return await m.answer("⚠️ Сервер недоступен, попробуй через минуту")
    if st != 200: return await m.answer(f"⚠️ Ошибка: {d}")
    flow.pop(uid, None)
    await m.answer("✅ Регистрация пройдена. Открывай магазин.", reply_markup=ReplyKeyboardRemove())
    await welcome(m)

@dp.message(F.forward_from)
async def fwd_id(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    await m.answer(f"🆔 ID отправителя: <code>{m.forward_from.id}</code> · {m.forward_from.first_name}", parse_mode="HTML")

@dp.message(F.text)
async def text_reg(m: types.Message):
    uid = str(m.from_user.id)
    f = flow.get(uid)
    if not f or f.get('step') != 'reg': return
    t = m.text.strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if not PHONE_RE.match(t):
        return await m.answer("⚠️ Кнопка контакта или номер целиком: +998XXXXXXXXX")
    st, d = await api_post("/api/shop/register", {"id": uid, "phone": t,
        "name": m.from_user.first_name or "user", "username": m.from_user.username or ""})
    if st == 0: return await m.answer("⚠️ Сервер недоступен")
    if st != 200: return await m.answer(f"⚠️ Ошибка: {d}")
    flow.pop(uid, None)
    await m.answer("✅ Регистрация пройдена. Открывай магазин.")
    await welcome(m)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="sTONks Shop", web_app=WebAppInfo(url=API)))
        log.info('menu button set')
    except Exception as e:
        log.warning('menu button failed: %s', e)
    await dp.start_polling(bot, skip_updates=True, handle_signals=False)

if __name__ == '__main__':
    asyncio.run(main())