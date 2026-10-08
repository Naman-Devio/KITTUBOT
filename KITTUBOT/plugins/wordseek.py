# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT WordSeek / Wordle Game Engine
Powered by the complete English dictionary banks (4, 5, 6-letter & daily lists) from WSKUSERBOT.
Supports 6 attempts, real-time color grids (🟩 🟨 ⬛), keyboard letter tracking, smart hints & coin bounties.
"""

import os
import json
import random
import time
import asyncio
from pathlib import Path
from functools import lru_cache
from telegram import Update, Message, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from KITTUBOT.database.users import ensure_user, update_balance
from KITTUBOT import log

__mod_name__ = "WordSeek"
__help__ = """
<blockquote>🔍 <b>ᴡᴏʀᴅsᴇᴇᴋ (ᴡᴏʀᴅʟᴇ ʜᴜʙ):</b>
• <code>/wordseek</code> or <code>/ws</code> - sᴛᴀʀᴛ 5-ʟᴇᴛᴛᴇʀ ᴡᴏʀᴅsᴇᴇᴋ
• <code>/wordseek 4</code> - 4-ʟᴇᴛᴛᴇʀ ǫᴜɪᴄᴋ ʀᴏᴜɴᴅ
• <code>/wordseek 6</code> - 6-ʟᴇᴛᴛᴇʀ ᴍᴀsᴛᴇʀ ʀᴏᴜɴᴅ
• <code>/wsdaily</code> - ᴛᴏᴅᴀʏ's ᴅᴀɪʟʏ ᴄʜᴀʟʟᴇɴɢᴇ ᴡᴏʀᴅ
• <code>/wshint</code> - ɢᴇᴛ ᴀ sᴍᴀʀᴛ ʜɪɴᴛ / ʀᴇᴄᴏᴍᴍᴇɴᴅᴇᴅ ɢᴜᴇss
• <code>/stopws</code> - ᴇɴᴅ ᴀᴄᴛɪᴠᴇ ᴡᴏʀᴅsᴇᴇᴋ ɢᴀᴍᴇ

