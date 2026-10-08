# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT AFK (Away From Keyboard) Plugin
Alerts chat members when tagged users are away, and welcomes them back on return.
"""

import time
from telegram import Update, MessageEntity
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from KITTUBOT.database.afk import set_user_afk, get_user_afk, remove_user_afk
from KITTUBOT import log

__mod_name__ = "AFK"
__help__ = """
<blockquote>💤 <b>ᴀғᴋ (ᴀᴡᴀʏ ғʀᴏᴍ ᴋᴇʏʙᴏᴀʀᴅ):</b>
• <code>/afk [reason]</code> - ᴍᴀʀᴋ ʏᴏᴜʀsᴇʟғ ᴀs ᴀғᴋ
• <i>ᴡʜᴇɴ ᴍᴇɴᴛɪᴏɴᴇᴅ, ᴋɪᴛᴛᴜ ᴡɪʟʟ ɪɴғᴏʀᴍ ᴛʜᴇ ɢʀᴏᴜᴘ!</i>
• <i>sɪᴍᴘʟʏ sᴇɴᴅ ᴀɴʏ ᴍᴇssᴀɢᴇ ᴛᴏ ᴛᴜʀɴ ᴏғғ ᴀғᴋ.</i></blockquote>
"""


def format_duration(seconds: float) -> str:
    """Formats seconds into human readable duration."""
    sec = int(seconds)
    if sec < 60:
        return f"{sec} seconds"
    minutes = sec // 60
    rem_sec = sec % 60
    if minutes < 60:
        return f"{minutes}m {rem_sec}s"
    hours = minutes // 60
    rem_min = minutes % 60
    if hours < 24:
        return f"{hours}h {rem_min}m"
    days = hours // 24
    rem_hours = hours % 24
    return f"{days}d {rem_hours}h {rem_min}m"


async def afk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return

    reason = "Busy right now"
    if context.args:
        reason = " ".join(context.args).strip()

    await set_user_afk(user.id, reason)
    await update.message.reply_html(
        f"<blockquote>💤 <b>{user.mention_html()} ɪs ɴᴏᴡ ᴀғᴋ!</b>\n"
        f"💭 <b>ʀᴇᴀsᴏɴ :</b> <i>{reason}</i></blockquote>"
    )


async def afk_message_listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return

    # 1. Check if the current sender was AFK -> welcome them back!
    # Only if this message was NOT the /afk command itself
    if not (message.text and message.text.startswith("/afk")):
        afk_info = await get_user_afk(user.id)
        if afk_info:
            now = time.time()
            elapsed = now - afk_info.get("afk_time", now)
            # Give a 5 second grace period to prevent instant triggers
            if elapsed > 5:
                await remove_user_afk(user.id)
                time_str = format_duration(elapsed)
                await message.reply_html(
                    f"<blockquote>✨ <b>ᴡᴇʟᴄᴏᴍᴇ ʙᴀᴄᴋ, {user.mention_html()}!</b>\n"
                    f"🕒 ʏᴏᴜ ᴡᴇʀᴇ ᴀᴡᴀʏ ғᴏʀ : <b>{time_str}</b></blockquote>"
                )

    # 2. Check if sender replied to an AFK user
    if message.reply_to_message and message.reply_to_message.from_user:
        replied_user = message.reply_to_message.from_user
        if replied_user.id != user.id and not replied_user.is_bot:
            afk_target = await get_user_afk(replied_user.id)
            if afk_target:
                elapsed = time.time() - afk_target.get("afk_time", time.time())
                time_str = format_duration(elapsed)
                reason = afk_target.get("reason", "Busy right now")
                await message.reply_html(
                    f"<blockquote>💤 <b>{replied_user.first_name} ɪs ᴄᴜʀʀᴇɴᴛʟʏ ᴀғᴋ!</b>\n"
                    f"🕒 <b>ᴀᴡᴀʏ ғᴏʀ :</b> <code>{time_str}</code>\n"
                    f"💭 <b>ʀᴇᴀsᴏɴ :</b> <i>{reason}</i></blockquote>"
                )

    # 3. Check if sender mentioned any users who are AFK
    if message.entities:
        for ent in message.entities:
            target_id = None
            if ent.type == MessageEntity.TEXT_MENTION and ent.user:
                target_id = ent.user.id
            if target_id and target_id != user.id:
                afk_target = await get_user_afk(target_id)
                if afk_target:
                    elapsed = time.time() - afk_target.get("afk_time", time.time())
                    time_str = format_duration(elapsed)
                    reason = afk_target.get("reason", "Busy right now")
                    await message.reply_html(
                        f"<blockquote>💤 <b>{ent.user.first_name} ɪs ᴄᴜʀʀᴇɴᴛʟʏ ᴀғᴋ!</b>\n"
                        f"🕒 <b>ᴀᴡᴀʏ ғᴏʀ :</b> <code>{time_str}</code>\n"
                        f"💭 <b>ʀᴇᴀsᴏɴ :</b> <i>{reason}</i></blockquote>"
                    )


def register_handlers(app: Application):
    app.add_handler(CommandHandler(["afk", "away"], afk_command))
    app.add_handler(
        MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL, afk_message_listener),
        group=5,
    )
