# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Group Locks Database Layer
Tracks active media/message locks per chat with in-memory cache for high-speed checks.
"""

from KITTUBOT.database import locks_col
from KITTUBOT import log

# In-memory fast cache: chat_id -> set of active locked types
_LOCKS_CACHE: dict[int, set[str]] = {}

VALID_LOCK_TYPES = {
    "stickers",
    "links",
    "forwards",
    "media",
    "gifs",
    "audio",
    "bots",
    "games",
}


async def get_chat_locks(chat_id: int) -> set[str]:
    """Retrieves all locked types for a chat."""
    if chat_id in _LOCKS_CACHE:
        return _LOCKS_CACHE[chat_id]

    try:
        doc = await locks_col.find_one({"chat_id": chat_id})
        locked_set = set(doc.get("locked", [])) if doc else set()
        _LOCKS_CACHE[chat_id] = locked_set
        return locked_set
    except Exception as e:
        log.error(f"Error fetching locks for chat {chat_id}: {e}")
        return set()


async def set_chat_lock(chat_id: int, lock_type: str, locked: bool) -> bool:
    """Enables or disables a specific lock for a chat."""
    try:
        current_locks = await get_chat_locks(chat_id)
        if locked:
            current_locks.add(lock_type)
        else:
            current_locks.discard(lock_type)

        _LOCKS_CACHE[chat_id] = current_locks

        await locks_col.update_one(
            {"chat_id": chat_id},
            {"$set": {"chat_id": chat_id, "locked": list(current_locks)}},
            upsert=True,
        )
        return True
    except Exception as e:
        log.error(f"Error updating lock {lock_type} for chat {chat_id}: {e}")
        return False
