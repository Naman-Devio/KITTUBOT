# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Configuration Module
Centralized, validated settings loaded cleanly from environment variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _get_int(key: str, default: int = 0) -> int:
    val = os.getenv(key, "").strip()
    return int(val) if val.lstrip("-").isdigit() else default


def _get_list(key: str, default: list | None = None) -> list[str]:
    raw = os.getenv(key, "")
    if not raw:
        return default or []
    return [item.strip() for item in raw.split(",") if item.strip()]


class Config:
    # Telegram Bot Core
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
    BOT_NAME: str = os.getenv("BOT_NAME", "Kittu").strip()
    BOT_USERNAME: str = os.getenv("BOT_USERNAME", "KittuBot").strip()

    # Database
    MONGO_URI: str = os.getenv("MONGO_URI", "").strip()
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "kittubot_db").strip()
    WAIFU_DB_NAME: str = os.getenv("WAIFU_DB_NAME", "grabwaifu").strip()

    # Permissions & Privileges
    OWNER_ID: int = _get_int("OWNER_ID", 0)
    LOGGER_ID: int = _get_int("LOGGER_ID", 0)
    OWNER_LINK: str = os.getenv("OWNER_LINK", "https://t.me/eceqt").strip()

    SUDO_IDS: list[int] = [
        int(x)
        for x in os.getenv("SUDO_IDS", "").split(",")
        if x.strip().lstrip("-").isdigit()
    ]
    if OWNER_ID and OWNER_ID not in SUDO_IDS:
        SUDO_IDS.append(OWNER_ID)

    # Visual / Animation Assets
    START_STICKER_FILE_ID: str = os.getenv(
        "START_STICKER_FILE_ID",
        "CAACAgUAAyEFAAS-Y9n1AAJio2lnx-7YpGWYAAGKW3ILDhBG7Gl0qgACoxsAAnmZoFUj0zVj_zPVix4E",
    ).strip()

    START_IMG_URL: list[str] = [
        "https://files.catbox.moe/04yc10.mp4",
        "https://telegra.ph/file/9b7e1b820c72a14d90be7.mp4",
        "https://telegra.ph/file/a4d90b0cb759b67d68644.mp4",
    ]

    HELP_IMG_URL: str = os.getenv(
        "HELP_IMG_URL", "https://files.catbox.moe/7m98k1.mp4"
    ).strip()

    MESSAGE_EFFECT_ID: int = _get_int("MESSAGE_EFFECT_ID", 5046509860389126442)

    # Links
    SUPPORT_CHAT_LINK: str = os.getenv(
        "SUPPORT_CHAT_LINK", "https://t.me/+cWCtXiDOgIxlZWQ1"
    ).strip()
    SUPPORT_CHANNEL_LINK: str = os.getenv(
        "SUPPORT_CHANNEL_LINK", "https://t.me/echowavesupport"
    ).strip()

    # AI API Keys
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
    MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "").strip()

    # YouTube Yuki Stream API
    YUKI_API_KEY: str = os.getenv("YUKI_API_KEY", "yuki_7c008e025c4bb3d3f5a958e6b1b0c0c6").strip()
    YUKI_STREAM_GATEWAYS: list[str] = [
        "https://play.yukiapi.site/stream/{video_id}?key={key}",
        "https://music.yukiapi.site/stream/{video_id}?key={key}",
    ]
    NVIDIA_API_KEY: str = os.getenv("NVIDIA_API_KEY", "").strip()
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "").strip()

    # Economy Engine Parameters
    REGISTER_BONUS: int = 500
    DAILY_BONUS: int = 1500
    BONUS_COOLDOWN_HOURS: int = 12
    REVIVE_COST: int = 200
    DIVORCE_COST: int = 2000
    PROPOSE_COST: int = 5000
    TAX_RATE: float = 0.10
    RIDDLE_REWARD: int = 1000

    # Game Limits & Cooldowns
    KILL_LIMIT_DAILY: int = 100
    ROB_LIMIT_DAILY: int = 200
    ROB_MAX_AMOUNT: int = 500_000
    KILL_COOLDOWN_SECONDS: int = 3
    PROTECT_1D_COST: int = 2500
    PROTECT_2D_COST: int = 6000
    AUTO_REVIVE_HOURS: int = 5

    # Shop Items & Buffs
    SHOP_ITEMS: list[dict] = [
        {"id": "stick", "name": "🪵 Wooden Stick", "price": 500, "type": "weapon", "buff": 0.02},
        {"id": "knife", "name": "🔪 Hunting Knife", "price": 3500, "type": "weapon", "buff": 0.06},
        {"id": "pistol", "name": "🔫 Desert Eagle", "price": 25000, "type": "weapon", "buff": 0.20},
        {"id": "ak47", "name": "⚡ AK-47 Dragon", "price": 100000, "type": "weapon", "buff": 0.40},
        {"id": "rpg", "name": "🚀 RPG Bazooka", "price": 300000, "type": "weapon", "buff": 0.55},
        {"id": "deathnote", "name": "📓 Death Note", "price": 5000000, "type": "weapon", "buff": 0.70},
        {"id": "cloth", "name": "🥋 Martial Gi", "price": 2500, "type": "armor", "buff": 0.05},
        {"id": "riot", "name": "🛡️ Riot Shield", "price": 40000, "type": "armor", "buff": 0.18},
        {"id": "iron", "name": "🦾 Cyber Armor", "price": 100000, "type": "armor", "buff": 0.30},
        {"id": "vibranium", "name": "🔮 Vibranium Suit", "price": 1500000, "type": "armor", "buff": 0.50},
        {"id": "plot", "name": "✨ Kittu Plot Armor", "price": 10000000, "type": "armor", "buff": 0.65},
    ]


config = Config()
