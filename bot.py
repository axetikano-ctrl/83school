"""bot.py — sTONks Shop: админ меняет %, диагностика подписки"""
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
        "⭐ Telegram Stars · Premium · Карточка Грамм · Подарки\n"
        "🧰 Кейсы и 🎡 колесо фортуны — внутри мини-аппа\n\n"
        "⚖️ Программа лояльности: баллы-звёзды копятся за активность и подписку, "
        "тратятся в кейсах/колесе. Шансы открыты честно. Заказы реальных товаров — через менеджера.\n\n👇 Открывай:",
        parse_mode="HTML", reply_markup=kb())

@dp.message(Command("help"))
async def help(m: types.Message):
    await m.answer(
        "🟢 sTONks Shop — программа лояльности.\n\n"
        "🧰 ФРИ-кейс: раз в 24ч, нужна подписка\n"
        "🧰 Кейс за 50⭐ и 🎡 колесо: за баллы\n"
        "/subcheck — диагностика подписки\n\n"
        "🛠 Админ:\n/addstars [id] N — начислить N звёзд\n"
        "/prob list — текущие проценты\n"
        "/prob case_free 25 25 25 25 — поменять шансы\n"
        "/prob case_50 20 20 20 20 20\n"
        "/prob wheel 20 20 20 20 20")

@dp.message(Command("subcheck"))
async def subcheck(m: types.Message):
    """Диагностика подписки на канал"""
    async with aiohttp.ClientSession() as s:
        async with s.get(API + "/api/shop/me", params={"id": str(m.from_user.id)}) as r:
            d = await r.json()
    diag = d.get("sub_diag", {})
    await m.answer(
        f"🔍 Диагностика подписки:\n\n"
        f"• Подписан: {'✅ да' if d.get('subscribed') else '❌ нет'}\n"
        f"• Статус в канале: <code>{diag.get('status', '?')}</code>\n"
        f"• Канал: {CHANNEL}\n"
        f"• Деталь: <code>{diag.get('error', 'ok')}</code>\n\n"
        f"Если status='left' или 'kicked' — ты не подписан.\n"
        f"Если status='member' / 'creator' / 'administrator' — подписан.\n"
        f"Если status='restricted' — тоже подписан (с ограничением).\n\n"
        f"💡 Чтобы бот видел подписку, он должен быть добавлен в канал как участник (не обязательно админ).",
        parse_mode="HTML")

@dp.message(Command("addstars"))
async def addstars(m: types.Message):
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
    await m.answer(f"✅ Начислено: {d.get('stars')} звёзд (баланс)")

@dp.message(Command("prob"))
async def prob(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        return await m.answer("⛔ Только админ")
    parts = (m.text or "").split()
    if len(parts) < 2:
        return await m.answer("Формат: /prob list | /prob case_free 25 25 25 25")
    if parts[1] == "list":
        async with aiohttp.ClientSession() as s:
            async with s.get(API + "/api/shop/prob") as r:
                d = await r.json()
        lines = []
        for k in ("case_free", "case_50", "wheel"):
            tbl = d[k]
            lines.append(f"• {k}:")
            for item in tbl:
                name = "NFT" if item["prize"] == "NFT" else f'{item["prize"]}⭐'
                lines.append(f"    {name} → {item['chance']}%")
        await m.answer("📊 Текущие шансы:\n\n" + "\n".join(lines))
        return
    key = parts[1]
    if key not in ("case_free", "case_50", "wheel"):
        return await m.answer("Ключ: case_free / case_50 / wheel")
    try:
        vals = [int(x) for x in parts[2:]]
    except ValueError:
        return await m.answer("Числами, напр. 25 25 25 25")
    async with aiohttp.ClientSession() as s:
        async with s.post(API + "/api/shop/setprob", json={"key": key, "chances": vals},
                          headers={"X-Admin-Id": str(ADMIN_ID)}) as r:
            status = r.status
            d = await r.json()
    if status == 200:
        lines = [f"{it['prize']}⭐ → {it['chance']}%" for it in d["table"]]
        await m.answer(f"✅ {key} обновлён:\n\n" + "\n".join(lines))
    else:
        await m.answer(f"⚠️ Ошибка: {d}")

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