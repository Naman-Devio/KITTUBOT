# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Async Database Layer (Motor + MongoDB)
Completely non-blocking, asynchronous database engine.
"""

from motor.motor_asyncio import AsyncIOMotorClient
import certifi
from KITTUBOT.config import config
from KITTUBOT import log

if not config.MONGO_URI:
    log.error("MONGO_URI is not set in environment or .env!")

client: AsyncIOMotorClient = AsyncIOMotorClient(
    config.MONGO_URI,
    tlsCAFile=certifi.where() if config.MONGO_URI.startswith("mongodb+srv") else None,
)

db = client[config.DATABASE_NAME]

# Main DB Collections
users_col = db["users"]
chats_col = db["chats"]
sudoers_col = db["sudoers"]
couples_col = db["couples"]
riddles_col = db["riddles"]
inventory_col = db["inventory"]
warns_col = db["warns"]
stats_col = db["bot_stats"]
locks_col = db["chat_locks"]
afk_col = db["afk"]
rankings_col = db["chat_rankings"]
stickers_col = db["stickers_pool"]
automod_col = db["automod_settings"]
user_models_col = db["user_models"]
voice_cache_col = db["voice_cache"]
voice_quota_col = db["voice_quota"]

# Waifu Gacha Collections (from user's real waifu database)
waifu_db = client[config.WAIFU_DB_NAME]
waifu_chars_col = waifu_db["waifu_anime_characters"]
waifu_users_col = waifu_db["waifu_user_collection"]


async def init_db():
    """Create essential unique indexes on startup without crashing."""
    try:
        await users_col.create_index("user_id", unique=True)
        await chats_col.create_index("chat_id", unique=True)
        await couples_col.create_index([("chat_id", 1), ("date", 1)], unique=True)
        await rankings_col.create_index([("chat_id", 1), ("user_id", 1)], unique=True)
        await rankings_col.create_index([("points", -1)])
        await voice_cache_col.create_index("text_hash", unique=True)
        await voice_quota_col.create_index("month", unique=True)
        log.info("MongoDB indexes verified successfully.")
    except Exception as e:
        log.warning(f"Index creation note: {e}")