<b>Rules:</b> 6 attempts. 🟩 = Right spot, 🟨 = Wrong spot, ⬛ = Not in word.</blockquote>
"""

WORDS_DIR = Path(__file__).resolve().parent.parent / "assets" / "words"

# In-memory dictionary caches
COMMON_WORDS: dict[int, list[str]] = {}
ALL_WORDS: dict[int, set[str]] = {}
DAILY_WORDS: list[str] = []


def load_dictionaries():
    """Loads dictionary lists from assets/words."""
    global DAILY_WORDS
    for length, name in [(4, "four"), (5, "five"), (6, "six")]:
        c_path = WORDS_DIR / f"common-{name}.json"
        a_path = WORDS_DIR / f"all-{name}.json"

        if c_path.exists():
            with open(c_path, encoding="utf-8") as f:
                COMMON_WORDS[length] = json.load(f)
        else:
            COMMON_WORDS[length] = ["apple", "crane", "tiger", "zebra"]

        if a_path.exists():
            with open(a_path, encoding="utf-8") as f:
                ALL_WORDS[length] = set(w.lower().strip() for w in json.load(f))
        else:
            ALL_WORDS[length] = set(COMMON_WORDS[length])

    daily_path = WORDS_DIR / "daily-word-lists.json"
    if daily_path.exists():
        with open(daily_path, encoding="utf-8") as f:
            DAILY_WORDS = json.load(f)


load_dictionaries()


def evaluate_guess(guess: str, answer: str) -> list[str]:
    """Evaluates guess against answer matching exact Wordle duplicate rules."""
    n = len(guess)
    pattern = ["⬛"] * n
    pool = list(answer)

    # Pass 1: exact matches (Green)
    for i in range(n):
        if guess[i] == answer[i]:
            pattern[i] = "🟩"
            pool[i] = None

    # Pass 2: wrong position matches (Yellow)
    for i in range(n):
        if pattern[i] == "🟩":
            continue
        if guess[i] in pool:
            pattern[i] = "🟨"
            pool[pool.index(guess[i])] = None

    return pattern


@lru_cache(maxsize=30000)
def _internal_pattern(guess: str, answer: str) -> tuple[str, ...]:
    n = len(guess)
    pattern = ["B"] * n
    pool = list(answer)
    for i in range(n):
        if guess[i] == answer[i]:
            pattern[i] = "G"
            pool[i] = None
    for i in range(n):
        if pattern[i] == "G":
            continue
        if guess[i] in pool:
            pattern[i] = "Y"
            pool[pool.index(guess[i])] = None
    return tuple(pattern)


def get_smart_hint(game: "WordSeekGame") -> str:
    """Calculates best hint suggestion from candidate words using letter frequencies."""
    candidates = COMMON_WORDS.get(game.length, [])
    # Filter candidates based on previous guesses
    remaining = candidates[:]
    for word, pattern in game.guesses:
        p_code = tuple("G" if p == "🟩" else ("Y" if p == "🟨" else "B") for p in pattern)
        remaining = [w for w in remaining if _internal_pattern(word, w) == p_code]

    if not remaining:
        return "Try testing unused common vowels (A, E, I, O, U)!"

    # Letter frequency scoring
    freq: dict[str, int] = {}
    for w in remaining:
        for ch in set(w):
            freq[ch] = freq.get(ch, 0) + 1

    # Find candidate with highest score
    guessed_words = {g[0] for g in game.guesses}
    best_candidate = None
    best_score = -1
    for w in remaining:
        if w in guessed_words:
            continue
        score = sum(freq.get(ch, 0) for ch in set(w))
        if score > best_score:
            best_score = score
            best_candidate = w

    rem_count = len(remaining)
    if best_candidate:
        return f"💡 <b>Hint:</b> <code>{rem_count}</code> possible candidate words left.\nRecommended word to test: <b><code>{best_candidate.upper()}</code></b>"
    return f"💡 <b>Hint:</b> <code>{rem_count}</code> possible words remaining! Focus on: {', '.join(k.upper() for k, _ in sorted(freq.items(), key=lambda x: -x[1])[:4])}"


class WordSeekGame:
    def __init__(self, chat_id: int, length: int, target: str, is_daily: bool = False):
        self.chat_id = chat_id
        self.length = length
        self.target = target.lower()
        self.is_daily = is_daily
        self.guesses: list[tuple[str, list[str]]] = []  # [(word, pattern)]
        self.max_attempts = 6
        self.created_at = time.time()
        self.used_letters: dict[str, str] = {}  # char -> best emoji
        self.solved = False


ACTIVE_WORDSEEK_GAMES: dict[int, WordSeekGame] = {}


def get_game_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💡 Smart Hint", callback_data="ws_hint"),
            InlineKeyboardButton("📜 Rules", callback_data="ws_rules"),
            InlineKeyboardButton("🛑 Forfeit", callback_data="ws_stop"),
        ]
    ])


def render_board(game: WordSeekGame) -> str:
    """Renders the aesthetic WordSeek game board."""
    grid_lines = []
    for word, pattern in game.guesses:
        spaced_word = "  ".join(ch.upper() for ch in word)
        boxes = " ".join(pattern)
        grid_lines.append(f"<code>{spaced_word}</code>\n{boxes}")

    empty_row = " ".join(["⬜"] * game.length)
    for _ in range(game.max_attempts - len(game.guesses)):
        grid_lines.append(empty_row)

    grid_text = "\n\n".join(grid_lines)

    # Keyboard status summary
    status_summary = []
    for ch in sorted(game.used_letters.keys()):
        status_summary.append(f"{ch.upper()}{game.used_letters[ch]}")
    used_str = " ".join(status_summary) if status_summary else "None yet"

    mode_label = "DAILY CHALLENGE" if game.is_daily else f"{game.length}-LETTER MODE"

    return (
        f"🔍 <b>ᴋɪᴛᴛᴜ ᴡᴏʀᴅsᴇᴇᴋ ({mode_label})</b> ✨\n\n"
        f"<blockquote>🎯 <b>ᴛᴀʀɢᴇᴛ :</b> <code>{game.length}-Letter Word</code>\n"
        f"⏳ <b>ᴀᴛᴛᴇᴍᴘᴛs :</b> <code>{len(game.guesses)} / {game.max_attempts}</code>\n"
        f"🔤 <b>ᴋᴇʏʙᴏᴀʀᴅ :</b> {used_str}</blockquote>\n\n"
        f"{grid_text}\n\n"
        f"🎋 <i>Type any {game.length}-letter English word in chat to guess!</i>"
    )


async def start_wordseek_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    if update.callback_query:
        try:
            await update.callback_query.answer()
        except Exception:
            pass

    if chat.id in ACTIVE_WORDSEEK_GAMES:
        await msg.reply_html(
            "⚠️ <b>A WordSeek game is already active here!</b> Finish it or type <code>/stopws</code>.",
            reply_markup=get_game_keyboard()
        )
        return

    length = 5
    if context.args and context.args[0] in ["4", "5", "6"]:
        length = int(context.args[0])

    candidates = COMMON_WORDS.get(length, ["apple", "crane", "tiger"])
    target = random.choice(candidates).lower()

    game = WordSeekGame(chat.id, length, target)
    ACTIVE_WORDSEEK_GAMES[chat.id] = game

    board_text = render_board(game)
    await msg.reply_html(board_text, reply_markup=get_game_keyboard())


async def wsdaily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    if update.callback_query:
        try:
            await update.callback_query.answer()
        except Exception:
            pass

    if chat.id in ACTIVE_WORDSEEK_GAMES:
        await msg.reply_html(
            "⚠️ <b>A WordSeek game is already active here!</b> Finish it or type <code>/stopws</code>.",
            reply_markup=get_game_keyboard()
        )
        return

    if DAILY_WORDS:
        day_idx = int(time.time() // 86400) % len(DAILY_WORDS)
        target = DAILY_WORDS[day_idx].lower()
    else:
        target = random.choice(COMMON_WORDS.get(5, ["crane"])).lower()

    game = WordSeekGame(chat.id, len(target), target, is_daily=True)
    ACTIVE_WORDSEEK_GAMES[chat.id] = game

    board_text = render_board(game)
    await msg.reply_html(board_text, reply_markup=get_game_keyboard())


async def stop_ws_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    if chat.id in ACTIVE_WORDSEEK_GAMES:
        game = ACTIVE_WORDSEEK_GAMES.pop(chat.id)
        await msg.reply_html(
            f"🛑 <b>ᴡᴏʀᴅsᴇᴇᴋ ᴄᴀɴᴄᴇʟʟᴇᴅ!</b>\n\n"
            f"<blockquote>The secret word was: <b>{game.target.upper()}</b></blockquote>"
        )
    else:
        await msg.reply_html("No WordSeek game is currently running in this chat.")


async def wshint_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    if chat.id not in ACTIVE_WORDSEEK_GAMES:
        await msg.reply_html("No WordSeek game active! Start one with <code>/wordseek</code>.")
        return
    game = ACTIVE_WORDSEEK_GAMES[chat.id]
    hint_text = get_smart_hint(game)
    await msg.reply_html(hint_text)


async def wordseek_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = update.effective_chat.id

    if data == "ws_rules":
        await query.message.reply_html(
            "<blockquote>📖 <b>ᴡᴏʀᴅsᴇᴇᴋ ɢᴜɪᴅᴇ & ʀᴜʟᴇs:</b>\n\n"
            "• You have <b>6 attempts</b> to find the hidden secret word.\n"
            "• 🟩 <b>Green:</b> Letter is correct and in the right spot.\n"
            "• 🟨 <b>Yellow:</b> Letter is in the word, but in wrong position.\n"
            "• ⬛ <b>Black:</b> Letter does not appear in remaining slots.\n\n"
            "Simply send your guess directly as a message in chat!</blockquote>"
        )
        return

    if chat_id not in ACTIVE_WORDSEEK_GAMES:
        await query.answer("No active game in this chat!", show_alert=True)
        return

    game = ACTIVE_WORDSEEK_GAMES[chat_id]

    if data == "ws_hint":
        hint_text = get_smart_hint(game)
        await query.message.reply_html(hint_text)
    elif data == "ws_stop":
        del ACTIVE_WORDSEEK_GAMES[chat_id]
        await query.message.reply_html(
            f"🛑 <b>ɢᴀᴍᴇ ғᴏʀғᴇɪᴛᴇᴅ!</b>\n\n"
            f"<blockquote>The hidden word was: <b>{game.target.upper()}</b></blockquote>"
        )


async def wordseek_guess_listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message = update.effective_message
    user = update.effective_user

    if not chat or chat.id not in ACTIVE_WORDSEEK_GAMES:
        return

    if not message or not message.text:
        return

    text = message.text.strip().lower()
    game = ACTIVE_WORDSEEK_GAMES[chat.id]

    # Must be alphabetic and exact length
    if not text.isalpha() or len(text) != game.length:
        return

    # Check dictionary validity
    valid_set = ALL_WORDS.get(game.length, set())
    if valid_set and text not in valid_set:
        await message.reply_html(f"❌ <b>'{text.upper()}'</b> is not in the WordSeek English dictionary! Try another word.")
        return

    pattern = evaluate_guess(text, game.target)
    game.guesses.append((text, pattern))

    # Update keyboard tracker
    for ch, p in zip(text, pattern):
        curr = game.used_letters.get(ch, "")
        if p == "🟩" or (p == "🟨" and curr != "🟩") or (p == "⬛" and not curr):
            game.used_letters[ch] = p

    # Check WIN
    if text == game.target:
        game.solved = True
        del ACTIVE_WORDSEEK_GAMES[chat.id]

        attempts_left = game.max_attempts - len(game.guesses)
        rewards = {5: 600, 4: 500, 3: 400, 2: 300, 1: 200, 0: 100}
        bounty = rewards.get(attempts_left, 250)

        await ensure_user(user)
        await update_balance(user.id, bounty)

        board_text = render_board(game)
        await message.reply_html(
            f"{board_text}\n\n"
            f"🎉 <b>ᴡᴏʀᴅsᴇᴇᴋ sᴏʟᴠᴇᴅ!</b> 🏆✨\n\n"
            f"<blockquote>👑 {user.mention_html()} guessed the word <b>{game.target.upper()}</b> in <b>{len(game.guesses)} attempts</b>!\n"
            f"💰 <b>Bounty Won:</b> <code>+{bounty:,} Coins</code>! 🪙</blockquote>\n\n"
            "🎋 <i>Type /wordseek to play another round!</i>"
        )
        return

    # Check LOSS (6 attempts finished)
    if len(game.guesses) >= game.max_attempts:
        del ACTIVE_WORDSEEK_GAMES[chat.id]
        board_text = render_board(game)
        await message.reply_html(
            f"{board_text}\n\n"
            f"💀 <b>ɢᴀᴍᴇ ᴏᴠᴇʀ! ᴏᴜᴛ ᴏғ ᴀᴛᴛᴇᴍᴘᴛs!</b>\n\n"
            f"<blockquote>The secret word was: <b>{game.target.upper()}</b>\n"
            f"Better luck next time!</blockquote>\n\n"
            "🎋 <i>Type /wordseek to try again!</i>"
        )
        return

    # Show updated board with buttons
    board_text = render_board(game)
    await message.reply_html(board_text, reply_markup=get_game_keyboard())


def register_handlers(app: Application):
    app.add_handler(CommandHandler(["wordseek", "ws"], start_wordseek_command))
    app.add_handler(CommandHandler(["wsdaily", "dailyword"], wsdaily_command))
    app.add_handler(CommandHandler(["wshint", "wordhint"], wshint_command))
    app.add_handler(CommandHandler(["stopws", "endws"], stop_ws_command))
    app.add_handler(CallbackQueryHandler(wordseek_callback_handler, pattern="^ws_"))

    # Listen for words without slash commands in both Groups and Private Chats
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, wordseek_guess_listener),
        group=18,
    )
