# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
KITTUBOT Stickers Pool Database Engine
Collects and serves authentic Telegram stickers for conversational bot reactions.
"""

import random
import time
from KITTUBOT.database import stickers_col
from KITTUBOT import log

# In-memory sticker cache for zero-latency retrieval
_STICKER_CACHE: list[str] = []
_STICKER_CACHE_LOADED = False
MAX_STICKER_POOL = 300


async def _ensure_cache_loaded():
    global _STICKER_CACHE, _STICKER_CACHE_LOADED
    if _STICKER_CACHE_LOADED:
        return
    try:
        cursor = stickers_col.find({}, {"file_id": 1}).sort("added_at", -1).limit(MAX_STICKER_POOL)
        items = await cursor.to_list(length=MAX_STICKER_POOL)
        _STICKER_CACHE = [item["file_id"] for item in items if "file_id" in item]
        _STICKER_CACHE_LOADED = True
        log.info(f"[StickersPool] Loaded {len(_STICKER_CACHE)} stickers into memory pool.")
    except Exception as e:
        log.warning(f"[StickersPool] Failed to load sticker cache: {e}")


async def add_sticker(
    file_id: str,
    file_unique_id: str,
    emoji: str = "",
    added_by: int = 0,
    chat_id: int = 0,
) -> bool:
    """Saves a sticker to the pool if it does not already exist."""
    global _STICKER_CACHE
    if not file_id or not file_unique_id:
        return False

    await _ensure_cache_loaded()

    if file_id in _STICKER_CACHE:
        return False

    try:
        exists = await stickers_col.find_one({"file_unique_id": file_unique_id})
        if exists:
            return False

        doc = {
            "file_id": file_id,
            "file_unique_id": file_unique_id,
            "emoji": emoji,
            "added_by": added_by,
            "chat_id": chat_id,
            "added_at": int(time.time()),
        }
        await stickers_col.insert_one(doc)

        _STICKER_CACHE.append(file_id)
        if len(_STICKER_CACHE) > MAX_STICKER_POOL:
            _STICKER_CACHE.pop(0)

        return True
    except Exception as e:
        log.warning(f"[StickersPool] Error saving sticker: {e}")
        return False


async def get_random_sticker() -> str | None:
    """Returns a random sticker file_id from the cache."""
    await _ensure_cache_loaded()
    if not _STICKER_CACHE:
        return None
    return random.choice(_STICKER_CACHE)


async def get_sticker_count() -> int:
    """Returns the total number of stickers in the pool."""
    await _ensure_cache_loaded()
    return len(_STICKER_CACHE)
