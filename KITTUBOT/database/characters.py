# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Characters & Harem Database Layer
Seamlessly connected to the user's real MongoDB waifu database (2,865+ anime characters).
"""

import time
import random
from datetime import datetime
from telegram import User
from KITTUBOT.database import waifu_chars_col, waifu_users_col, users_col
from KITTUBOT import log

# In-memory cache for character count to prevent DB overhead on every spawn
_CACHED_CHAR_COUNT = 0
_LAST_COUNT_CHECK = 0.0


async def get_total_waifu_count() -> int:
    """Returns cached total count of waifus in the database."""
    global _CACHED_CHAR_COUNT, _LAST_COUNT_CHECK
    now = time.time()
    if _CACHED_CHAR_COUNT == 0 or (now - _LAST_COUNT_CHECK) > 300:
        try:
            _CACHED_CHAR_COUNT = await waifu_chars_col.count_documents({})
            _LAST_COUNT_CHECK = now
        except Exception as e:
            log.warning(f"Failed to count waifu documents: {e}")
            if _CACHED_CHAR_COUNT == 0:
                _CACHED_CHAR_COUNT = 2865
    return _CACHED_CHAR_COUNT


async def get_random_character() -> dict | None:
    """Fetches a random character from the 2,865+ character database."""
    try:
        total = await get_total_waifu_count()
        if total > 0:
            rand_idx = random.randint(0, total - 1)
            docs = await waifu_chars_col.find().skip(rand_idx).limit(1).to_list(length=1)
            if docs:
                c = docs[0]
                return {
                    "id": str(c.get("id", c.get("_id", "0"))),
                    "name": c.get("name", "Unknown Character"),
                    "anime": c.get("anime", "Anime Series"),
                    "rarity": c.get("rarity", "⚪ Common"),
                    "img": c.get("img_url", ""),
                }
    except Exception as e:
        log.error(f"Error fetching random waifu from MongoDB: {e}")
    return None


async def get_user_harem(user_id: int) -> dict:
    """Fetches user harem from waifu_user_collection, or creates default."""
    try:
        doc = await waifu_users_col.find_one({"id": user_id})
        if not doc:
            doc = {
                "id": user_id,
                "characters": [],
                "balance": 0,
                "start_time": time.time(),
            }
            await waifu_users_col.insert_one(doc)
        return doc
    except Exception as e:
        log.error(f"Error fetching user harem: {e}")
        return {"id": user_id, "characters": [], "balance": 0}


async def add_character_to_harem(user: User, character: dict) -> bool:
    """Adds a claimed character into the user's permanent harem collection."""
    try:
        user_id = user.id
        now_dt = datetime.utcnow()
        char_entry = {
            "name": character.get("name"),
            "anime": character.get("anime"),
            "rarity": character.get("rarity"),
            "id": str(character.get("id")),
            "img_url": character.get("img"),
            "added_at": now_dt,
            "source": "kittu_bot",
            "timestamp": time.time(),
        }

        # Ensure user exists and append character
        res = await waifu_users_col.find_one({"id": user_id})
        if not res:
            new_user_doc = {
                "id": user_id,
                "username": user.username or "",
                "first_name": user.first_name,
                "last_name": user.last_name or "",
                "start_time": time.time(),
                "characters": [char_entry],
                "balance": 500,
            }
            await waifu_users_col.insert_one(new_user_doc)
        else:
            await waifu_users_col.update_one(
                {"id": user_id},
                {
                    "$push": {"characters": char_entry},
                    "$set": {
                        "first_name": user.first_name,
                        "username": user.username or "",
                    },
                },
            )
        return True
    except Exception as e:
        log.error(f"Error adding waifu to user harem: {e}")
        return False


async def set_favorite_character(user_id: int, char_id: str) -> dict | None:
    """Sets a character as the user's favorite."""
    try:
        doc = await waifu_users_col.find_one({"id": user_id})
        if not doc:
            return None
        characters = doc.get("characters", [])
        char_id_str = str(char_id).lower()
        target = next(
            (c for c in characters if str(c.get("id", "")).lower() == char_id_str or char_id_str in c.get("name", "").lower()),
            None
        )
        if not target:
            return None

        await waifu_users_col.update_one(
            {"id": user_id},
            {"$set": {"favorite_character": target}},
        )
        return target
    except Exception as e:
        log.error(f"Error setting favorite waifu: {e}")
        return None


async def transfer_character(sender_id: int, receiver_user: User, char_id: str) -> tuple[bool, str]:
    """Transfers a character from sender to receiver in waifu_users_col."""
    try:
        sender_doc = await waifu_users_col.find_one({"id": sender_id})
        if not sender_doc:
            return False, "You do not own any characters yet!"

        chars = sender_doc.get("characters", [])
        char_id_str = str(char_id).lower()
        target_idx = next(
            (idx for idx, c in enumerate(chars) if str(c.get("id", "")).lower() == char_id_str),
            None
        )
        if target_idx is None:
            return False, f"Character ID '{char_id}' not found in your harem!"

        target_char = chars.pop(target_idx)

        # Update sender
        await waifu_users_col.update_one(
            {"id": sender_id},
            {"$set": {"characters": chars}},
        )

        # Add to receiver
        await add_character_to_harem(receiver_user, target_char)
        return True, f"Successfully gifted {target_char.get('name')} to {receiver_user.first_name}!"
    except Exception as e:
        log.error(f"Error transferring character: {e}")
        return False, "Transfer failed due to a database error."


async def get_top_collectors(limit: int = 10) -> list[dict]:
    """Fetches top collectors ranked by collection size."""
    try:
        cursor = waifu_users_col.find(
            {"characters.0": {"$exists": True}},
            {"id": 1, "first_name": 1, "username": 1, "characters": 1, "favorite_character": 1}
        ).limit(100)
        docs = await cursor.to_list(length=100)
        docs.sort(key=lambda d: len(d.get("characters", [])), reverse=True)
        top = []
        for d in docs[:limit]:
            top.append({
                "user_id": d.get("id"),
                "first_name": d.get("first_name", "Collector"),
                "username": d.get("username", ""),
                "total_count": len(d.get("characters", [])),
                "favorite": d.get("favorite_character"),
            })
        return top
    except Exception as e:
        log.error(f"Error fetching top collectors: {e}")
        return []
