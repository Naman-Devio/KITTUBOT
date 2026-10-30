# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
KITTUBOT AI Model & Thinking Preferences Engine
Stores per-user and per-chat model selection and reasoning depth.
"""

from KITTUBOT.database import user_models_col
from KITTUBOT import log

DEFAULT_MODEL = "qwen/qwen3.8-27b"
DEFAULT_THINK = "low"

# In-memory cache for fast lookups
_MODEL_CACHE: dict[str, tuple[str, str]] = {}


def _get_key(chat_id: int, user_id: int, is_group: bool) -> str:
    return f"gc_{chat_id}_u_{user_id}" if is_group else f"dm_{user_id}"


async def get_model_pref(chat_id: int, user_id: int, is_group: bool = False) -> tuple[str, str]:
    """Returns (model_id, think_level) for given chat/user."""
    key = _get_key(chat_id, user_id, is_group)
    if key in _MODEL_CACHE:
        return _MODEL_CACHE[key]

    try:
        doc = await user_models_col.find_one({"session_key": key})
        if doc:
            model = doc.get("model", DEFAULT_MODEL)
            think = doc.get("think", DEFAULT_THINK)
            _MODEL_CACHE[key] = (model, think)
            return (model, think)
    except Exception as e:
        log.warning(f"[ModelPref] Error reading model pref: {e}")

    return (DEFAULT_MODEL, DEFAULT_THINK)


async def set_model_pref(
    chat_id: int,
    user_id: int,
    is_group: bool,
    model: str | None = None,
    think: str | None = None,
):
    """Updates model or think level for given session."""
    key = _get_key(chat_id, user_id, is_group)
    cur_model, cur_think = await get_model_pref(chat_id, user_id, is_group)

    new_model = model or cur_model
    new_think = think or cur_think

    _MODEL_CACHE[key] = (new_model, new_think)

    try:
        await user_models_col.update_one(
            {"session_key": key},
            {
                "$set": {
                    "session_key": key,
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "is_group": is_group,
                    "model": new_model,
                    "think": new_think,
                }
            },
            upsert=True,
        )
    except Exception as e:
        log.warning(f"[ModelPref] Error saving model pref: {e}")
