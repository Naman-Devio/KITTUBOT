# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Chatbot & AI Companion Plugin
Expressive, Hinglish AI companion that talks naturally in DMs and group mentions,
featuring conversational active memory windowing, media vision reactions,
sticker integration, and human-like voice note conversations.
"""

import io
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
from KITTUBOT.core.ai_brain import ask_kittu, ask_kittu_voice
from KITTUBOT.core.media_processor import process_message_media
from KITTUBOT.core.voice_engine import (
    transcribe_voice,
    generate_voice_note,
    get_bored_line,
    _detect_voice_request,
    clean_text_for_speech,
)
from KITTUBOT.database.users import ensure_user
from KITTUBOT.database.stickers import add_sticker, get_random_sticker
from KITTUBOT.database.voice_cache import get_cached_voice, cache_voice, invalidate_cached_voice
from KITTUBOT.core.ratelimit import check_rate_limit
from KITTUBOT.config import config
from KITTUBOT import log

__mod_name__ = "Chatbot"
__help__ = """
<blockquote>🐾 <b>Kittu AI Companion:</b>
• Just talk naturally in DMs or mention <b>kittu</b> in groups!
• <b>Active Window:</b> Once you talk to Kittu in a group, she remembers you for 60 seconds — no need to repeat @KittuBot on every text!
• <b>Vision:</b> Send photos or stickers — Kittu can actually see and react to them!
• <b>Voice Notes:</b> Send Kittu a voice note and she'll reply with her own voice! Ask her to say things too!
• <b>Image Generation:</b> Say <i>"cat ki photo bana de"</i> or <code>/imagine [prompt]</code>
• <code>/ask [query]</code> - Ask Kittu any direct question
• <code>/clear</code> - Clear conversation memory for this chat</blockquote>
"""

# Active conversational memory window per (chat_id, user_id): timestamp
ACTIVE_WINDOWS: dict[tuple[int, int], float] = {}

# Bored mode tracker per chat_id: (message_count, last_kittu_mention_time)
BORED_TRACKER: dict[int, dict] = {}

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


async def _send_voice_reply(
    message,
    text: str,
    language: str = "hi",
    chat_id: int | None = None,
    bot=None,
) -> bool:
    """Generates and sends a voice note reply. Handles caching transparently."""
    from KITTUBOT.core.voice_engine import _pick_voice_id

    clean_text = clean_text_for_speech(text)
    if not clean_text:
        clean_text = text

    voice_id = _pick_voice_id(language)

    # 1. Check cache for existing Telegram file_id
    cached_fid = await get_cached_voice(clean_text, voice_id)
    if cached_fid:
        try:
            if message:
                await message.reply_voice(voice=cached_fid)
            elif bot and chat_id:
                await bot.send_voice(chat_id=chat_id, voice=cached_fid)
            log.info("[Chatbot] Voice reply sent from cache")
            return True
        except Exception as e:
            log.warning(f"[Chatbot] Cached voice file_id expired or rejected, invalidating: {e}")
            await invalidate_cached_voice(clean_text, voice_id)

    # 2. Generate new voice note
    ogg_data, used_voice_id = await generate_voice_note(clean_text, language=language, force_voice_id=voice_id)
    if ogg_data:
        voice_file = io.BytesIO(ogg_data)
        voice_file.name = "kittu_voice.ogg"
        try:
            sent = None
            if message:
                sent = await message.reply_voice(voice=voice_file)
            elif bot and chat_id:
                sent = await bot.send_voice(chat_id=chat_id, voice=voice_file)

            # Cache the file_id for reuse
            if sent and sent.voice:
                await cache_voice(clean_text, used_voice_id, sent.voice.file_id, language)
            log.info(f"[Chatbot] Voice reply sent ({len(clean_text)} chars, lang={language})")
            return True
        except Exception as e:
            log.warning(f"[Chatbot] Failed to send voice: {e}")
    return False


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming voice notes — transcribes, processes, and replies with voice."""
    message = update.effective_message
    if not message or not message.voice:
        return

    user = update.effective_user
    chat = update.effective_chat
    if not user or user.is_bot:
        return

    bot_info = await context.bot.get_me()
    bot_id = bot_info.id
    is_private = chat.type == "private"

    # Determine if this voice note is directed at Kittu
    is_reply_to_bot = False
    if message.reply_to_message and message.reply_to_message.from_user:
        is_reply_to_bot = message.reply_to_message.from_user.id == bot_id

    caption = (message.caption or "").strip()
    has_name_in_caption = bool(NAME_PATTERN.search(caption))

    # Check active window
    user_window_key = (chat.id, user.id)
    now = time.time()
    is_in_active_window = (now - ACTIVE_WINDOWS.get(user_window_key, 0)) <= 60.0

    should_respond = is_private or is_reply_to_bot or has_name_in_caption or is_in_active_window

    if not should_respond:
        return

    # Guard: Audio duration and size check (prevent dyno memory exhaustion)
    if (message.voice.duration and message.voice.duration > 120) or (message.voice.file_size and message.voice.file_size > 8 * 1024 * 1024):
        await message.reply_text("itna bada voice note mat bhej yaar, chhota sa bhej 1-2 min max ^_^")
        return

    # Refresh active window
    ACTIVE_WINDOWS[user_window_key] = now
    await ensure_user(user)

    # Send "recording voice" action
    try:
        await context.bot.send_chat_action(chat_id=chat.id, action="record_voice")
    except Exception:
        pass

    # Download and transcribe the voice note
    try:
        voice_file = await message.voice.get_file()
        voice_bytes = await voice_file.download_as_bytearray()
    except Exception as e:
        log.warning(f"[Chatbot] Failed to download voice note: {e}")
        await message.reply_text("voice note download nhi ho paya, wapas bhej na")
        return

    transcription = await transcribe_voice(bytes(voice_bytes))
    if not transcription or not transcription.text:
        # Could not transcribe, send a text fallback
        await message.reply_text("voice note sun li pr kuch samjh nhi aaya tera network kharab h kya")
        return

    detected_lang = transcription.language
    transcript_text = transcription.text
    is_owner = user.id == config.OWNER_ID

    log.info(f"[Chatbot] Voice transcribed: '{transcript_text[:80]}' lang={detected_lang} owner={is_owner}")

    # Check if it's a "say this" / custom speech request
    is_voice_req, requested_text = _detect_voice_request(transcript_text)
    if not is_voice_req and caption:
        is_voice_req, requested_text = _detect_voice_request(caption)

    if is_voice_req:
        # Generate custom speech response
        voice_reply_text = await ask_kittu_voice(
            user_prompt=transcript_text,
            user=user,
            chat=chat,
            is_group=(not is_private),
            is_owner=is_owner,
            custom_speech_text=requested_text,
        )
    else:
        # Generate normal conversational voice response
        voice_reply_text = await ask_kittu_voice(
            user_prompt=transcript_text,
            user=user,
            chat=chat,
            is_group=(not is_private),
            is_owner=is_owner,
        )

    if voice_reply_text:
        success = await _send_voice_reply(message, voice_reply_text, language=detected_lang)
        if not success:
            await message.reply_text(voice_reply_text)


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

    # Prune memory if dictionaries grow large
    if len(ACTIVE_WINDOWS) > 300:
        cutoff = now - 120.0
        for k in [k for k, v in ACTIVE_WINDOWS.items() if v < cutoff]:
            ACTIVE_WINDOWS.pop(k, None)

    if len(BORED_TRACKER) > 300:
        cutoff_b = now - 3600.0
        for cid in [c for c, tr in BORED_TRACKER.items() if tr.get("last_mention", 0) < cutoff_b]:
            BORED_TRACKER.pop(cid, None)

    # Bored mode: Track group activity
    if chat.type != "private":
        tracker = BORED_TRACKER.setdefault(chat.id, {"msg_count": 0, "last_mention": time.time()})
        tracker["msg_count"] += 1
        if has_name or has_mention or is_reply_to_bot:
            tracker["last_mention"] = now

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

    # Check for text-based voice request (e.g., "kittu bol ke bata i love you")
    is_text_voice_req = False
    requested_speech = None
    if should_respond and text_clean and not message.photo and not message.sticker:
        is_text_voice_req, requested_speech = _detect_voice_request(text_clean)

    # Handle text-based voice request → generate voice note reply
    if is_text_voice_req and should_respond:
        ACTIVE_WINDOWS[user_window_key] = now
        await ensure_user(user)
        try:
            await context.bot.send_chat_action(chat_id=chat.id, action="record_voice")
        except Exception:
            pass

        is_owner = user.id == config.OWNER_ID
        voice_text = await ask_kittu_voice(
            user_prompt=text_clean,
            user=user,
            chat=chat,
            is_group=(not is_private),
            is_owner=is_owner,
            custom_speech_text=requested_speech,
        )
        if voice_text:
            # Detect language from text for voice selection
            lang = "hi"  # Default Hinglish
            if re.search(r"[a-zA-Z]{3,}", voice_text) and not re.search(r"[\u0900-\u097F]", voice_text):
                lang = "en"
            success = await _send_voice_reply(message, voice_text, language=lang)
            if not success:
                await message.reply_text(voice_text)
        return

    if not should_respond:
        # Bored mode check: Random spontaneous voice note in groups
        if chat.type != "private":
            tracker = BORED_TRACKER.get(chat.id, {})
            msg_count = tracker.get("msg_count", 0)
            last_mention = tracker.get("last_mention", now)
            # After 50+ messages, no mention for 10+ min, 3% chance
            if msg_count >= 50 and (now - last_mention) > 600 and random.random() < 0.03:
                BORED_TRACKER[chat.id] = {"msg_count": 0, "last_mention": now}
                bored_text = get_bored_line()
                try:
                    await context.bot.send_chat_action(chat_id=chat.id, action="record_voice")
                    # Send unsolicited to chat directly, without quoting an innocent user's text
                    success = await _send_voice_reply(
                        message=None,
                        text=bored_text,
                        language="hi",
                        chat_id=chat.id,
                        bot=context.bot,
                    )
                    if not success:
                        await context.bot.send_message(chat_id=chat.id, text=bored_text)
                    log.info(f"[Chatbot] Bored mode voice sent in {chat.id}")
                except Exception as e:
                    log.warning(f"[Chatbot] Bored mode failed: {e}")
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
    # Voice note handler (higher priority)
    app.add_handler(
        MessageHandler(
            filters.VOICE & ~filters.COMMAND,
            handle_voice_message,
        ),
        group=19,
    )
    # Handles text, photos, and stickers for complete multimodal immersion
    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.PHOTO | filters.Sticker.ALL) & ~filters.COMMAND,
            handle_chat_message,
        ),
        group=20,
    )
