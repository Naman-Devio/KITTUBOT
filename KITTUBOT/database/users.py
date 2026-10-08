# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT User & Economy Database Functions
"""

import time
from telegram import User
from KITTUBOT.database import users_col
from KITTUBOT.config import config


async def ensure_user(user: User) -> dict:
    """Ensure user exists in DB; return latest record atomically."""
    user_data = await users_col.find_one({"user_id": user.id})
    if not user_data:
        default_record = {
            "user_id": user.id,
            "first_name": user.first_name,
            "username": user.username or "",
            "balance": config.REGISTER_BONUS,
            "bank": 0,
            "kills": 0,
            "deaths": 0,
            "bomb_wins": 0,
            "is_dead": False,
            "death_time": 0,
            "protection_until": 0,
            "last_daily": 0,
            "spouse_id": 0,
            "inventory": [],
            "created_at": time.time(),
        }
        await users_col.insert_one(default_record)
        return default_record

    # Update basic profile metadata
    if user.first_name != user_data.get("first_name") or (user.username or "") != user_data.get("username"):
        await users_col.update_one(
            {"user_id": user.id},
            {"$set": {"first_name": user.first_name, "username": user.username or ""}},
        )
    return user_data


async def get_user(user_id: int) -> dict | None:
    return await users_col.find_one({"user_id": user_id})


async def update_balance(user_id: int, amount: int) -> int:
    """Adjusts wallet balance (positive or negative) and returns new balance."""
    res = await users_col.find_one_and_update(
        {"user_id": user_id},
        {"$inc": {"balance": amount}},
        return_document=True,
    )
    return res["balance"] if res else 0


async def deposit_to_bank(user_id: int, amount: int) -> bool:
    """Transfers coins atomically from wallet into bank."""
    user = await get_user(user_id)
    if not user or user.get("balance", 0) < amount:
        return False
    await users_col.update_one(
        {"user_id": user_id},
        {"$inc": {"balance": -amount, "bank": amount}},
    )
    return True


async def withdraw_from_bank(user_id: int, amount: int) -> bool:
    """Transfers coins atomically from bank into wallet."""
    user = await get_user(user_id)
    if not user or user.get("bank", 0) < amount:
        return False
    await users_col.update_one(
        {"user_id": user_id},
        {"$inc": {"balance": amount, "bank": -amount}},
    )
    return True


async def set_user_dead(user_id: int, is_dead: bool = True):
    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"is_dead": is_dead, "death_time": int(time.time()) if is_dead else 0}},
    )


async def check_auto_revive(user: dict) -> bool:
    """If user died more than AUTO_REVIVE_HOURS ago, revive automatically."""
    if not user.get("is_dead"):
        return False
    death_time = user.get("death_time", 0)
    if time.time() - death_time > (config.AUTO_REVIVE_HOURS * 3600):
        await set_user_dead(user["user_id"], False)
        return True
    return False


async def is_protected(user_id: int) -> bool:
    user = await get_user(user_id)
    if not user:
        return False
    protect_until = user.get("protection_until", 0)
    return protect_until > time.time()


async def set_protection(user_id: int, seconds: int):
    until = time.time() + seconds
    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"protection_until": until}},
    )


async def get_top_rich(limit: int = 10) -> list[dict]:
    cursor = users_col.find({}).sort("balance", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def get_top_killers(limit: int = 10) -> list[dict]:
    cursor = users_col.find({}).sort("kills", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def record_bomb_win(user_id: int, pot_amount: int):
    await users_col.update_one(
        {"user_id": user_id},
        {"$inc": {"balance": pot_amount, "bomb_wins": 1}},
    )


async def get_top_bomb_winners(limit: int = 10) -> list[dict]:
    cursor = users_col.find({"bomb_wins": {"$gt": 0}}).sort("bomb_wins", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def get_user_bomb_rank(user_id: int) -> tuple[int, int]:
    """Returns (rank, total_wins)."""
    user = await get_user(user_id)
    if not user:
        return 0, 0
    wins = user.get("bomb_wins", 0)
    higher_count = await users_col.count_documents({"bomb_wins": {"$gt": wins}})
    return higher_count + 1, wins
