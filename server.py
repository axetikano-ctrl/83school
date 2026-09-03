"""
server.py — FastAPI HTTP server for 83 SCHOOL game API
Includes game API + admin API + notifications + telegram webhook.
"""
import os
import time
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from aiogram.types import Update as TgUpdate
from bot import bot as tg_bot, dp as tg_dp

from config import (
    DAILY_BONUS_AMOUNT,
    MAX_TAPS_PER_WINDOW,
    REFERRAL_BONUS_INVITER,
    REFERRAL_BONUS_INVITED,
    ADMIN_TELEGRAM_ID,
    WEBHOOK_SECRET,
)
from database import (
    init_db, get_user, create_user, update_user,
    apply_passive_income, apply_energy_regen,
    get_user_upgrades, set_upgrade_level,
    get_referrals, create_referral, mark_referral_reward, add_transaction,
    get_characters, get_character, create_character, update_character, delete_character,
    get_shop_items, get_shop_item, create_shop_item, update_shop_item, delete_shop_item,
    get_user_shop_levels, set_user_shop_level, compute_item_price,
    get_top_users, get_notifications, create_notification,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

CHARACTERS_UPLOAD_DIR = Path("frontend/assets/characters")
CHARACTERS_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class InitRequest(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    ref: Optional[str] = None


class SyncRequest(BaseModel):
    telegram_id: int
    taps: int
    energy_spent: float
    client_ts: float


class BuyShopItemRequest(BaseModel):
    telegram_id: int
    item_id: int


class ClaimDailyRequest(BaseModel):
    telegram_id: int


class AdminCharacterCreate(BaseModel):
    name: str
    description: str = ""
    base_tap_power: int = 1
    base_energy: int = 1000
    base_passive: int = 0
    color: str = "#e0e0e0"
    emoji: str = "👤"
    image: str = ""
    sort_order: int = 0


class AdminCharacterUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    base_tap_power: Optional[int] = None
    base_energy: Optional[int] = None
    base_passive: Optional[int] = None
    color: Optional[str] = None
    emoji: Optional[str] = None
    image: Optional[str] = None
    active: Optional[int] = None
    sort_order: Optional[int] = None


class AdminShopItemCreate(BaseModel):
    name: str
    description: str = ""
    icon: str = "⬆️"
    effect_type: str
    effect_value: float = 1
    base_price: int = 500
    price_multiplier: float = 3.0
    max_level: int = 7
    sort_order: int = 0


class AdminShopItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    effect_type: Optional[str] = None
    effect_value: Optional[float] = None
    base_price: Optional[int] = None
    price_multiplier: Optional[float] = None
    max_level: Optional[int] = None
    active: Optional[int] = None
    sort_order: Optional[int] = None


class AdminGrantRequest(BaseModel):
    admin_id: int
    target_telegram_id: int
    amount: float
    reason: str = "admin_grant"


class AdminNotificationCreate(BaseModel):
    title: str
    message: str


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database initialized and seeded.")
    yield


app = FastAPI(title="83 SCHOOL API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
async def serve_frontend():
    return FileResponse("frontend/index.html")


@app.get("/admin")
async def serve_admin():
    return FileResponse("frontend/admin.html")


# ---------------------------------------------------------------------------
# Telegram webhook (для облака)
# ---------------------------------------------------------------------------

@app.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    if request.headers.get("x-telegram-bot-api-secret-token", "") != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")
    data = await request.json()
    await tg_dp.feed_update(tg_bot, TgUpdate(**data))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Admin auth helper
# ---------------------------------------------------------------------------

def check_admin(telegram_id: int):
    if not ADMIN_TELEGRAM_ID:
        raise HTTPException(status_code=403, detail="Admin not configured. Set ADMIN_TELEGRAM_ID in .env")
    if telegram_id != ADMIN_TELEGRAM_ID:
        raise HTTPException(status_code=403, detail="Доступ запрещён")


# ---------------------------------------------------------------------------
# Game helpers
# ---------------------------------------------------------------------------

def compute_level(total_earned: float) -> int:
    return int(total_earned // 10000) + 1

def get_user_character(characters: list, level: int) -> dict:
    if not characters:
        return {}
    idx = min(level - 1, len(characters) - 1)
    return characters[idx]


async def update_user_stats_in_db(telegram_id: int):
    user = await get_user(telegram_id)
    if not user:
        return

    level = compute_level(user.get("total_earned", 0))
    characters = await get_characters(active_only=True)
    char = get_user_character(characters, level)

    tap_power = char.get("base_tap_power", 1)
    max_energy = char.get("base_energy", 1000)
    energy_regen = 1.0
    passive_income = char.get("base_passive", 0)

    shop_items = await get_shop_items(active_only=True)
    user_levels = await get_user_shop_levels(user["id"])
    for item in shop_items:
        lvl = user_levels.get(item["id"], 0)
        if lvl > 0:
            if item["effect_type"] == "tap_power":
                tap_power += item["effect_value"] * lvl
            elif item["effect_type"] == "max_energy":
                max_energy += item["effect_value"] * lvl
            elif item["effect_type"] == "energy_regen":
                energy_regen += item["effect_value"] * lvl
            elif item["effect_type"] == "passive_income":
                passive_income += item["effect_value"] * lvl

    tap_power += (level - 1) * 1
    new_energy = min(user["energy"], max_energy)

    await update_user(
        telegram_id,
        tap_power=int(tap_power),
        max_energy=int(max_energy),
        energy_regen=round(energy_regen, 2),
        passive_income=int(passive_income),
        level=level,
        energy=new_energy,
    )


async def build_shop_state(user: dict) -> list:
    items = await get_shop_items(active_only=True)
    user_levels = await get_user_shop_levels(user["id"])
    result = []
    for item in items:
        cur_level = user_levels.get(item["id"], 0)
        is_max = cur_level >= item["max_level"]
        next_price = None if is_max else compute_item_price(
            item["base_price"], item["price_multiplier"], cur_level
        )
        result.append({
            "id": item["id"],
            "name": item["name"],
            "description": item["description"],
            "icon": item["icon"],
            "effect_type": item["effect_type"],
            "effect_value": item["effect_value"],
            "current_level": cur_level,
            "max_level": item["max_level"],
            "is_max": is_max,
            "next_price": next_price,
            "can_afford": (next_price is not None and user["balance"] >= next_price),
        })
    return result


async def build_profile(user: dict) -> dict:
    await update_user_stats_in_db(user["telegram_id"])
    user = await get_user(user["telegram_id"])

    level = user["level"]
    shop_state = await build_shop_state(user)
    characters = await get_characters(active_only=True)
    char = get_user_character(characters, level)

    return {
        "telegram_id": user["telegram_id"],
        "username": user["username"],
        "first_name": user["first_name"],
        "balance": round(user["balance"], 2),
        "tap_power": user["tap_power"],
        "energy": round(user["energy"], 1),
        "max_energy": user["max_energy"],
        "energy_regen": user["energy_regen"],
        "passive_income": user["passive_income"],
        "total_taps": user["total_taps"],
        "total_earned": round(user.get("total_earned", 0), 2),
        "level": level,
        "character": char,
        "daily_claimed": user["daily_claimed"],
        "shop": shop_state,
        "created_at": user["created_at"],
        "is_admin": (ADMIN_TELEGRAM_ID is not None and user["telegram_id"] == ADMIN_TELEGRAM_ID),
    }


# ---------------------------------------------------------------------------
# Game API
# ---------------------------------------------------------------------------

@app.post("/api/init")
async def api_init(req: InitRequest):
    user = await get_user(req.telegram_id)

    if not user:
        referrer_db = None
        referrer_telegram_id = None
        if req.ref and req.ref.startswith("ref_"):
            try:
                referrer_telegram_id = int(req.ref[4:])
                if referrer_telegram_id != req.telegram_id:
                    referrer_db = await get_user(referrer_telegram_id)
            except ValueError:
                pass

        user = await create_user(
            telegram_id=req.telegram_id,
            username=req.username,
            first_name=req.first_name or "Игрок",
            referrer_id=referrer_db["id"] if referrer_db else None,
        )

        if referrer_db and user:
            await update_user(
                referrer_telegram_id,
                balance=referrer_db["balance"] + REFERRAL_BONUS_INVITER,
                total_earned=referrer_db.get("total_earned", 0) + REFERRAL_BONUS_INVITER,
            )
            await add_transaction(referrer_db["id"], REFERRAL_BONUS_INVITER, "referral_bonus")
            await update_user(
                req.telegram_id,
                balance=REFERRAL_BONUS_INVITED,
                total_earned=REFERRAL_BONUS_INVITED,
            )
            await add_transaction(user["id"], REFERRAL_BONUS_INVITED, "referral_welcome")
            await create_referral(referrer_db["id"], user["id"])
            user = await get_user(req.telegram_id)
    else:
        user = await apply_passive_income(user)
        user = await apply_energy_regen(user)

    await update_user(req.telegram_id, last_seen=time.time())
    user = await get_user(req.telegram_id)
    return {"ok": True, "user": await build_profile(user)}


@app.post("/api/sync")
async def api_sync(req: SyncRequest):
    user = await get_user(req.telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user = await apply_energy_regen(user)
    now = time.time()

    if req.taps < 0:
        raise HTTPException(status_code=400, detail="Invalid taps")

    if req.taps > MAX_TAPS_PER_WINDOW:
        logger.warning(f"Anti-cheat: {req.telegram_id} sent {req.taps} taps")
        req.taps = MAX_TAPS_PER_WINDOW

    actual_taps = min(req.taps, int(user["energy"]))

    if actual_taps <= 0:
        user = await get_user(req.telegram_id)
        return {"ok": True, "user": await build_profile(user)}

    coins_earned = actual_taps * user["tap_power"]
    new_energy = max(0.0, user["energy"] - actual_taps)
    new_balance = user["balance"] + coins_earned
    new_total_taps = user["total_taps"] + actual_taps
    new_total_earned = user.get("total_earned", 0) + coins_earned

    await update_user(
        req.telegram_id,
        balance=new_balance,
        energy=new_energy,
        total_taps=new_total_taps,
        total_earned=new_total_earned,
        last_seen=now,
        level=compute_level(new_total_earned),
    )
    await add_transaction(user["id"], coins_earned, "taps")

    user = await get_user(req.telegram_id)
    return {"ok": True, "user": await build_profile(user)}


@app.get("/api/shop")
async def api_shop(telegram_id: int):
    user = await get_user(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    shop = await build_shop_state(user)
    return {"ok": True, "shop": shop, "balance": round(user["balance"], 2)}


@app.post("/api/buy-shop-item")
async def api_buy_shop_item(req: BuyShopItemRequest):
    user = await get_user(req.telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    item = await get_shop_item(req.item_id)
    if not item or not item["active"]:
        raise HTTPException(status_code=404, detail="Товар не найден")

    user_levels = await get_user_shop_levels(user["id"])
    cur_level = user_levels.get(item["id"], 0)

    if cur_level >= item["max_level"]:
        raise HTTPException(status_code=400, detail="Максимальный уровень")

    price = compute_item_price(item["base_price"], item["price_multiplier"], cur_level)
    if user["balance"] < price:
        raise HTTPException(status_code=400, detail="Недостаточно монет")

    updates = {"balance": user["balance"] - price}
    effect_type = item["effect_type"]
    effect_value = item["effect_value"]

    if effect_type == "tap_power":
        updates["tap_power"] = int(user["tap_power"] + effect_value)
    elif effect_type == "max_energy":
        updates["max_energy"] = int(user["max_energy"] + effect_value)
        updates["energy"] = min(user["energy"] + effect_value, updates["max_energy"])
    elif effect_type == "energy_regen":
        updates["energy_regen"] = round(user["energy_regen"] + effect_value, 2)
    elif effect_type == "passive_income":
        updates["passive_income"] = int(user["passive_income"] + effect_value)

    new_level = cur_level + 1
    await set_user_shop_level(user["id"], item["id"], new_level)
    await update_user(req.telegram_id, **updates)
    await add_transaction(user["id"], -price, f"shop_{item['name']}_lvl{new_level}")

    user = await get_user(req.telegram_id)
    return {
        "ok": True,
        "message": f"✅ {item['name']} — уровень {new_level}!",
        "user": await build_profile(user),
    }


@app.post("/api/claim-daily")
async def api_claim_daily(req: ClaimDailyRequest):
    user = await get_user(req.telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = time.time()
    cooldown = 22 * 3600
    if now - user["daily_claimed"] < cooldown:
        remaining = cooldown - (now - user["daily_claimed"])
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        raise HTTPException(
            status_code=400,
            detail=f"Бонус уже получен. Следующий через {hours}ч {minutes}мин"
        )

    level = compute_level(user.get("total_earned", 0))
    bonus = DAILY_BONUS_AMOUNT * level
    new_total_earned = user.get("total_earned", 0) + bonus

    await update_user(
        req.telegram_id,
        balance=user["balance"] + bonus,
        daily_claimed=now,
        total_earned=new_total_earned,
    )
    await add_transaction(user["id"], bonus, "daily_bonus")
    user = await get_user(req.telegram_id)

    return {
        "ok": True,
        "bonus": bonus,
        "message": f"Ежедневный бонус: +{bonus:,} монет!",
        "user": await build_profile(user),
    }


@app.get("/api/referrals")
async def api_referrals(telegram_id: int):
    user = await get_user(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    referrals = await get_referrals(telegram_id)
    return {
        "ok": True,
        "referrals": referrals,
        "count": len(referrals),
        "total_earned": len(referrals) * REFERRAL_BONUS_INVITER,
    }


@app.get("/api/characters")
async def api_characters():
    chars = await get_characters(active_only=True)
    return {"ok": True, "characters": chars}


@app.get("/api/leaderboard")
async def api_leaderboard():
    users = await get_top_users(20)
    return {"ok": True, "leaderboard": users}


@app.get("/api/info")
async def api_info():
    return {"ok": True, "bot_username": os.getenv("BOT_USERNAME", "")}


@app.get("/api/notifications")
async def api_notifications():
    notes = await get_notifications(50)
    return {"ok": True, "notifications": notes}


# ===========================================================================
# ADMIN API
# ===========================================================================

@app.get("/api/admin/characters")
async def admin_list_characters(admin_id: int):
    check_admin(admin_id)
    chars = await get_characters(active_only=False)
    return {"ok": True, "characters": chars}


@app.post("/api/admin/characters")
async def admin_create_character(admin_id: int, data: AdminCharacterCreate):
    check_admin(admin_id)
    char = await create_character(data.model_dump())
    return {"ok": True, "character": char}


@app.put("/api/admin/characters/{char_id}")
async def admin_update_character(char_id: int, admin_id: int, data: AdminCharacterUpdate):
    check_admin(admin_id)
    existing = await get_character(char_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Персонаж не найден")
    await update_character(char_id, {k: v for k, v in data.model_dump().items() if v is not None})
    updated = await get_character(char_id)
    return {"ok": True, "character": updated}


@app.delete("/api/admin/characters/{char_id}")
async def admin_delete_character(char_id: int, admin_id: int):
    check_admin(admin_id)
    existing = await get_character(char_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Персонаж не найден")
    await delete_character(char_id)
    return {"ok": True}


@app.get("/api/admin/shop")
async def admin_list_shop(admin_id: int):
    check_admin(admin_id)
    items = await get_shop_items(active_only=False)
    return {"ok": True, "items": items}


@app.post("/api/admin/shop")
async def admin_create_shop_item(admin_id: int, data: AdminShopItemCreate):
    check_admin(admin_id)
    VALID_TYPES = {"tap_power", "max_energy", "energy_regen", "passive_income"}
    if data.effect_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Неверный тип эффекта. Допустимы: {VALID_TYPES}")
    item = await create_shop_item(data.model_dump())
    return {"ok": True, "item": item}


@app.put("/api/admin/shop/{item_id}")
async def admin_update_shop_item(item_id: int, admin_id: int, data: AdminShopItemUpdate):
    check_admin(admin_id)
    existing = await get_shop_item(item_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Товар не найден")
    await update_shop_item(item_id, {k: v for k, v in data.model_dump().items() if v is not None})
    updated = await get_shop_item(item_id)
    return {"ok": True, "item": updated}


@app.delete("/api/admin/shop/{item_id}")
async def admin_delete_shop_item(item_id: int, admin_id: int):
    check_admin(admin_id)
    existing = await get_shop_item(item_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Товар не найден")
    await delete_shop_item(item_id)
    return {"ok": True}


@app.post("/api/admin/upload-image")
async def admin_upload_image(
    admin_id: int,
    file: UploadFile = File(...),
):
    check_admin(admin_id)

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Только изображения (jpeg, png, gif, webp)")

    ext_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }
    ext = ext_map.get(file.content_type, ".jpg")
    filename = f"{int(time.time())}_{file.filename or 'image'}"
    filename = "".join(c for c in filename if c.isalnum() or c in "._-")
    if not filename.endswith(ext):
        filename = filename + ext

    save_path = CHARACTERS_UPLOAD_DIR / filename
    content = await file.read()

    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Файл слишком большой (макс. 5MB)")

    save_path.write_bytes(content)
    url = f"/static/assets/characters/{filename}"
    return {"ok": True, "url": url, "filename": filename}


@app.get("/api/admin/users")
async def admin_list_users(admin_id: int, limit: int = 50):
    check_admin(admin_id)
    users = await get_top_users(limit)
    return {"ok": True, "users": users, "count": len(users)}


@app.post("/api/admin/grant")
async def admin_grant(req: AdminGrantRequest):
    check_admin(req.admin_id)
    target = await get_user(req.target_telegram_id)
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    new_balance = target["balance"] + req.amount
    new_earned = target.get("total_earned", 0) + max(0, req.amount)
    await update_user(
        req.target_telegram_id,
        balance=new_balance,
        total_earned=new_earned,
    )
    await add_transaction(target["id"], req.amount, req.reason)
    updated = await get_user(req.target_telegram_id)
    return {
        "ok": True,
        "message": f"Выдано {req.amount:+.0f} монет игроку {req.target_telegram_id}",
        "new_balance": round(updated["balance"], 2),
    }


@app.get("/api/admin/notifications")
async def admin_list_notifications(admin_id: int):
    check_admin(admin_id)
    notes = await get_notifications(100)
    return {"ok": True, "notifications": notes}


@app.post("/api/admin/notifications")
async def admin_create_notification(admin_id: int, data: AdminNotificationCreate):
    check_admin(admin_id)
    note = await create_notification(data.title, data.message)
    return {"ok": True, "notification": note}