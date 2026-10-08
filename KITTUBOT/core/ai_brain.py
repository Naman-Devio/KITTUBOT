# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT AI Brain & Personality Engine
Dual fallback async AI conversation engine with Hinglish personality & context memory.
"""

import random
import time
import httpx
from KITTUBOT.config import config
from KITTUBOT import log

KITTU_SYSTEM_PROMPT = (
    "You are Kittu (किट्टू), an affectionate, witty, super smart and slightly sarcastic AI companion "
    "living inside Telegram. You chat naturally in casual conversational Hinglish (mix of Hindi & English). "
    "You love teasing your friends, playing games, and keeping group chats alive. Keep replies punchy, "
    "fun, expressive and human-like (usually 1 to 3 sentences). Never sound like a robotic customer service bot."
)

# Groq models that are verified and active on the platform
GROQ_MODELS = [
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
]

# Recent message history per user_id: {user_id: [(role, content), ...]}
USER_HISTORIES: dict[int, list[dict]] = {}
LAST_ACTIVE: dict[int, float] = {}


def get_user_messages(user_id: int, user_name: str, new_prompt: str) -> list[dict]:
    """Builds conversation history payload with system prompt."""
    now = time.time()
    # Reset history if inactive for more than 20 minutes
    if user_id in LAST_ACTIVE and (now - LAST_ACTIVE[user_id]) > 1200:
        USER_HISTORIES.pop(user_id, None)

    history = USER_HISTORIES.setdefault(user_id, [])

    messages = [{"role": "system", "content": KITTU_SYSTEM_PROMPT}]
    for msg in history[-6:]:  # Keep last 6 exchanges
        messages.append(msg)

    messages.append({"role": "user", "content": f"{user_name}: {new_prompt}"})
    LAST_ACTIVE[user_id] = now
    return messages


def record_assistant_reply(user_id: int, user_name: str, user_prompt: str, reply: str):
    """Saves user prompt and assistant reply to context history."""
    history = USER_HISTORIES.setdefault(user_id, [])
    history.append({"role": "user", "content": f"{user_name}: {user_prompt}"})
    history.append({"role": "assistant", "content": reply})
    if len(history) > 12:
        USER_HISTORIES[user_id] = history[-12:]


async def ask_kittu(user_prompt: str, user_name: str = "Friend", user_id: int = 0) -> str:
    """Queries AI provider with prioritized Groq engine, Mistral fallback, and context memory."""
    messages = get_user_messages(user_id, user_name, user_prompt)

    # 1. Groq (Ultra-fast, lowest latency)
    if config.GROQ_API_KEY:
        for model in GROQ_MODELS:
            try:
                async with httpx.AsyncClient(timeout=12.0) as client:
                    res = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {config.GROQ_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": messages,
                            "max_tokens": 180,
                            "temperature": 0.85,
                        },
                    )
                    if res.status_code == 200:
                        data = res.json()
                        reply = data["choices"][0]["message"]["content"].strip()
                        if reply:
                            record_assistant_reply(user_id, user_name, user_prompt, reply)
                            return reply
                    else:
                        log.warning(f"Groq model '{model}' returned {res.status_code}: {res.text[:120]}")
            except Exception as e:
                log.warning(f"Groq API error on '{model}': {e}")

    # 2. Mistral AI Fallback
    if config.MISTRAL_API_KEY:
        for model in ["mistral-small-latest", "open-mistral-7b"]:
            try:
                async with httpx.AsyncClient(timeout=12.0) as client:
                    res = await client.post(
                        "https://api.mistral.ai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {config.MISTRAL_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": messages,
                            "max_tokens": 180,
                            "temperature": 0.8,
                        },
                    )
                    if res.status_code == 200:
                        data = res.json()
                        reply = data["choices"][0]["message"]["content"].strip()
                        if reply:
                            record_assistant_reply(user_id, user_name, user_prompt, reply)
                            return reply
                    else:
                        log.warning(f"Mistral model '{model}' returned {res.status_code}: {res.text[:120]}")
            except Exception as e:
                log.warning(f"Mistral AI query failed on '{model}': {e}")

    # 3. Smart dynamic fallbacks
    fallbacks = [
        f"Arre {user_name}, kya bol rahe ho! Thoda seedha bolo na 😂",
        f"Acha ji? {user_name}, main sab samajh rahi hu! Baad me mat bolna maine warn nahi kiya 😉",
        f"Haha {user_name}! Game khelna hai to /game likho, baki baatein baad me!",
        f"Suno {user_name}, main thoda busy hu coins count karne me, par tum bolo kya haal chaal?",
    ]
    return random.choice(fallbacks)
