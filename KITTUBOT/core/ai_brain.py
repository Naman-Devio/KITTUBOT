# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT AI Brain & Personality Engine
Dual fallback async AI conversation engine with Hinglish personality.
"""

import httpx
from KITTUBOT.config import config
from KITTUBOT import log

KITTU_SYSTEM_PROMPT = (
    "You are Kittu (किट्टू), an affectionate, witty, super smart and slightly sarcastic AI companion "
    "living inside Telegram. You chat naturally in casual conversational Hinglish (mix of Hindi & English). "
    "You love teasing your friends, playing games, and keeping group chats alive. Keep replies punchy, "
    "fun, and human-like (usually 1 to 3 sentences). Never sound like a robotic customer service bot."
)


async def ask_kittu(user_prompt: str, user_name: str = "Friend") -> str:
    """Queries AI provider with graceful fallback."""
    # 1. Try Mistral if key exists
    if config.MISTRAL_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    "https://api.mistral.ai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {config.MISTRAL_API_KEY}"},
                    json={
                        "model": "mistral-small-latest",
                        "messages": [
                            {"role": "system", "content": KITTU_SYSTEM_PROMPT},
                            {"role": "user", "content": f"{user_name}: {user_prompt}"},
                        ],
                        "max_tokens": 150,
                        "temperature": 0.8,
                    },
                )
                if res.status_code == 200:
                    data = res.json()
                    return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            log.warning(f"Mistral AI query failed: {e}")

    # 2. Try Groq if key exists
    if config.GROQ_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [
                            {"role": "system", "content": KITTU_SYSTEM_PROMPT},
                            {"role": "user", "content": f"{user_name}: {user_prompt}"},
                        ],
                        "max_tokens": 150,
                        "temperature": 0.8,
                    },
                )
                if res.status_code == 200:
                    data = res.json()
                    return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            log.warning(f"Groq AI query failed: {e}")

    # 3. Smart offline fallbacks
    fallbacks = [
        f"Arre {user_name}, kya bol rahe ho! Thoda seedha bolo na 😂",
        f"Acha ji? {user_name}, main sab samajh rahi hu! Baad me mat bolna maine warn nahi kiya 😉",
        f"Haha {user_name}! Game khelna hai to /game likho, baki baatein baad me!",
        f"Suno {user_name}, main thoda busy hu coins count karne me, par tum bolo kya haal chaal?",
    ]
    import random
    return random.choice(fallbacks)
