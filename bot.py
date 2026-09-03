 """
bot.py — Telegram Bot (aiogram 3.x) for 83 SCHOOL
Работает локально через polling и в Render через webhook.
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.markdown import hbold

from config import (
    BOT_TOKEN,
    WEBAPP_URL,
    REFERRAL_BONUS_INVITER,
    REFERRAL_BONUS_INVITED,
    WEBHOOK_SECRET,
)
from database import (
    init_db,
    get_user,
    create_user,
    update_user,
    create_referral,
    add_transaction,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def get_play_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Кнопка запуска Telegram WebApp."""
    webapp_url = f"{WEBAPP_URL.rstrip('/')}?user_id={user_id}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎮 Играть в 83 SCHOOL",
                    web_app=WebAppInfo(url=webapp_url),
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Пригласить друзей",
                    callback_data="referral",
                )
            ],
        ]
    )


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    """
    /start
    /start ref_123456789
    """
    user_tg = message.from_user
    referrer_telegram_id = None

    # Парсим реферальный параметр
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        param = args[1].strip()
        if param.startswith("ref_"):
            try:
                referrer_telegram_id = int(param[4:])
                if referrer_telegram_id == user_tg.id:
                    referrer_telegram_id = None
            except ValueError:
                referrer_telegram_id = None

    existing_user = await get_user(user_tg.id)

    if not existing_user:
        referrer_db = None

        if referrer_telegram_id:
            referrer_db = await get_user(referrer_telegram_id)

        new_user = await create_user(
            telegram_id=user_tg.id,
            username=user_tg.username,
            first_name=user_tg.first_name or "Игрок",
            referrer_id=referrer_db["id"] if referrer_db else None,
        )

        # Реферальные бонусы
        if referrer_db and new_user:
            await update_user(
                referrer_telegram_id,
                balance=referrer_db["balance"] + REFERRAL_BONUS_INVITER,
                total_earned=referrer_db.get("total_earned", 0) + REFERRAL_BONUS_INVITER,
            )
            await add_transaction(
                referrer_db["id"],
                REFERRAL_BONUS_INVITER,
                "referral_bonus",
            )

            await update_user(
                user_tg.id,
                balance=REFERRAL_BONUS_INVITED,
                total_earned=REFERRAL_BONUS_INVITED,
            )
            await add_transaction(
                new_user["id"],
                REFERRAL_BONUS_INVITED,
                "referral_welcome",
            )

            await create_referral(referrer_db["id"], new_user["id"])

            try:
                await bot.send_message(
                    referrer_telegram_id,
                    f"🎉 По твоей ссылке присоединился "
                    f"{hbold(user_tg.first_name or 'новый игрок')}!\n"
                    f"💰 Ты получил +{REFERRAL_BONUS_INVITER:,} поинтов!",
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning(f"Failed to notify inviter: {e}")

        welcome_text = (
            f"👋 Добро пожаловать, {hbold(user_tg.first_name or 'Игрок')}!\n\n"
            f"🥊 <b>83 SCHOOL</b> — минималистичный тап-кликер.\n\n"
            f"Тапай, собирай поинты, прокачивай бойца и поднимайся в топ.\n\n"
        )

        if referrer_db:
            welcome_text += (
                f"🎁 Ты получил <b>+{REFERRAL_BONUS_INVITED} поинтов</b> "
                f"за регистрацию по ссылке!\n\n"
            )

        welcome_text += "👇 Жми кнопку ниже, чтобы начать:"
    else:
        welcome_text = (
            f"👋 С возвращением, {hbold(user_tg.first_name or 'Игрок')}!\n\n"
            f"🥊 Продолжай играть в <b>83 SCHOOL</b>.\n\n"
            f"👇 Жми кнопку ниже:"
        )

    await message.answer(
        welcome_text,
        reply_markup=get_play_keyboard(user_tg.id),
        parse_mode="HTML",
    )


@dp.callback_query(lambda c: c.data == "referral")
async def referral_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    try:
        me = await bot.get_me()
        bot_username = me.username
    except Exception:
        bot_username = None

    if bot_username:
        ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    else:
        ref_link = "Ошибка: username бота не найден"

    text = (
        f"👥 <b>Реферальная программа 83 SCHOOL</b>\n\n"
        f"🎁 За каждого приглашённого друга:\n"
        f"• Ты получаешь <b>+{REFERRAL_BONUS_INVITER:,} поинтов</b>\n"
        f"• Друг получает <b>+{REFERRAL_BONUS_INVITED:,} поинтов</b>\n\n"
        f"🔗 Твоя ссылка:\n"
        f"<code>{ref_link}</code>\n\n"
        f"Скопируй и отправь друзьям."
    )

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


async def setup_webhook():
    """
    Эта функция нужна Render.
    run.py импортирует её так:
    from bot import setup_webhook
    """
    webhook_url = WEBAPP_URL.rstrip("/") + "/api/telegram/webhook"

    await bot.set_webhook(
        webhook_url,
        secret_token=WEBHOOK_SECRET,
        drop_pending_updates=True,
    )

    logger.info(f"Webhook set: {webhook_url}")


async def main():
    """
    Локальный запуск bot.py через polling.
    На Render используется setup_webhook() из run.py.
    """
    await init_db()
    logger.info("Database initialized.")
    logger.info("Starting bot polling...")

    # Если до этого был webhook, локально polling не стартанёт без удаления webhook
    await bot.delete_webhook(drop_pending_updates=True)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
