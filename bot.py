"""
bot.py — CampusPay Telegram Bot
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, MenuButtonWebApp
from aiogram.utils.markdown import hbold
from config import BOT_TOKEN, WEBAPP_URL

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        f"👋 Привет, {hbold(message.from_user.first_name)}!\n\n"
        f"🏛 <b>CampusPay</b> — учебный прототип кампусного супер-аппа.\n\n"
        f"👇 Жми кнопку:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 Открыть CampusPay", web_app=WebAppInfo(url=WEBAPP_URL))]
        ]),
        parse_mode="HTML"
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "🏛 <b>CampusPay — учебный проект</b>\n\n"
        "Это демонстрационный прототип кампусного супер-аппа.\n\n"
        "⚠️ <b>Важно:</b>\n"
        "• Все данные демонстрационные, платежи не проводятся\n"
        "• Используется только для тестирования и обучения\n"
        "• Создатель не несёт ответственности за действия пользователя\n"
        "• Запрещено использовать для обмана или мошенничества\n\n"
        "📱 Открой приложение через кнопку в меню бота.",
        parse_mode="HTML"
    )


async def main():
    logger.info("Bot starting...")
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="📱 Открыть CampusPay", web_app=WebAppInfo(url=WEBAPP_URL)))
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())