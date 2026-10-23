# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🛡️ KITTUBOT Auto-Moderation Plugin
Automatically detects and cleans abusive, vulgar, and evasion-attempting profanity
with self-destructing warning messages.
"""

import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from KITTUBOT.core.automod import AUTOMOD_FILTER
from KITTUBOT.core.permissions import is_user_admin
from KITTUBOT.config import config
from KITTUBOT import log

__mod_name__ = "AutoMod"
__help__ = """
<blockquote>🛡️ <b>Evasion-Proof Auto-Moderation:</b>
• <code>/abuse [on|off]</code> - Toggle smart profanity auto-deletion in this group
• Automatically normalizes leetspeak, dots, fancy unicode fonts, and typos
• Offending messages are instantly purged with an 8-second self-destructing warning badge</blockquote>
"""


async def delete_after_delay(msg, delay: float = 8.0):
    """Deletes the warning message after specified seconds."""
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass


async def automod_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Intercepts and screens incoming messages for abusive content."""
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user or user.is_bot:
        return

    # Auto-moderation only runs in group chats
    if chat.type == "private":
        return

    # Check if enabled in this chat
    if not await AUTOMOD_FILTER.is_chat_enabled(chat.id):
        return

    text = message.text or message.caption or ""
    if not text:
        return

    # Skip commands to avoid false alarms
    if text.strip().startswith("/"):
        return

    # Skip admins so they can administer the group
    if await is_user_admin(chat, user.id):
        return

    is_bad, matched = await AUTOMOD_FILTER.is_abusive(text)
    if not is_bad:
        return

    log.info(f"[AutoMod] Abusive content detected from user {user.id} in chat {chat.id} (matched: {matched}). Deleting...")

    # Delete offending message
    try:
        await message.delete()
    except Exception as e:
        log.warning(f"[AutoMod] Could not delete message: {e}")

    # Send self-destructing warning
    user_mention = f"@{user.username}" if user.username else user.first_name
    warning_text = (
        f"<blockquote>🚫 <b>{user_mention}</b>, abusive and vulgar language is not allowed here. "
        f"Keep the chat respectful!</blockquote>"
    )

    try:
        warn_msg = await chat.send_message(warning_text, parse_mode="HTML")
        if warn_msg:
            asyncio.create_task(delete_after_delay(warn_msg, delay=8.0))
    except Exception as e:
        log.warning(f"[AutoMod] Failed to send warning: {e}")


async def abuse_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enables or disables auto-moderation for the group."""
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return

    if chat.type == "private":
        await message.reply_html("🛡️ Auto-moderation is only active in group chats! In DMs you can text normally.")
        return

    if not await is_user_admin(chat, user.id):
        await message.reply_html("🚫 Only group administrators can toggle auto-moderation!")
        return

    if not context.args:
        is_enabled = await AUTOMOD_FILTER.is_chat_enabled(chat.id)
        status_str = "ENABLED" if is_enabled else "DISABLED"
        word_count = len(AUTOMOD_FILTER.words)
        await message.reply_html(
            f"🛡️ <b>Auto-Moderation Status:</b> <code>{status_str}</code> (Loaded Stems: <code>{word_count}</code>)\n\n"
            "<b>Usage:</b>\n"
            "• <code>/abuse on</code> - Enable smart auto-moderation\n"
            "• <code>/abuse off</code> - Disable auto-moderation"
        )
        return

    sub = context.args[0].lower().strip()
    if sub in ("on", "enable", "start", "true"):
        await AUTOMOD_FILTER.set_chat_enabled(chat.id, True)
        await message.reply_html(
            "🛡️ <b>Auto-Moderation is now ENABLED for this group!</b>\n"
            "Abusive messages will be automatically purged with self-destructing warnings."
        )
    elif sub in ("off", "disable", "stop", "false"):
        await AUTOMOD_FILTER.set_chat_enabled(chat.id, False)
        await message.reply_html("🛡️ <b>Auto-Moderation is now DISABLED for this group.</b>")
    else:
        await message.reply_html("Usage: <code>/abuse on</code> or <code>/abuse off</code>")


async def reload_abuse_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reloads local blocklist (Owner only)."""
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return

    if user.id != config.OWNER_ID and user.id not in config.SUDO_IDS:
        await message.reply_html("🚫 You do not have permission to reload the blocklist.")
        return

    count = await AUTOMOD_FILTER.reload()
    await message.reply_html(f"✨ Auto-moderation blocklist successfully reloaded! (Active Stems: <code>{count}</code>)")


def register_handlers(app: Application):
    app.add_handler(CommandHandler(["abuse", "automod"], abuse_command))
    app.add_handler(CommandHandler("reload_abuse", reload_abuse_command))
    # Intercept text and captions at group 0 with highest priority
    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.CAPTION) & ~filters.COMMAND,
            automod_message_handler,
        ),
        group=0,
    )
