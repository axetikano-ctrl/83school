"""
database.py — SQLite/Turso database initialization and CRUD helpers
Стиль: 83 SCHOOL. Добавлено: таблица notifications.
"""
import aiosqlite
import time
from typing import Optional
from config import (
    DATABASE_PATH,
    TURSO_DATABASE_URL,
    TURSO_AUTH_TOKEN,
    BASE_MAX_ENERGY,
    BASE_TAP_POWER,
    BASE_ENERGY_REGEN,
    BASE_PASSIVE_INCOME,
    DEFAULT_CHARACTERS,
    DEFAULT_SHOP_ITEMS,
)

USE_TURSO = bool(TURSO_DATABASE_URL)

if USE_TURSO:
    from libsql_experimental import create_client

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER UNIQUE NOT NULL,
    username      TEXT,
    first_name    TEXT,
    balance       REAL    DEFAULT 0,
    tap_power     INTEGER DEFAULT 1,
    energy        REAL    DEFAULT 1000,
    max_energy    INTEGER DEFAULT 1000,
    energy_regen  REAL    DEFAULT 1.0,
    passive_income INTEGER DEFAULT 0,
    last_seen     REAL    DEFAULT 0,
    daily_claimed REAL    DEFAULT 0,
    referrer_id   INTEGER DEFAULT NULL,
    level         INTEGER DEFAULT 1,
    total_taps    INTEGER DEFAULT 0,
    total_earned  REAL    DEFAULT 0,
    created_at    REAL    DEFAULT 0
);
"""

CREATE_USER_UPGRADES = """
CREATE TABLE IF NOT EXISTS upgrades (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    type       TEXT    NOT NULL,
    level      INTEGER DEFAULT 0,
    created_at REAL    DEFAULT 0,
    UNIQUE(user_id, type),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""

CREATE_REFERRALS = """
CREATE TABLE IF NOT EXISTS referrals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    inviter_id    INTEGER NOT NULL,
    invited_id    INTEGER NOT NULL UNIQUE,
    reward_claimed INTEGER DEFAULT 0,
    created_at    REAL    DEFAULT 0,
    FOREIGN KEY (inviter_id) REFERENCES users(id),
    FOREIGN KEY (invited_id) REFERENCES users(id)
);
"""

CREATE_TRANSACTIONS = """
CREATE TABLE IF NOT EXISTS transactions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    amount     REAL    NOT NULL,
    reason     TEXT,
    created_at REAL    DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""

CREATE_CHARACTERS = """
CREATE TABLE IF NOT EXISTS characters (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    description     TEXT    DEFAULT '',
    base_tap_power  INTEGER DEFAULT 1,
    base_energy     INTEGER DEFAULT 1000,
    base_passive    INTEGER DEFAULT 0,
    color           TEXT    DEFAULT '#e0e0e0',
    emoji           TEXT    DEFAULT '👤',
    image           TEXT    DEFAULT '',
    active          INTEGER DEFAULT 1,
    sort_order      INTEGER DEFAULT 0,
    created_at      REAL    DEFAULT 0
);
"""

CREATE_SHOP_ITEMS = """
CREATE TABLE IF NOT EXISTS shop_items (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT    NOT NULL,
    description      TEXT    DEFAULT '',
    icon             TEXT    DEFAULT '⬆️',
    effect_type      TEXT    NOT NULL,
    effect_value     REAL    DEFAULT 1,
    base_price       INTEGER NOT NULL,
    price_multiplier REAL    DEFAULT 3.0,
    max_level        INTEGER DEFAULT 7,
    active           INTEGER DEFAULT 1,
    sort_order       INTEGER DEFAULT 0,
    created_at       REAL    DEFAULT 0
);
"""

CREATE_USER_SHOP_LEVELS = """
CREATE TABLE IF NOT EXISTS user_shop_levels (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    item_id     INTEGER NOT NULL,
    level       INTEGER DEFAULT 0,
    created_at  REAL    DEFAULT 0,
    UNIQUE(user_id, item_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (item_id) REFERENCES shop_items(id)
);
"""

CREATE_NOTIFICATIONS = """
CREATE TABLE IF NOT EXISTS notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    message    TEXT NOT NULL,
    created_at REAL DEFAULT 0
);
"""

# ---------------------------------------------------------------------------
# Universal query executor (SQLite / Turso)
# ---------------------------------------------------------------------------

async def execute_query(query, params=None, fetch_one=False, fetch_all=False):
    if USE_TURSO:
        client = create_client(TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)
        result = await client.execute(query, list(params) if params else [])
        if fetch_one:
            if not result.rows:
                return None
            return dict(zip(result.columns, result.rows[0]))
        if fetch_all:
            return [dict(zip(result.columns, r)) for r in result.rows]
        return None
    else:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params or ()) as cur:
                if fetch_one:
                    row = await cur.fetchone()
                    return dict(row) if row else None
                if fetch_all:
                    return [dict(r) for r in await cur.fetchall()]
                await db.commit()
                return None

# ---------------------------------------------------------------------------
# Init & Seed
# ---------------------------------------------------------------------------

async def init_db():
    for q in (CREATE_USERS, CREATE_USER_UPGRADES, CREATE_REFERRALS,
              CREATE_TRANSACTIONS, CREATE_CHARACTERS, CREATE_SHOP_ITEMS,
              CREATE_USER_SHOP_LEVELS, CREATE_NOTIFICATIONS):
        await execute_query(q)
    try:
        await execute_query("ALTER TABLE users ADD COLUMN total_earned REAL DEFAULT 0")
    except Exception:
        pass
    await seed_characters()
    await seed_shop_items()


async def seed_characters():
    r = await execute_query("SELECT COUNT(*) AS c FROM characters", fetch_one=True)
    if r and r["c"] == 0:
        now = time.time()
        for i, ch in enumerate(DEFAULT_CHARACTERS):
            await execute_query(
                """INSERT INTO characters
                (name, description, base_tap_power, base_energy, base_passive,
                 color, emoji, image, active, sort_order, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                [ch["name"], ch["description"], ch["base_tap_power"],
                 ch["base_energy"], ch["base_passive"], ch["color"],
                 ch["emoji"], ch.get("image", ""), i, now],
            )


async def seed_shop_items():
    r = await execute_query("SELECT COUNT(*) AS c FROM shop_items", fetch_one=True)
    if r and r["c"] == 0:
        now = time.time()
        for i, item in enumerate(DEFAULT_SHOP_ITEMS):
            await execute_query(
                """INSERT INTO shop_items
                (name, description, icon, effect_type, effect_value,
                 base_price, price_multiplier, max_level, active, sort_order, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                [item["name"], item["description"], item["icon"],
                 item["effect_type"], item["effect_value"],
                 item["base_price"], item["price_multiplier"],
                 item["max_level"], i, now],
            )

# ---------------------------------------------------------------------------
# Characters
# ---------------------------------------------------------------------------

async def get_characters(active_only: bool = True) -> list:
    q = "SELECT * FROM characters"
    if active_only:
        q += " WHERE active = 1"
    q += " ORDER BY sort_order ASC, id ASC"
    return await execute_query(q, fetch_all=True) or []


async def get_character(char_id: int) -> Optional[dict]:
    return await execute_query("SELECT * FROM characters WHERE id = ?", [char_id], fetch_one=True)


async def create_character(data: dict) -> dict:
    now = time.time()
    await execute_query(
        """INSERT INTO characters
        (name, description, base_tap_power, base_energy, base_passive,
         color, emoji, image, active, sort_order, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
        [data["name"], data.get("description", ""),
         data.get("base_tap_power", 1), data.get("base_energy", 1000),
         data.get("base_passive", 0), data.get("color", "#e0e0e0"),
         data.get("emoji", "👤"), data.get("image", ""),
         data.get("sort_order", 0), now],
    )
    return await execute_query("SELECT * FROM characters ORDER BY id DESC LIMIT 1", fetch_one=True)


async def update_character(char_id: int, data: dict):
    fields = {k: v for k, v in data.items()
              if k in ("name", "description", "base_tap_power", "base_energy",
                       "base_passive", "color", "emoji", "image", "active", "sort_order")}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    await execute_query(f"UPDATE characters SET {set_clause} WHERE id = ?",
                        list(fields.values()) + [char_id])


async def delete_character(char_id: int):
    await execute_query("DELETE FROM characters WHERE id = ?", [char_id])

# ---------------------------------------------------------------------------
# Shop Items
# ---------------------------------------------------------------------------

async def get_shop_items(active_only: bool = True) -> list:
    q = "SELECT * FROM shop_items"
    if active_only:
        q += " WHERE active = 1"
    q += " ORDER BY sort_order ASC, id ASC"
    return await execute_query(q, fetch_all=True) or []


async def get_shop_item(item_id: int) -> Optional[dict]:
    return await execute_query("SELECT * FROM shop_items WHERE id = ?", [item_id], fetch_one=True)


async def create_shop_item(data: dict) -> dict:
    now = time.time()
    await execute_query(
        """INSERT INTO shop_items
        (name, description, icon, effect_type, effect_value,
         base_price, price_multiplier, max_level, active, sort_order, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
        [data["name"], data.get("description", ""), data.get("icon", "⬆️"),
         data["effect_type"], data.get("effect_value", 1),
         data["base_price"], data.get("price_multiplier", 3.0),
         data.get("max_level", 7), data.get("sort_order", 0), now],
    )
    return await execute_query("SELECT * FROM shop_items ORDER BY id DESC LIMIT 1", fetch_one=True)


async def update_shop_item(item_id: int, data: dict):
    fields = {k: v for k, v in data.items()
              if k in ("name", "description", "icon", "effect_type", "effect_value",
                       "base_price", "price_multiplier", "max_level", "active", "sort_order")}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    await execute_query(f"UPDATE shop_items SET {set_clause} WHERE id = ?",
                        list(fields.values()) + [item_id])


async def delete_shop_item(item_id: int):
    await execute_query("DELETE FROM shop_items WHERE id = ?", [item_id])

# ---------------------------------------------------------------------------
# User Shop Levels
# ---------------------------------------------------------------------------

def compute_item_price(base_price: int, multiplier: float, current_level: int) -> int:
    return int(base_price * (multiplier ** current_level))


async def get_user_shop_levels(user_id: int) -> dict:
    rows = await execute_query(
        "SELECT item_id, level FROM user_shop_levels WHERE user_id = ?", [user_id], fetch_all=True)
    return {r["item_id"]: r["level"] for r in (rows or [])}


async def set_user_shop_level(user_id: int, item_id: int, level: int):
    now = time.time()
    await execute_query(
        """INSERT INTO user_shop_levels (user_id, item_id, level, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, item_id) DO UPDATE SET level = ?, created_at = ?""",
        [user_id, item_id, level, now, level, now],
    )

# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

async def get_user(telegram_id: int) -> Optional[dict]:
    return await execute_query("SELECT * FROM users WHERE telegram_id = ?", [telegram_id], fetch_one=True)


async def create_user(telegram_id: int, username: Optional[str] = None,
                      first_name: Optional[str] = None,
                      referrer_id: Optional[int] = None) -> dict:
    now = time.time()
    await execute_query(
        """INSERT OR IGNORE INTO users
        (telegram_id, username, first_name, balance, tap_power, energy,
         max_energy, energy_regen, passive_income, last_seen, daily_claimed,
         referrer_id, level, total_taps, total_earned, created_at)
        VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?, ?, 0, ?, 1, 0, 0, ?)""",
        [telegram_id, username, first_name, BASE_TAP_POWER,
         float(BASE_MAX_ENERGY), BASE_MAX_ENERGY, BASE_ENERGY_REGEN,
         BASE_PASSIVE_INCOME, now, referrer_id, now],
    )
    return await get_user(telegram_id)


async def update_user(telegram_id: int, **fields):
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    await execute_query(f"UPDATE users SET {set_clause} WHERE telegram_id = ?",
                        list(fields.values()) + [telegram_id])


async def apply_passive_income(user: dict) -> dict:
    now = time.time()
    elapsed = now - user["last_seen"]
    if elapsed <= 0 or user["passive_income"] <= 0:
        return user
    earned = (elapsed / 3600.0) * user["passive_income"]
    earned = min(earned, 8 * user["passive_income"])
    if earned > 0:
        new_balance = user["balance"] + earned
        new_earned = user.get("total_earned", 0) + earned
        await update_user(user["telegram_id"], balance=new_balance,
                          last_seen=now, total_earned=new_earned)
        await add_transaction(user["id"], earned, "passive_income")
        user["balance"] = new_balance
    return user


async def apply_energy_regen(user: dict) -> dict:
    now = time.time()
    elapsed = now - user["last_seen"]
    if elapsed <= 0:
        return user
    regen = elapsed * user["energy_regen"]
    new_energy = min(user["energy"] + regen, user["max_energy"])
    await update_user(user["telegram_id"], energy=new_energy, last_seen=now)
    user["energy"] = new_energy
    user["last_seen"] = now
    return user


async def get_top_users(limit: int = 50) -> list:
    return await execute_query(
        """SELECT telegram_id, username, first_name, balance,
                  total_taps, level, total_earned, created_at
        FROM users ORDER BY total_earned DESC LIMIT ?""",
        [limit], fetch_all=True) or []

# ---------------------------------------------------------------------------
# Legacy upgrades
# ---------------------------------------------------------------------------

async def get_user_upgrades(user_id: int) -> dict:
    rows = await execute_query("SELECT type, level FROM upgrades WHERE user_id = ?", [user_id], fetch_all=True)
    return {r["type"]: r["level"] for r in (rows or [])}


async def set_upgrade_level(user_id: int, upg_type: str, level: int):
    now = time.time()
    await execute_query(
        """INSERT INTO upgrades (user_id, type, level, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, type) DO UPDATE SET level = ?, created_at = ?""",
        [user_id, upg_type, level, now, level, now],
    )

# ---------------------------------------------------------------------------
# Referrals
# ---------------------------------------------------------------------------

async def get_referrals(inviter_telegram_id: int) -> list:
    return await execute_query(
        """SELECT u.telegram_id, u.username, u.first_name, u.created_at,
                r.reward_claimed, r.created_at AS ref_at
        FROM referrals r
        JOIN users u ON u.id = r.invited_id
        WHERE r.inviter_id = (SELECT id FROM users WHERE telegram_id = ?)
        ORDER BY r.created_at DESC""",
        [inviter_telegram_id], fetch_all=True) or []


async def create_referral(inviter_id: int, invited_id: int):
    now = time.time()
    await execute_query(
        """INSERT OR IGNORE INTO referrals (inviter_id, invited_id, reward_claimed, created_at)
        VALUES (?, ?, 0, ?)""",
        [inviter_id, invited_id, now],
    )


async def mark_referral_reward(invited_id: int):
    await execute_query("UPDATE referrals SET reward_claimed = 1 WHERE invited_id = ?", [invited_id])

# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

async def add_transaction(user_id: int, amount: float, reason: str):
    now = time.time()
    await execute_query(
        "INSERT INTO transactions (user_id, amount, reason, created_at) VALUES (?, ?, ?, ?)",
        [user_id, amount, reason, now],
    )

# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

async def get_notifications(limit: int = 50) -> list:
    return await execute_query(
        "SELECT * FROM notifications ORDER BY created_at DESC, id DESC LIMIT ?",
        [limit], fetch_all=True) or []


async def create_notification(title: str, message: str) -> dict:
    now = time.time()
    await execute_query(
        "INSERT INTO notifications (title, message, created_at) VALUES (?, ?, ?)",
        [title, message, now],
    )
    return await execute_query("SELECT * FROM notifications ORDER BY id DESC LIMIT 1", fetch_one=True)
