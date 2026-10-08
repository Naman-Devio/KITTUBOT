# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT AFK Database Layer
Tracks AFK status, reason, and away timestamps for users.
"""

import time
from KITTUBOT.database import afk_col
from KITTUBOT import log


async def set_user_afk(user_id: int, reason: str = "Busy right now") -> bool:
    """Sets a user's AFK state in MongoDB."""
    try:
        await afk_col.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "user_id": user_id,
                    "reason": reason,
                    "afk_time": time.time(),
                }
            },
            upsert=True,
        )
        return True
    except Exception as e:
        log.error(f"Error setting AFK for {user_id}: {e}")
        return False


async def get_user_afk(user_id: int) -> dict | None:
    """Gets AFK data if user is currently away."""
    try:
        return await afk_col.find_one({"user_id": user_id})
    except Exception as e:
        log.error(f"Error getting AFK for {user_id}: {e}")
        return None


async def remove_user_afk(user_id: int) -> dict | None:
    """Removes user from AFK and returns their previous AFK doc."""
    try:
        doc = await afk_col.find_one({"user_id": user_id})
        if doc:
            await afk_col.delete_one({"user_id": user_id})
        return doc
    except Exception as e:
        log.error(f"Error removing AFK for {user_id}: {e}")
        return None
