"""
bot.py — Telegram Bot (aiogram 3.x) for 83 SCHOOL + admin commands
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.markdown import hbold

from config import (BOT_TOKEN, WEBAPP_URL, REFERRAL_BONUS_INVITER,
                    REFERRAL_BONUS_INVITED, WEBHOOK_SECRET, ADMIN_TELEGRAM_ID)
from database import (init_db, get_user, create_user, update_user,
                      create_referral, add_transaction,
                      create_notification, get_top_users)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def is_admin(tid: int) -> bool:
    return ADMIN_TELEGRAM_ID is not None and tid == ADMIN_TELEGRAM_ID


def get_play_keyboard(user_id: int) -> InlineKeyboardMarkup:
    webapp_url = f"{WEBAPP_URL}?user_id={user_id}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Играть в 83 SCHOOL", web_app=WebAppInfo(url=webapp_url))],
        [InlineKeyboardButton(text="👥 Пригласить друзей", callback_data="referral")],
    ])


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_tg = message.from_user
    referrer_telegram_id = None

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

        if referrer_db and new_user:
            await update_user(referrer_telegram_id,
                              balance=referrer_db["balance"] + REFERRAL_BONUS_INVITER,
                              total_earned=referrer_db.get("total_earned", 0) + REFERRAL_BONUS_INVITER)
            await add_transaction(referrer_db["id"], REFERRAL_BONUS_INVITER, "referral_bonus")
            await update_user(user_tg.id, balance=REFERRAL_BONUS_INVITED, total_earned=REFERRAL_BONUS_INVITED)
            await add_transaction(new_user["id"], REFERRAL_BONUS_INVITED, "referral_welcome")
            try:
                await bot.send_message(referrer_telegram_id,
                    f"🎉 По вашей ссылке присоединился {hbold(user_tg.first_name or 'новый игрок')}!\n💰 +{REFERRAL_BONUS_INVITER:,} поинтов!")
            except Exception as e:
                logger.warning(f"Failed to notify inviter: {e}")

        welcome_text = (
            f"👋 Добро пожаловать, {hbold(user_tg.first_name or 'Игрок')}!\n\n"
            f"🥊 <b>83 SCHOOL</b> — тапай, прокачивай бойца, собирай поинты.\n\n"
            + (f"🎁 +{REFERRAL_BONUS_INVITED} поинтов за регистрацию по ссылке!\n\n" if referrer_db else "")
            + "👇 Жми кнопку:"
        )
    else:
        welcome_text = f"👋 С возвращением, {hbold(user_tg.first_name or 'Игрок')}!\n\n👇 Жми кнопку:"

    await message.answer(welcome_text, reply_markup=get_play_keyboard(user_tg.id), parse_mode="HTML")


@dp.callback_query(lambda c: c.data == "referral")
async def referral_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    ref_link = f"https://t.me/{(await bot.get_me()).username}?start=ref_{user_id}"
    text = (
        f"👥 <b>Рефералка 83 SCHOOL</b>\n\n"
        f"🎁 Тебе +{REFERRAL_BONUS_INVITER:,}, другу +{REFERRAL_BONUS_INVITED}\n\n"
        f"🔗 <code>{ref_link}</code>"
    )
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


# ===========================================================================
# ADMIN COMMANDS
# ===========================================================================

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Недоступно"); return
    await message.answer(
        "🛠 <b>Админ-команды</b>\n\n"
        "📨 /notify Текст — оповещение всем игрокам (в Telegram + в колокольчик в игре)\n"
        "💰 /grant ID КОЛ-ВО — выдать/забрать поинты (например: /grant 123 5000)\n"
        "📊 /stats — топ игроков\n"
        "🔔 /bells Текст — то же, что /notify, но только в колокольчик (без рассылки)",
        parse_mode="HTML",
    )


@dp.message(Command("notify"))
async def cmd_notify(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Недоступно"); return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Формат: /notify Текст сообщения"); return
    body = parts[1]
    await create_notification("📢 Оповещение", body)
    users = await get_top_users(100000)
    sent = 0
    for u in users:
        try:
            await bot.send_message(u["telegram_id"], f"📢 <b>83 SCHOOL</b>\n\n{body}", parse_mode="HTML")
            sent += 1
        except Exception:
            pass
    await message.answer(f"✅ Оповещение отправлено {sent} игрокам и добавлено в колокольчик 🔔")


@dp.message(Command("bells"))
async def cmd_bells(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Недоступно"); return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Формат: /bells Текст"); return
    await create_notification("📢 Оповещение", parts[1])
    await message.answer("✅ Добавлено в колокольчик 🔔 всем игрокам")


@dp.message(Command("grant"))
async def cmd_grant(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Недоступно"); return
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Формат: /grant ID КОЛ-ВО (минус = забрать)"); return
    try:
        tid = int(parts[1]); amount = float(parts[2])
    except ValueError:
        await message.answer("ID и количество — числами"); return
    target = await get_user(tid)
    if not target:
        await message.answer("Игрок не найден"); return
    await update_user(tid,
                      balance=target["balance"] + amount,
                      total_earned=target.get("total_earned", 0) + max(0, amount))
    await add_transaction(target["id"], amount, "admin_grant")
    await message.answer(f"✅ Игроку {tid} начислено {amount:+.0f} поинтов")


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Недоступно"); return
    top = await get_top_users(10)
    lines = [f"{i+1}. {u['first_name'] or u['username'] or u['telegram_id']} — {int(u['total_earned']):,} поинтов"
             for i, u in enumerate(top)]
    await message.answer("📊 <b>Топ игроков</b>\n\n" + "\n".join(lines), parse_mode="HTML")


# ===========================================================================

async def setup_webhook():
    url = WEBAPP_URL.rstrip("/") + "/api/telegram/webhook"
    await bot.set_webhook(url, secret_token=WEBHOOK_SECRET)
    logger.info(f"Webhook set: {url}")


async def main():
    await init_db()
    logger.info("Database initialized.")
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
