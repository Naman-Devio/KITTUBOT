# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Font & Aesthetic Typography Engine
Converts text into aesthetic Small Caps and styled Telegram typography.
"""

# Small Caps Character Map
SMALL_CAPS_MAP = {
    'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ғ', 'g': 'ɢ', 'h': 'ʜ',
    'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ',
    'q': 'ǫ', 'r': 'ʀ', 's': 's', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x',
    'y': 'ʏ', 'z': 'ᴢ',
    'A': 'ᴀ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 'E': 'ᴇ', 'F': 'ғ', 'G': 'ɢ', 'H': 'ʜ',
    'I': 'ɪ', 'J': 'ᴊ', 'K': 'ᴋ', 'L': 'ʟ', 'M': 'ᴍ', 'N': 'ɴ', 'O': 'ᴏ', 'P': 'ᴘ',
    'Q': 'ǫ', 'R': 'ʀ', 'S': 's', 'T': 'ᴛ', 'U': 'ᴜ', 'V': 'ᴠ', 'W': 'ᴡ', 'X': 'x',
    'Y': 'ʏ', 'Z': 'ᴢ',
}


def to_small_caps(text: str) -> str:
    """Converts a standard English string to aesthetic Small Caps."""
    return ''.join(SMALL_CAPS_MAP.get(c, c) for c in text)


def format_category_name(name: str) -> str:
    """Formats module category names into aesthetic button text."""
    icons = {
        "admin": "👑",
        "chatbot": "🤖",
        "economy": "💰",
        "games": "⚔️",
        "help": "📖",
        "ping": "⚡",
        "riddles": "🧩",
        "shop": "🛒",
        "social": "❤️",
        "general": "🐾",
        "uno": "🃏",
        "wordgames": "🔤",
        "bomb": "💣",
    }
    icon = icons.get(name.lower(), "✨")
    return f"{icon} {to_small_caps(name)}"
