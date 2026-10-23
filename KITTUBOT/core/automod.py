# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🛡️ KITTUBOT Evasion-Proof Auto-Moderation Engine
Provides robust text de-obfuscation, homoglyph normalization, leetspeak decoding,
repeated character collapsing, and typo-tolerant stem matching.
"""

import os
import re
import asyncio
from KITTUBOT.database import automod_col
from KITTUBOT import log

BLOCKLIST_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "assets", "blocklist.txt")
)

LEET_MAP = {
    "0": "o",
    "1": "i",
    "!": "i",
    "|": "i",
    "3": "e",
    "4": "a",
    "@": "a",
    "$": "s",
    "5": "s",
    "7": "t",
    "8": "b",
}

NON_ALPHA_REGEX = re.compile(r"[^a-zA-Z\u0900-\u097F\u0A00-\u0A7F]")


def unicode_to_ascii(char: str) -> str:
    """Converts mathematical bold, fraktur, script, and fullwidth unicode to ASCII."""
    code = ord(char)

    # Fullwidth Latin
    if 0xFF21 <= code <= 0xFF3A:
        return chr(ord("a") + (code - 0xFF21))
    if 0xFF41 <= code <= 0xFF5A:
        return chr(ord("a") + (code - 0xFF41))

    # Mathematical Alphanumeric Symbols (0x1D400 - 0x1D7CB)
    if 0x1D400 <= code <= 0x1D7CB:
        for base in range(0x1D400, 0x1D701, 52):
            if base <= code < base + 26:
                return chr(ord("a") + (code - base))
            if base + 26 <= code < base + 52:
                return chr(ord("a") + (code - (base + 26)))

    return char


def collapse_repeated_chars(text: str) -> str:
    """Collapses consecutive identical characters (e.g. fuuuck -> fuck)."""
    if not text:
        return ""
    result = []
    prev = None
    for ch in text:
        if ch != prev:
            result.append(ch)
            prev = ch
    return "".join(result)


def normalize_text(text: str) -> str:
    """Complete de-obfuscation pipeline."""
    # 1. Unicode to ASCII
    text_ascii = "".join(unicode_to_ascii(c) for c in text).lower()

    # 2. Leetspeak substitution
    text_leet = "".join(LEET_MAP.get(c, c) for c in text_ascii)

    # 3. Strip punctuation, dots, spaces, numbers
    clean_alpha = NON_ALPHA_REGEX.sub("", text_leet)

    # 4. Collapse repeated characters
    return collapse_repeated_chars(clean_alpha)


def levenshtein_distance(s: str, t: str) -> int:
    """Calculates Levenshtein edit distance between two strings."""
    if s == t:
        return 0
    if not s:
        return len(t)
    if not t:
        return len(s)

    v0 = list(range(len(t) + 1))
    v1 = [0] * (len(t) + 1)

    for i in range(len(s)):
        v1[0] = i + 1
        for j in range(len(t)):
            cost = 0 if s[i] == t[j] else 1
            v1[j + 1] = min(v1[j] + 1, v0[j + 1] + 1, v0[j] + cost)
        v0 = list(v1)

    return v0[len(t)]


class ModerationFilter:
    def __init__(self, blocklist_path: str = BLOCKLIST_FILE):
        self.blocklist_path = blocklist_path
        self.words: set[str] = set()
        self.stems: list[str] = []
        self._disabled_chats: set[int] = set()
        self._loaded = False

    async def reload(self) -> int:
        """Loads blocklist from local asset file with embedded fallback seeds."""
        new_words: set[str] = set()
        new_stems: list[str] = []

        if os.path.exists(self.blocklist_path):
            try:
                with open(self.blocklist_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        norm = normalize_text(line)
                        if norm:
                            new_words.add(norm)
                            if len(norm) >= 4:
                                new_stems.append(norm)
                log.info(f"[AutoMod] Loaded {len(new_words)} abuse stems from {self.blocklist_path}")
            except Exception as e:
                log.warning(f"[AutoMod] Failed to read blocklist file: {e}")

        # Core profanity seeds to guarantee coverage
        seeds = [
            "chutiya", "madarchod", "bhosdike", "randi", "behenchod",
            "bhadwe", "bhadwa", "gandmasti", "gandu", "bastard", "bitch", "asshole",
            "lauda", "lavde", "lodu", "chut", "gaand", "jhaatu"
        ]
        for s in seeds:
            norm = normalize_text(s)
            if norm:
                new_words.add(norm)
                if len(norm) >= 4:
                    new_stems.append(norm)

        self.words = new_words
        self.stems = new_stems
        self._loaded = True
        return len(self.words)

    async def is_chat_enabled(self, chat_id: int) -> bool:
        """Checks if auto-moderation is active for this chat in MongoDB."""
        if chat_id in self._disabled_chats:
            return False
        try:
            doc = await automod_col.find_one({"chat_id": chat_id})
            if doc and doc.get("enabled") is False:
                self._disabled_chats.add(chat_id)
                return False
        except Exception as e:
            log.warning(f"[AutoMod] DB error: {e}")
        return True

    async def set_chat_enabled(self, chat_id: int, enabled: bool):
        """Enables or disables auto-moderation for a group chat."""
        if enabled:
            self._disabled_chats.discard(chat_id)
        else:
            self._disabled_chats.add(chat_id)

        try:
            await automod_col.update_one(
                {"chat_id": chat_id},
                {"$set": {"chat_id": chat_id, "enabled": enabled}},
                upsert=True,
            )
        except Exception as e:
            log.warning(f"[AutoMod] Error saving setting: {e}")

    async def is_abusive(self, text: str) -> tuple[bool, str]:
        """Checks text against normalized blocklist and typo tolerance."""
        if not self._loaded:
            await self.reload()

        if not text or not self.words:
            return False, ""

        norm_full = normalize_text(text)
        if not norm_full:
            return False, ""

        # 1. Exact match on full normalized text
        if norm_full in self.words:
            return True, norm_full

        # 2. Long stem match on full text (prevents short sub-word false positives)
        for stem in self.stems:
            if len(stem) >= 6 and stem in norm_full:
                return True, stem

        # 3. Word-by-word token evaluation with exact matches and Levenshtein distance
        tokens = text.split()
        for tok in tokens:
            norm_tok = normalize_text(tok)
            if not norm_tok:
                continue
            if norm_tok in self.words:
                return True, norm_tok

            # Check stem containment inside a single word token
            for stem in self.stems:
                if len(stem) >= 6 and stem in norm_tok:
                    return True, stem
                elif len(stem) >= 4 and (norm_tok == stem or norm_tok.startswith(stem)):
                    return True, stem

            # Fuzzy match with edit distance <= 1 on tokens of length >= 5
            if len(norm_tok) >= 5:
                for stem in self.stems:
                    if len(stem) >= 5 and abs(len(norm_tok) - len(stem)) <= 1:
                        if levenshtein_distance(norm_tok, stem) <= 1:
                            return True, stem

        return False, ""


# Global singleton instance
AUTOMOD_FILTER = ModerationFilter()
