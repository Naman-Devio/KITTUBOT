# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Group TagAll & Admin Mention Plugin
Mentions active group members in batches with cancel support.
"""

import asyncio
from telegram import Update
from telegram.constants import ChatType, ChatMemberStatus
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from KITTUBOT.core.permissions import is_user_admin
from KITTUBOT.database.chats import track_chat_member, get_chat_active_members
from KITTUBOT import log

__mod_name__ = "TagAll"
__help__ = """
<blockquote>📢 <b>ᴍᴇɴᴛɪᴏɴ & ᴛᴀɢ ᴍᴇᴍʙᴇʀs:</b>
• <code>/tagall [message]</code> - ᴍᴇɴᴛɪᴏɴ ᴀᴄᴛɪᴠᴇ ᴍᴇᴍʙᴇʀs ɪɴ ʙᴀᴛᴄʜᴇs
• <code>/tagadmins [message]</code> - ᴛᴀɢ ᴀʟʟ ɢʀᴏᴜᴘ ᴀᴅᴍɪɴs
• <code>/cancel</code> - sᴛᴏᴘ ᴏɴɢᴏɪɴɢ ᴍᴇɴᴛɪᴏɴ ᴘʀᴏᴄᴇss

<i>⚠️ Admin only feature to prevent group spam.</i></blockquote>
"""

ACTIVE_TAG_TASKS: dict[int, bool] = {}


async def tagall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == ChatType.PRIVATE:
        await update.message.reply_html("⚠️ This command can only be used in groups!")
        return

    if not await is_user_admin(chat, user.id):
        await update.message.reply_html("⛔ <b>Admin only command!</b>")
        return

    if chat.id in ACTIVE_TAG_TASKS:
        await update.message.reply_html("⚠️ A mention process is already running! Type <code>/cancel</code> to stop it.")
        return

    notice = " ".join(context.args) if context.args else "Attention everyone! ✨"
    members = await get_chat_active_members(chat.id)

    if not members:
        await update.message.reply_html("⚠️ No recent active chat members recorded yet! Members are logged as they chat.")
        return

    ACTIVE_TAG_TASKS[chat.id] = True
    await update.message.reply_html(f"📢 <b>Starting mention sequence for {len(members)} members...</b>\n<i>Type /cancel anytime to abort.</i>")

    batch_size = 5
    try:
        for i in range(0, len(members), batch_size):
            if not ACTIVE_TAG_TASKS.get(chat.id, False):
                break

            chunk = members[i : i + batch_size]
            mentions = []
            for m in chunk:
                name = m.get("name", "Member")
                uid = m.get("id")
                mentions.append(f'<a href="tg://user?id={uid}">{name}</a>')

            text = f"📢 <b>{notice}</b>\n\n" + " • ".join(mentions)
            try:
                await context.bot.send_message(chat_id=chat.id, text=text, parse_mode="HTML")
            except Exception as e:
                log.warning(f"Failed to send tag batch: {e}")

            await asyncio.sleep(2.5)
    finally:
        ACTIVE_TAG_TASKS.pop(chat.id, None)


async def tagadmins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == ChatType.PRIVATE:
        await update.message.reply_html("⚠️ This command can only be used in groups!")
        return

    notice = " ".join(context.args) if context.args else "Admins attention needed! 🚨"

    try:
        admins = await chat.get_administrators()
        mentions = []
        for admin in admins:
            if not admin.user.is_bot:
                mentions.append(f'<a href="tg://user?id={admin.user.id}">{admin.user.first_name}</a>')

        if not mentions:
            await update.message.reply_html("No human admins found.")
            return

        text = f"🚨 <b>{notice}</b>\n\n" + " • ".join(mentions)
        await update.message.reply_html(text)
    except Exception as e:
        await update.message.reply_html(f"❌ Failed to fetch admins: {e}")


async def cancel_tag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not await is_user_admin(chat, user.id):
        await update.message.reply_html("⛔ <b>Admin only command!</b>")
        return

    if chat.id in ACTIVE_TAG_TASKS:
        ACTIVE_TAG_TASKS[chat.id] = False
        ACTIVE_TAG_TASKS.pop(chat.id, None)
        await update.message.reply_html("🛑 <b>Mention process stopped!</b>")
    else:
        await update.message.reply_html("ℹ️ No active mention process running.")


async def chat_member_tracker_listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if chat and chat.type != ChatType.PRIVATE and user and not user.is_bot:
        await track_chat_member(chat.id, user)


def register_handlers(app: Application):
    app.add_handler(CommandHandler(["tagall", "mentionall"], tagall_command))
    app.add_handler(CommandHandler(["tagadmins", "admins"], tagadmins_command))
    app.add_handler(CommandHandler("cancel", cancel_tag_command))

    # Tracks active members in background
    app.add_handler(
        MessageHandler(filters.ChatType.GROUPS & filters.ALL & ~filters.StatusUpdate.ALL, chat_member_tracker_listener),
        group=20,
    )
