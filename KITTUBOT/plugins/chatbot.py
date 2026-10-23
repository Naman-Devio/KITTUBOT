# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Chatbot & AI Companion Plugin
Expressive, Hinglish AI companion that talks naturally in DMs and group mentions,
featuring conversational active memory windowing, media vision reactions, and sticker integration.
"""

import re
import time
import random
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from KITTUBOT.core.ai_brain import ask_kittu
from KITTUBOT.core.media_processor import process_message_media
from KITTUBOT.database.users import ensure_user
from KITTUBOT.database.stickers import add_sticker, get_random_sticker
from KITTUBOT.core.ratelimit import check_rate_limit
from KITTUBOT import log

__mod_name__ = "Chatbot"
__help__ = """
<blockquote>🐾 <b>Kittu AI Companion:</b>
• Just talk naturally in DMs or mention <b>kittu</b> in groups!
• <b>Active Window:</b> Once you talk to Kittu in a group, she remembers you for 60 seconds — no need to repeat @KittuBot on every text!
• <b>Vision:</b> Send photos or stickers — Kittu can actually see and react to them!
• <b>Image Generation:</b> Say <i>"cat ki photo bana de"</i> or <code>/imagine [prompt]</code>
• <code>/ask [query]</code> - Ask Kittu any direct question
• <code>/clear</code> - Clear conversation memory for this chat</blockquote>
"""

# Active conversational memory window per (chat_id, user_id): timestamp
ACTIVE_WINDOWS: dict[tuple[int, int], float] = {}

# Regex patterns for natural Hinglish image generation requests
IMAGE_PROMPT_PATTERNS = [
    re.compile(r"(?i)^(.+?)\s*(?:ki|ka)?\s*(?:image|photo|pic)\s+(?:bana\s*de|bana\s*do|banao|bana)$"),
    re.compile(r"(?i)(?:image|photo|pic|picture)\s+(?:bana\s*de|bana\s*do|banao|bana)\s*[:\-\s]*(.+)"),
    re.compile(r"(?i)(?:draw|generate\s+(?:an?\s+)?image|create\s+(?:an?\s+)?image|paint)\s*(?:of|a|an|me|for\s*me)?\s*[:\-\s]*(.+)"),
]

NAME_PATTERN = re.compile(r"(?i)\b(kittu|kitu|kittubot|kittuai|billu|billi)\b")


def extract_natural_image_prompt(text: str) -> str | None:
    """Detects conversational drawing requests like 'cat ki image bana de'."""
    if not text:
        return None
    for pat in IMAGE_PROMPT_PATTERNS:
        match = pat.search(text.strip())
        if match:
            prompt = match.group(1).strip().lstrip(":- ").strip()
            if len(prompt) >= 3:
                return prompt
    return None


async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct query command."""
    if not update.message:
        return
    if not context.args:
        await update.message.reply_html("🐾 Haan bolo! Kya puchna hai? Example: <code>/ask who is the best?</code>")
        return

    query = " ".join(context.args)
    user = update.effective_user
    chat = update.effective_chat
    await ensure_user(user)

    try:
        await context.bot.send_chat_action(chat_id=chat.id, action="typing")
    except Exception:
        pass

    reply_text, should_sticker = await ask_kittu(
        query, user=user, chat=chat, is_group=(chat.type != "private")
    )
    await update.message.reply_text(reply_text)
    if should_sticker:
        stk_id = await get_random_sticker()
        if stk_id:
            try:
                await update.message.reply_sticker(stk_id)
            except Exception:
                pass


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clears conversation session memory."""
    if not update.message:
        return
    user = update.effective_user
    chat = update.effective_chat
    is_group = chat.type != "private"
    sess_key = f"gc_{chat.id}_u_{user.id}" if is_group else f"dm_{user.id}"

    from KITTUBOT.core.ai_brain import USER_HISTORIES, LAST_ACTIVE
    USER_HISTORIES.pop(sess_key, None)
    LAST_ACTIVE.pop(sess_key, None)
    ACTIVE_WINDOWS.pop((chat.id, user.id), None)

    await update.message.reply_text("chat memory cleared! clean slate. what's up? ^_^")


async def handle_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Master message listener with conversational active window and vision support."""
    message = update.effective_message
    if not message:
        return

    user = update.effective_user
    chat = update.effective_chat
    if not user or user.is_bot:
        return

    # 1. Harvest stickers posted in groups for bot's sticker pool
    if message.sticker and chat.type != "private":
        await add_sticker(
            file_id=message.sticker.file_id,
            file_unique_id=message.sticker.file_unique_id,
            emoji=message.sticker.emoji or "",
            added_by=user.id,
            chat_id=chat.id,
        )

    # 2. Leaky bucket check in Private DMs
    if chat.type == "private" and (message.sticker or message.photo):
        allowed, rem_sec = check_rate_limit(user.id)
        if not allowed:
            await message.reply_text(f"bro stop spamming media, baltti bhar gayi teri! blocked for {rem_sec}s, shanti rakh.")
            return

    text = message.text or message.caption or ""
    text_clean = text.strip()
    if text_clean.startswith("/"):
        return

    bot_info = await context.bot.get_me()
    is_private = chat.type == "private"
    bot_id = bot_info.id
    bot_username = bot_info.username.lower()

    is_reply_to_bot = False
    is_reply_to_someone_else = False

    if message.reply_to_message:
        if message.reply_to_message.from_user and message.reply_to_message.from_user.id == bot_id:
            is_reply_to_bot = True
        else:
            is_reply_to_someone_else = True

    lower_text = text_clean.lower()
    has_mention = f"@{bot_username}" in lower_text
    has_name = bool(NAME_PATTERN.search(text_clean))

    now = time.time()
    user_window_key = (chat.id, user.id)
    is_in_active_window = (now - ACTIVE_WINDOWS.get(user_window_key, 0)) <= 60.0

    # Determine whether Kittu should respond
    should_respond = False
    prompt_to_feed = text_clean

    if is_private:
        should_respond = True
    elif is_reply_to_bot:
        should_respond = True
    elif has_mention:
        should_respond = True
        prompt_to_feed = re.sub(rf"(?i)@{bot_username}", "", text_clean).strip()
    elif has_name:
        should_respond = True
        prompt_to_feed = NAME_PATTERN.sub("", text_clean).strip()
        if not prompt_to_feed:
            prompt_to_feed = text_clean
    elif is_in_active_window and not is_reply_to_someone_else and (message.text or message.photo or message.sticker):
        # User is actively chatting with the bot in group and didn't reply to another person!
        should_respond = True

    if not should_respond:
        return

    # Refresh active window timer for this user in this chat
    ACTIVE_WINDOWS[user_window_key] = now
    await ensure_user(user)

    # 3. Check for Natural Language Image Generation request (e.g. "cat ki photo bana de")
    img_prompt = extract_natural_image_prompt(prompt_to_feed)
    if img_prompt and not message.photo and not message.sticker:
        from KITTUBOT.plugins.imagine import generate_and_reply_image
        await generate_and_reply_image(update, context, img_prompt)
        return

    # 4. Multimodal Media Processing (Photos & Stickers)
    proc_media = None
    if message.photo or message.sticker:
        proc_media = await process_message_media(message)

    # 5. Send Typing / Chat Action
    try:
        action = "upload_photo" if (message.photo or message.sticker) else "typing"
        await context.bot.send_chat_action(chat_id=chat.id, action=action)
    except Exception:
        pass

    # 6. Generate AI response
    reply_text, should_send_sticker = await ask_kittu(
        user_prompt=prompt_to_feed,
        user=user,
        chat=chat,
        is_group=(not is_private),
        media=proc_media,
    )

    # If the user sent a sticker, 25% chance of sending a sticker back
    if not should_send_sticker and message.sticker and random.random() < 0.25:
        should_send_sticker = True

    # Reply with text
    if reply_text:
        try:
            await message.reply_text(reply_text)
        except Exception as e:
            log.warning(f"[Chatbot] Failed to reply: {e}")

    # Reply with sticker if indicated
    if should_send_sticker:
        stk_id = await get_random_sticker()
        if stk_id:
            try:
                await message.reply_sticker(stk_id)
            except Exception as e:
                log.warning(f"[Chatbot] Failed to send sticker: {e}")


def register_handlers(app: Application):
    app.add_handler(CommandHandler("ask", ask_command))
    app.add_handler(CommandHandler("clear", clear_command))
    # Handles text, photos, and stickers for complete multimodal immersion
    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.PHOTO | filters.Sticker.ALL) & ~filters.COMMAND,
            handle_chat_message,
        ),
        group=20,
    )
