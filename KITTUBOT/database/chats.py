# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Group & Chat Database Functions
"""

import time
from telegram import Chat
from KITTUBOT.database import chats_col


async def ensure_chat(chat: Chat) -> dict:
    chat_data = await chats_col.find_one({"chat_id": chat.id})
    if not chat_data:
        record = {
            "chat_id": chat.id,
            "title": chat.title or "",
            "type": chat.type,
            "antiflood": False,
            "welcome": True,
            "locks": {},
            "created_at": time.time(),
        }
        await chats_col.insert_one(record)
        return record
    return chat_data


async def get_chat(chat_id: int) -> dict | None:
    return await chats_col.find_one({"chat_id": chat_id})


async def set_chat_setting(chat_id: int, key: str, value):
    await chats_col.update_one({"chat_id": chat_id}, {"$set": {key: value}}, upsert=True)


async def track_chat_member(chat_id: int, user) -> None:
    """Tracks active members in the chat for /tagall and group mentions."""
    if not user or user.is_bot:
        return
    try:
        user_info = {
            "id": user.id,
            "name": user.first_name,
            "username": user.username or "",
            "last_seen": time.time(),
        }
        # Pull existing record with this id, then push the updated one, keeping max 150 members
        await chats_col.update_one(
            {"chat_id": chat_id},
            {
                "$pull": {"active_members": {"id": user.id}},
            },
            upsert=True,
        )
        await chats_col.update_one(
            {"chat_id": chat_id},
            {
                "$push": {
                    "active_members": {
                        "$each": [user_info],
                        "$slice": -150,  # Keep up to 150 active members
                    }
                }
            },
        )
    except Exception:
        pass


async def get_chat_active_members(chat_id: int) -> list[dict]:
    """Retrieves active tracked members for this chat."""
    try:
        doc = await chats_col.find_one({"chat_id": chat_id})
        if doc and "active_members" in doc:
            return doc["active_members"]
    except Exception:
        pass
    return []
