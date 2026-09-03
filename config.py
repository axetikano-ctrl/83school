"""
config.py — Configuration loaded from .env
"""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
WEBAPP_URL: str = os.getenv("WEBAPP_URL", "http://localhost:8000")
API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000")
SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))

# Admin access: set your Telegram user ID here
_admin_raw = os.getenv("ADMIN_TELEGRAM_ID", "")
ADMIN_TELEGRAM_ID: int | None = int(_admin_raw) if _admin_raw.strip().isdigit() else None
TURSO_DATABASE_URL: str = os.getenv("TURSO_DATABASE_URL", "")
TURSO_AUTH_TOKEN: str = os.getenv("TURSO_AUTH_TOKEN", "")

DATABASE_PATH: str = "antigravity.db"

# Game balance constants
DAILY_BONUS_AMOUNT: int = 500
REFERRAL_BONUS_INVITER: int = 1000
REFERRAL_BONUS_INVITED: int = 500

# Anti-cheat: max taps per sync window (15 seconds)
MAX_TAPS_PER_WINDOW: int = 150  # ~10 taps/sec * 15 sec
SYNC_WINDOW_SECONDS: int = 15

# Energy regen: base = 1 energy per second
BASE_ENERGY_REGEN: float = 1.0
BASE_MAX_ENERGY: int = 1000
BASE_TAP_POWER: int = 1
BASE_PASSIVE_INCOME: int = 0  # per hour

# Default characters — imported into DB on first run
DEFAULT_CHARACTERS = [
    {
        "name": "Новобранец",
        "description": "Начинающий боец. Скромная сила, но с огромным потенциалом.",
        "base_tap_power": 1,
        "base_energy": 1000,
        "base_passive": 0,
        "color": "#00d4ff",
        "emoji": "👾",
        "image": "",
    },
    {
        "name": "Гравитон",
        "description": "Освоил базовые техники антигравитации. Удар заметно сильнее.",
        "base_tap_power": 3,
        "base_energy": 1500,
        "base_passive": 100,
        "color": "#7b2fff",
        "emoji": "⚡",
        "image": "",
    },
    {
        "name": "Левитатор",
        "description": "Парит над землёй. Энергия течёт свободно.",
        "base_tap_power": 6,
        "base_energy": 2000,
        "base_passive": 300,
        "color": "#00ff88",
        "emoji": "🌀",
        "image": "",
    },
    {
        "name": "Нейтрализатор",
        "description": "Нейтрализует гравитацию вокруг себя. Серьёзная угроза.",
        "base_tap_power": 12,
        "base_energy": 3000,
        "base_passive": 800,
        "color": "#ff6b35",
        "emoji": "🔥",
        "image": "",
    },
    {
        "name": "Космический воин",
        "description": "Страж антигравитационного пространства. Легенда 83 SCHOOL.",
        "base_tap_power": 25,
        "base_energy": 5000,
        "base_passive": 2000,
        "color": "#ffd700",
        "emoji": "🌟",
        "image": "",
    },
]

# Default shop items — imported into DB on first run
DEFAULT_SHOP_ITEMS = [
    {
        "name": "Сила тапа",
        "description": "Увеличивает монеты за клик",
        "icon": "💥",
        "effect_type": "tap_power",
        "effect_value": 1,
        "base_price": 500,
        "price_multiplier": 3.0,
        "max_level": 7,
    },
    {
        "name": "Макс. энергия",
        "description": "Увеличивает максимальный запас энергии",
        "icon": "⚡",
        "effect_type": "max_energy",
        "effect_value": 250,
        "base_price": 300,
        "price_multiplier": 3.5,
        "max_level": 6,
    },
    {
        "name": "Скорость энергии",
        "description": "Ускоряет восстановление энергии",
        "icon": "🔄",
        "effect_type": "energy_regen",
        "effect_value": 1,
        "base_price": 400,
        "price_multiplier": 3.0,
        "max_level": 6,
    },
    {
        "name": "Пассивный доход",
        "description": "Монеты начисляются автоматически в час",
        "icon": "🌌",
        "effect_type": "passive_income",
        "effect_value": 100,
        "base_price": 800,
        "price_multiplier": 3.2,
        "max_level": 7,
    },
]
