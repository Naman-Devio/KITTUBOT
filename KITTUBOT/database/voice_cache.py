# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
Voice cache database operations.
Stores generated voice note file_ids keyed by text hash + voice_id
to avoid redundant TTS API calls and conserve ElevenLabs quota.
"""

import hashlib
import time
from datetime import datetime, timezone
from KITTUBOT.database import db

voice_cache_col = db["voice_cache"]
voice_quota_col = db["voice_quota"]


def _text_hash(text: str, voice_id: str) -> str:
    """Deterministic hash for a text+voice combination."""
    raw = f"{text.strip().lower()}|{voice_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


async def get_cached_voice(text: str, voice_id: str) -> str | None:
    """Returns cached Telegram file_id for this text+voice combo, or None."""
    h = _text_hash(text, voice_id)
    doc = await voice_cache_col.find_one({"text_hash": h})
    if doc:
        return doc.get("telegram_file_id")
    return None


async def invalidate_cached_voice(text: str, voice_id: str):
    """Deletes an invalid or expired voice cache entry from MongoDB."""
    h = _text_hash(text, voice_id)
    await voice_cache_col.delete_one({"text_hash": h})


async def cache_voice(text: str, voice_id: str, telegram_file_id: str, language: str = "hi"):
    """Stores a generated voice note's Telegram file_id for future reuse."""
    h = _text_hash(text, voice_id)
    await voice_cache_col.update_one(
        {"text_hash": h},
        {
            "$set": {
                "text_hash": h,
                "voice_id": voice_id,
                "language": language,
                "telegram_file_id": telegram_file_id,
                "text_preview": text[:80],
                "updated_at": datetime.now(timezone.utc),
            },
            "$setOnInsert": {"created_at": datetime.now(timezone.utc)},
        },
        upsert=True,
    )


async def get_monthly_chars_used() -> int:
    """Returns total ElevenLabs characters used this month."""
    now = datetime.now(timezone.utc)
    month_key = f"{now.year}-{now.month:02d}"
    doc = await voice_quota_col.find_one({"month": month_key})
    if doc:
        return doc.get("chars_used", 0)
    return 0


async def add_chars_used(chars: int):
    """Increments the monthly character usage counter."""
    now = datetime.now(timezone.utc)
    month_key = f"{now.year}-{now.month:02d}"
    await voice_quota_col.update_one(
        {"month": month_key},
        {"$inc": {"chars_used": chars}},
        upsert=True,
    )


async def is_quota_available(text_length: int, max_chars: int = 9500) -> bool:
    """Checks if ElevenLabs monthly quota can handle this text."""
    used = await get_monthly_chars_used()
    return (used + text_length) <= max_chars
