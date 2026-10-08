# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Chat Locks & Media Restrictions Plugin
Enforces granular group restrictions: stickers, links, forwards, media, gifs, bots, audio.
"""

from telegram import Update, MessageEntity
from telegram.constants import ChatType
from telegram.ext import Application, CommandHandler, MessageHandler, ChatMemberHandler, ContextTypes, filters
from KITTUBOT.core.permissions import is_user_admin, can_bot_delete
from KITTUBOT.database.locks import get_chat_locks, set_chat_lock, VALID_LOCK_TYPES
from KITTUBOT import log

__mod_name__ = "Locks"
__help__ = """
<blockquote>🔒 <b>ɢʀᴏᴜᴘ sᴇᴄᴜʀɪᴛʏ ʟᴏᴄᴋs:</b>
• <code>/lock [type]</code> - ʟᴏᴄᴋ ᴀ sᴘᴇᴄɪғɪᴄ ᴍᴇᴅɪᴀ/ᴍᴇssᴀɢᴇ ᴛʏᴘᴇ
• <code>/unlock [type]</code> - ᴜɴʟᴏᴄᴋ ᴀ ᴍᴇᴅɪᴀ/ᴍᴇssᴀɢᴇ ᴛʏᴘᴇ
• <code>/locks</code> - ᴠɪᴇᴡ ᴀᴄᴛɪᴠᴇ ʟᴏᴄᴋs ɪɴ ᴛʜɪs ᴄʜᴀᴛ

<b>ᴛʏᴘᴇs :</b> <code>stickers</code>, <code>links</code>, <code>forwards</code>, <code>media</code>, <code>gifs</code>, <code>audio</code>, <code>bots</code>, <code>games</code>, <code>all</code></blockquote>
"""


async def lock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if chat.type == ChatType.PRIVATE:
        await update.message.reply_html("⚠️ Locks only work in group chats!")
        return

    if not await is_user_admin(chat, user.id):
        await update.message.reply_html("⛔ <b>Admin only command!</b>")
        return

    if not context.args:
        await update.message.reply_html(
            "⚠️ <b>Specify what to lock!</b>\n"
            f"Available types: <code>{', '.join(sorted(VALID_LOCK_TYPES))}</code> or <code>all</code>"
        )
        return

    target = context.args[0].lower().strip()
    if target == "all":
        for t in VALID_LOCK_TYPES:
            await set_chat_lock(chat.id, t, True)
        await update.message.reply_html("🔒 <b>All chat locks have been activated!</b>")
        return

    if target not in VALID_LOCK_TYPES:
        await update.message.reply_html(f"❌ Invalid lock type! Available: <code>{', '.join(sorted(VALID_LOCK_TYPES))}</code>")
        return

    await set_chat_lock(chat.id, target, True)
    await update.message.reply_html(f"🔒 <b>Locked <code>{target}</code> in this chat!</b>")


async def unlock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if chat.type == ChatType.PRIVATE:
        await update.message.reply_html("⚠️ Locks only work in group chats!")
        return

    if not await is_user_admin(chat, user.id):
        await update.message.reply_html("⛔ <b>Admin only command!</b>")
        return

    if not context.args:
        await update.message.reply_html(
            "⚠️ <b>Specify what to unlock!</b>\n"
            f"Available types: <code>{', '.join(sorted(VALID_LOCK_TYPES))}</code> or <code>all</code>"
        )
        return

    target = context.args[0].lower().strip()
    if target == "all":
        for t in VALID_LOCK_TYPES:
            await set_chat_lock(chat.id, t, False)
        await update.message.reply_html("🔓 <b>All chat locks have been released!</b>")
        return

    if target not in VALID_LOCK_TYPES:
        await update.message.reply_html(f"❌ Invalid lock type! Available: <code>{', '.join(sorted(VALID_LOCK_TYPES))}</code>")
        return

    await set_chat_lock(chat.id, target, False)
    await update.message.reply_html(f"🔓 <b>Unlocked <code>{target}</code> in this chat!</b>")


async def locks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == ChatType.PRIVATE:
        await update.message.reply_html("⚠️ Locks only work in group chats!")
        return

    active_locks = await get_chat_locks(chat.id)

    text = f"🔐 <b>ᴄʜᴀᴛ ʟᴏᴄᴋ sᴛᴀᴛᴜs : {chat.title}</b>\n\n<blockquote>"
    for lock in sorted(VALID_LOCK_TYPES):
        status = "🔒 Locked" if lock in active_locks else "🔓 Open"
        text += f"• <b>{lock.title()}</b> : <code>{status}</code>\n"
    text += "</blockquote>"

    await update.message.reply_html(text)


def has_link(message) -> bool:
    """Checks if message text or caption contains URLs."""
    entities = message.entities or message.caption_entities or []
    for ent in entities:
        if ent.type in [MessageEntity.URL, MessageEntity.TEXT_LINK]:
            return True
    return False


async def lock_message_listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enforces locks in group chats."""
    chat = update.effective_chat
    message = update.effective_message
    user = update.effective_user

    if not chat or chat.type == ChatType.PRIVATE or not message or not user:
        return

    # Admins bypass all locks
    if await is_user_admin(chat, user.id):
        return

    active_locks = await get_chat_locks(chat.id)
    if not active_locks:
        return

    should_delete = False
    triggered_lock = ""

    # Check stickers
    if "stickers" in active_locks and message.sticker:
        should_delete = True
        triggered_lock = "stickers"

    # Check links
    elif "links" in active_locks and has_link(message):
        should_delete = True
        triggered_lock = "links"

    # Check forwards
    elif "forwards" in active_locks and (message.forward_origin or message.forward_date):
        should_delete = True
        triggered_lock = "forwards"

    # Check gifs
    elif "gifs" in active_locks and message.animation:
        should_delete = True
        triggered_lock = "gifs"

    # Check audio
    elif "audio" in active_locks and (message.audio or message.voice):
        should_delete = True
        triggered_lock = "audio"

    # Check media (photo, video, document)
    elif "media" in active_locks and (message.photo or message.video or message.document):
        should_delete = True
        triggered_lock = "media"

    # Check games
    elif "games" in active_locks and message.game:
        should_delete = True
        triggered_lock = "games"

    if should_delete:
        try:
            bot_id = context.bot.id
            if await can_bot_delete(chat, bot_id):
                await message.delete()
        except Exception as e:
            log.warning(f"Could not delete message for lock {triggered_lock}: {e}")


def register_handlers(app: Application):
    app.add_handler(CommandHandler("lock", lock_command))
    app.add_handler(CommandHandler("unlock", unlock_command))
    app.add_handler(CommandHandler("locks", locks_command))

    # Lock listener runs early on group messages
    app.add_handler(
        MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, lock_message_listener),
        group=2,
    )
