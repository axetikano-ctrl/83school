"""bot.py — ВОЛК ТАП bot + регистрация + админ с кастом-персами + дисклеймер"""
import asyncio, logging, base64
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
                           MenuButtonWebApp, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove)
from aiogram.utils.markdown import hbold
from config import BOT_TOKEN, WEBAPP_URL

CHANNEL_URL = 'https://t.me/voystai'
CHAT_URL = 'https://t.me/voystai_chat'
ADMIN_PASS = '1221221'
ADMIN_SECRET = 'wolftap2026secret'

API = WEBAPP_URL.rstrip('/')
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
flow = {}

async def api_get(path, secret=False):
    h = {'X-Admin-Secret': ADMIN_SECRET} if secret else {}
    async with aiohttp.ClientSession() as s:
        async with s.get(API + path, headers=h) as r:
            return await r.json()

async def api_post(path, data, secret=False):
    h = {'X-Admin-Secret': ADMIN_SECRET} if secret else {}
    async with aiohttp.ClientSession() as s:
        async with s.post(API + path, json=data, headers=h) as r:
            return await r.json()

def game_kb(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🐺 ТАПАТЬ ВОЛКА", web_app=WebAppInfo(url=f"{API}?user_id={uid}"))],
        [InlineKeyboardButton(text="📢 Канал стаи", url=CHANNEL_URL),
         InlineKeyboardButton(text="💬 Чат стаи", url=CHAT_URL)],
    ])

CONTACT_KB = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True,
                                 keyboard=[[KeyboardButton(text="📱 Отправить контакт", request_contact=True)]])

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить перса", callback_data="adm:add")],
        [InlineKeyboardButton(text="📋 Список персов", callback_data="adm:list")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="adm:bc")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="adm:stats")],
    ])

async def welcome(m: types.Message):
    await m.answer(
        f"🌙 {hbold(m.from_user.first_name or 'волк')}, ты в стае.\n\n"
        "🐺 Тапай волка → копи ВОЙ → расти до ОДИНОЧКИ.\n"
        "🔓 Открывай персов за тапы и ВОЙ.\n\n"
        "⚖️ Проект учебный. Автор не несёт ответственности и никого ни к чему не призывает.\n\n👇 Жми:",
        parse_mode="HTML", reply_markup=game_kb(m.from_user.id))

@dp.message(CommandStart())
async def start(m: types.Message):
    uid = str(m.from_user.id)
    try:
        me = await api_get(f"/api/me?id={uid}")
        reg = me.get("registered", False)
    except Exception:
        reg = False
    if not reg:
        flow[uid] = {'step': 'reg'}
        await m.answer("🌙 Добро пожаловать в ВОЛК ТАП.\n\n📱 Для регистрации отправь свой контакт кнопкой ниже — стая должна знать своих:",
                       reply_markup=CONTACT_KB)
    else:
        await welcome(m)

@dp.message(F.contact)
async def on_contact(m: types.Message):
    uid = str(m.from_user.id)
    await api_post("/api/register", {"id": uid, "phone": m.contact.phone_number,
                                     "name": m.from_user.first_name or "волк"})
    flow.pop(uid, None)
    await m.answer("✅ Контакт принят. Ты в стае, волк!", reply_markup=ReplyKeyboardRemove())
    await welcome(m)

@dp.message(Command("help"))
async def help(m: types.Message):
    await m.answer("🐺 ВОЛК ТАП — мемная тапалка для одиночек.\n\n"
                   "• Тапай волка — получай ВОЙ\n• Комбо → шанс КРИТА x5\n"
                   "• Ранги: Щенок → Волк → Матёрый → Альфа → ОДИНОЧКА 🌙\n"
                   "• Персы открываются за тапы или ВОЙ и дают множитель\n\n"
                   "⚖️ Дисклеймер: проект создан для обучения. Автор не несёт ответственности за действия пользователей и никого не призывал к действиям. Всё ненастоящее.")

@dp.message(Command("admin"))
async def admin(m: types.Message):
    flow[str(m.from_user.id)] = {'step': 'pass'}
    await m.answer("🔐 Введи пароль админа:")

@dp.message(F.photo)
async def photo_flow(m: types.Message):
    uid = str(m.from_user.id)
    f = flow.get(uid)
    if not f or f.get('step') != 'char_photo':
        return
    ph = m.photo[-1]
    try:
        fg = await bot.get_file(ph.file_id)
        bio = await bot.download_file(fg.file_path)
        raw = bio.read()
        if len(raw) > 1_500_000:
            return await m.answer("⚠️ Фотка тяжелее 1.5MB — пришли поменьше:")
        f['image'] = 'data:image/jpeg;base64,' + base64.b64encode(raw).decode()
        f['step'] = 'char_mult'
        await m.answer("📸 Фото принято.\n✖️ Множитель тапа (напр. 2 или 1.5):")
    except Exception:
        await m.answer("Не смог скачать фото. Ещё раз:")

