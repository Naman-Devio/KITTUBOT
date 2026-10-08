# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Chat Ranking, Activity & Leaderboard Database Layer
Pure async motor implementation with high-performance compound indexing.
"""

import time
from telegram import User
from KITTUBOT.database import rankings_col
from KITTUBOT.database.users import ensure_user, update_balance


async def record_chat_activity(chat_id: int, user: User, points_earned: int = 1):
    """Logs member message activity and awards activity points."""
    if not user or user.is_bot:
        return

    try:
        await rankings_col.update_one(
            {"chat_id": chat_id, "user_id": user.id},
            {
                "$set": {
                    "first_name": user.first_name,
                    "username": user.username or "",
                    "last_active": time.time(),
                },
                "$inc": {
                    "messages": 1,
                    "points": points_earned,
                },
                "$setOnInsert": {
                    "typing_wins": 0,
                    "coins_earned": 0,
                    "joined_at": time.time(),
                },
            },
            upsert=True,
        )
    except Exception:
        pass


async def award_typing_win(chat_id: int, user: User, reward_points: int, reward_coins: int) -> dict:
    """Awards typing challenge win points and coins atomically."""
    await ensure_user(user)
    await update_balance(user.id, reward_coins)

    updated = await rankings_col.find_one_and_update(
        {"chat_id": chat_id, "user_id": user.id},
        {
            "$set": {
                "first_name": user.first_name,
                "username": user.username or "",
                "last_active": time.time(),
            },
            "$inc": {
                "points": reward_points,
                "typing_wins": 1,
                "coins_earned": reward_coins,
            },
            "$setOnInsert": {
                "messages": 0,
                "joined_at": time.time(),
            },
        },
        upsert=True,
        return_document=True,
    )
    return updated


async def get_group_leaderboard(chat_id: int, limit: int = 10) -> list[dict]:
    """Returns top chat members ranked by points in this group."""
    cursor = rankings_col.find({"chat_id": chat_id}).sort("points", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def get_global_leaderboard(limit: int = 10) -> list[dict]:
    """Returns top chatters globally aggregated across all groups."""
    pipeline = [
        {
            "$group": {
                "_id": "$user_id",
                "first_name": {"$last": "$first_name"},
                "username": {"$last": "$username"},
                "total_points": {"$sum": "$points"},
                "total_messages": {"$sum": "$messages"},
                "total_typing_wins": {"$sum": "$typing_wins"},
            }
        },
        {"$sort": {"total_points": -1}},
        {"$limit": limit},
    ]
    cursor = rankings_col.aggregate(pipeline)
    return await cursor.to_list(length=limit)


async def get_user_chat_rank(chat_id: int, user_id: int) -> tuple[int, dict | None]:
    """Calculates user's position in this chat and returns record."""
    data = await rankings_col.find_one({"chat_id": chat_id, "user_id": user_id})
    if not data:
        return 0, None

    points = data.get("points", 0)
    higher_count = await rankings_col.count_documents({
        "chat_id": chat_id,
        "points": {"$gt": points},
    })
    return higher_count + 1, data


async def get_user_global_stats(user_id: int) -> dict:
    """Calculates user's cumulative points and stats across all groups."""
    pipeline = [
        {"$match": {"user_id": user_id}},
        {
            "$group": {
                "_id": "$user_id",
                "total_points": {"$sum": "$points"},
                "total_messages": {"$sum": "$messages"},
                "total_typing_wins": {"$sum": "$typing_wins"},
                "groups_count": {"$sum": 1},
            }
        },
    ]
    cursor = rankings_col.aggregate(pipeline)
    res = await cursor.to_list(length=1)
    if res:
        return res[0]
    return {
        "total_points": 0,
        "total_messages": 0,
        "total_typing_wins": 0,
        "groups_count": 0,
    }
