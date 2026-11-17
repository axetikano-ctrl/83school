"""bot.py — GRAM Wallet & Market: синий мини-апп, норм /start"""
import asyncio, logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, MenuButtonWebApp
from aiogram.utils.markdown import hbold
from config import BOT_TOKEN, WEBAPP_URL

API = WEBAPP_URL.rstrip('/')
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('gram-bot')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Открыть GRAM Wallet", web_app=WebAppInfo(url=API))],
        [InlineKeyboardButton(text="🎁 Маркет подарков", web_app=WebAppInfo(url=API))],
        [InlineKeyboardButton(text="🚀 Питч для инвесторов", web_app=WebAppInfo(url=API))],
    ])

@dp.message(CommandStart())
async def start(m: types.Message):
    await m.answer(
        f"🔷 {hbold(m.from_user.first_name or 'друг')}, добро пожаловать в GRAM.\n\n"
        "💎 Кошелёк TON: баланс, отправка, история\n"
        "🎁 Маркет подарков: продавцы выставляют СВОИ подарки, сделки официально\n"
        "🚀 Питч: roadmap и метрики продукта\n\n"
        "⚖️ Учебный демо-проект: данные ненастоящие, бот не имитирует системные сообщения Telegram и не проводит «офферов».\n\n"
        "👇 Открывай:",
        parse_mode="HTML", reply_markup=kb())

@dp.message(Command("help"))
async def help(m: types.Message):
    await m.answer(
        "🔷 GRAM — демо кошелёк + маркетплейс подарков.\n\n"
        "/start — главное меню с кнопками мини-аппа\n"
        "/market — как работает честная витрина\n\n"
        "Продавец сам выставляет свой подарок (ссылка, цена, контакт). "
        "Покупатель пишет ему в личку, сделка идёт официально через Telegram. "
        "Никаких фейковых «принять/отклонить» от имени системы.")

@dp.message(Command("market"))
async def market(m: types.Message):
    await m.answer(
        "🎁 Как продать подарок честно:\n\n"
        "1. Открой мини-апп → Маркет\n2. Выстави своё объявление: ссылка, цена ⭐, контакт\n"
        "3. Покупатель пишет тебе в личку → передаёшь подарок официально\n\n"
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