@dp.message(F.text)
async def text_flow(m: types.Message):
    uid = str(m.from_user.id)
    f = flow.get(uid)
    if not f:
        return
    step = f['step']
    if step == 'pass':
        if m.text.strip() == ADMIN_PASS:
            flow.pop(uid)
            await m.answer("🛠 Админ-меню:", reply_markup=admin_kb())
        else:
            await m.answer("❌ Неверно. Ещё раз:")
    elif step == 'char_name':
        f['name'] = m.text.strip()[:20]; f['step'] = 'char_photo'
        await m.answer("📸 Пришли ФОТО перса картинкой\n(или напиши «пропустить»):")
    elif step == 'char_photo':
        if m.text.strip().lower() in ('пропустить', 'нет', '-'):
            f['image'] = ''
        f['step'] = 'char_mult'
        await m.answer("✖️ Множитель тапа (напр. 2 или 1.5):")
    elif step == 'char_mult':
        try:
            f['mult'] = float(m.text.replace(',', '.'))
        except ValueError:
            return await m.answer("Числом напиши:")
        f['step'] = 'char_cur'
        await m.answer("💳 За что открывать перса?\nНапиши: ТАПЫ или ВОЙ")
    elif step == 'char_cur':
        t = m.text.strip().lower()
        f['cur'] = 'balance' if ('вой' in t or 'баланс' in t) else 'taps'
        f['step'] = 'char_price'
        await m.answer("💰 Цена открытия (числом, напр. 10000):")
    elif step == 'char_price':
        try:
            f['price'] = int(m.text.replace(' ', ''))
        except ValueError:
            return await m.answer("Числом напиши:")
        await api_post("/api/admin/chars", {
            "name": f['name'], "mult": f['mult'], "image": f.get('image', ''),
            "price": f['price'], "cur": f['cur']}, secret=True)
        flow.pop(uid)
        cur = 'тапов' if f['cur'] == 'taps' else 'ВОЙ'
        await m.answer(f"✅ Перс «{f['name']}» создан:\n✖️ x{f['mult']} · 🔓 за {f['price']} {cur}",
                       reply_markup=admin_kb())
    elif step == 'bc':
        users = await api_get("/api/admin/users", secret=True)
        sent = 0
        for u in users.get("users", []):
            try:
                await bot.send_message(int(u["id"]), f"📢 <b>Стае:</b>\n\n{m.text}", parse_mode="HTML")
                sent += 1
            except Exception:
                pass
        flow.pop(uid)
        await m.answer(f"📨 Отправлено {sent} волкам", reply_markup=admin_kb())

@dp.callback_query(F.data.startswith("adm:"))
async def adm_cb(c: types.CallbackQuery):
    uid = str(c.from_user.id)
    act = c.data.split(":")[1]
    if act == 'add':
        flow[uid] = {'step': 'char_name'}
        await c.message.answer("Имя перса (напр. Сигма-Волк):")
    elif act == 'list':
        chars = await api_get("/api/admin/chars", secret=True)
        if not chars.get("chars"):
            await c.message.answer("Персов пока нет.")
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"{ch['name']} x{ch['mult']} · {ch['price']} {'тапов' if ch['cur']=='taps' else 'ВОЙ'} — удалить",
                    callback_data=f"adm:del:{ch['id']}")]
                for ch in chars["chars"]])
            await c.message.answer("📋 Персы:", reply_markup=kb)
    elif act == 'del':
        cid = c.data.split(":")[2]
        await api_post(f"/api/admin/chars/{cid}/delete", {}, secret=True)
        await c.message.answer("🗑 Удалён.")
    elif act == 'bc':
        flow[uid] = {'step': 'bc'}
        await c.message.answer("Текст рассылки:")
    elif act == 'stats':
        st = await api_get("/api/admin/stats", secret=True)
        await c.message.answer(f"📊 Волков: {st['users']}\nЗарегистрировано: {st['registered']}\nВсего тапов: {st['taps']}\nВсего ВОЯ: {st['balance']}")
    await c.answer()

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="🐺 ТАПАТЬ", web_app=WebAppInfo(url=API)))
    except Exception:
        pass
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())