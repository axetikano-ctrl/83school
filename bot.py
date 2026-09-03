"""
bot.py — Telegram Bot (aiogram 3.x)
Запускается отдельно от FastAPI сервера.
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.markdown import hbold

from config import BOT_TOKEN, WEBAPP_URL, REFERRAL_BONUS_INVITER, REFERRAL_BONUS_INVITED, WEBHOOK_SECRET
from database import init_db, get_user, create_user, update_user, create_referral, add_transaction

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def get_play_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Returns inline keyboard with WebApp launch button."""
    webapp_url = f"{WEBAPP_URL}?user_id={user_id}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🚀 Запустить Antigravity",
                web_app=WebAppInfo(url=webapp_url),
            )
        ],
        [
            InlineKeyboardButton(
                text="👥 Пригласить друзей",
                callback_data="referral",
            )
        ],
    ])


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    """
    /start [ref_<telegram_id>] handler.
    Registers user, handles referral, shows WebApp button.
    """
    user_tg = message.from_user
    referrer_telegram_id: int | None = None

    # Parse referral param: /start ref_12345
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        param = args[1].strip()
        if param.startswith("ref_"):
            try:
                referrer_telegram_id = int(param[4:])
                # Don't allow self-referral
                if referrer_telegram_id == user_tg.id:
                    referrer_telegram_id = None
            except ValueError:
                referrer_telegram_id = None

    # Check if user exists
    existing_user = await get_user(user_tg.id)

    if not existing_user:
        # New user — create and handle referral
        referrer_db = None
        if referrer_telegram_id:
            referrer_db = await get_user(referrer_telegram_id)

        new_user = await create_user(
            telegram_id=user_tg.id,
            username=user_tg.username,
            first_name=user_tg.first_name or "Игрок",
            referrer_id=referrer_db["id"] if referrer_db else None,
        )

        # Grant referral bonuses
        if referrer_db and new_user:
            # Bonus to inviter
            await update_user(
                referrer_telegram_id,
                balance=referrer_db["balance"] + REFERRAL_BONUS_INVITER,
            )
            await add_transaction(referrer_db["id"], REFERRAL_BONUS_INVITER, "referral_bonus")

            # Bonus to new user
            await update_user(
                user_tg.id,
                balance=REFERRAL_BONUS_INVITED,
            )
            await add_transaction(new_user["id"], REFERRAL_BONUS_INVITED, "referral_welcome")

            # Notify inviter
            try:
                await bot.send_message(
                    referrer_telegram_id,
                    f"🎉 По вашей ссылке присоединился {hbold(user_tg.first_name or 'новый игрок')}!\n"
                    f"💰 Вы получили +{REFERRAL_BONUS_INVITER:,} AG монет!",
                )
            except Exception as e:
                logger.warning(f"Failed to notify inviter: {e}")

        welcome_text = (
            f"👋 Добро пожаловать, {hbold(user_tg.first_name or 'Игрок')}!\n\n"
            f"⚡ <b>Antigravity</b> — космический кликер нового поколения.\n\n"
            f"🌌 Тапай, собирай <b>AG монеты</b>, открывай апгрейды и покоряй невесомость!\n\n"
            + (f"🎁 Ты получил <b>+{REFERRAL_BONUS_INVITED} монет</b> за регистрацию по реферальной ссылке!\n\n"
               if referrer_db else "")
            + "👇 Нажми кнопку ниже, чтобы начать:"
        )
    else:
        welcome_text = (
            f"👋 С возвращением, {hbold(user_tg.first_name or 'Игрок')}!\n\n"
            f"🚀 Продолжай собирать <b>AG монеты</b> в Antigravity!\n\n"
            f"💰 Твой баланс ждёт тебя..."
        )

    await message.answer(
        welcome_text,
        reply_markup=get_play_keyboard(user_tg.id),
        parse_mode="HTML",
    )


@dp.callback_query(lambda c: c.data == "referral")
async def referral_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    ref_link = f"https://t.me/{(await bot.get_me()).username}?start=ref_{user_id}"
    text = (
        f"👥 <b>Реферальная программа Antigravity</b>\n\n"
        f"🎁 За каждого приглашённого друга:\n"
        f"  • Ты получаешь <b>+{REFERRAL_BONUS_INVITER:,} AG монет</b>\n"
        f"  • Друг получает <b>+{REFERRAL_BONUS_INVITED:,} AG монет</b>\n\n"
        f"🔗 Твоя ссылка:\n<code>{ref_link}</code>\n\n"
        f"Скопируй и поделись с друзьями!"
    )
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


async def main():
  async def setup_webhook():
    url = WEBAPP_URL.rstrip("/") + "/api/telegram/webhook"
    await bot.set_webhook(url, secret_token=WEBHOOK_SECRET)
    logger.info(f"Webhook set: {url}")  
    await init_db()
    logger.info("Database initialized.")
    logger.info("Starting Antigravity Bot...")
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
