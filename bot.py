"""bot.py — MUG0VE personal super-app bot"""
import asyncio, logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, MenuButtonWebApp
from aiogram.utils.markdown import hbold
from config import BOT_TOKEN, WEBAPP_URL

API = WEBAPP_URL.rstrip('/')
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def kb(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏛 Открыть MUG0VE", web_app=WebAppInfo(url=f"{API}?user_id={uid}"))],
    ])

@dp.message(CommandStart())
async def start(m: types.Message):
    await m.answer(
        f"👋 {hbold(m.from_user.first_name or 'друг')}, это MUG0VE — личный супер-апп для тебя и твоей пары.\n\n"
        "🏛 Услуги, виджеты, личная карта, QR — всё внутри.\n\n"
        "⚖️ Проект учебный, создан для обучения. Автор не несёт ответственности и никого ни к чему не призывает. Всё ненастоящее.\n\n"
        "👇 Жми:",
        parse_mode="HTML", reply_markup=kb(m.from_user.id))

@dp.message(Command("help"))
async def help(m: types.Message):
    await m.answer(
        "🏛 MUG0VE — личный демонстрационный супер-апп.\n\n"
        "• Главная: услуги, виджеты, поиск\n• QR: покажи код партнёру\n"
        "• Профиль: личная карта MUG0VE PASS, фото, настройки\n\n"
        "⚖️ Дисклеймер: проект создан исключительно для обучения. Автор не несёт ответственности за действия пользователей и никого не призывал к действиям. Все данные и «документы» ненастоящие и не являются документами.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="🏛 MUG0VE", web_app=WebAppInfo(url=API)))
    except Exception:
        pass
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())