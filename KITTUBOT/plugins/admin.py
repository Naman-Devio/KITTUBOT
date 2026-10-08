# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Sudo & Administrator Plugin
Management, coin grants, user moderation & global broadcast.
"""

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from KITTUBOT.config import config
from KITTUBOT.core.filters import sudo_filter
from KITTUBOT.database.users import ensure_user, update_balance
from KITTUBOT.database import users_col

__mod_name__ = "Admin"
__help__ = """
<blockquote>👑 <b>sᴜᴅᴏ & ᴅᴇᴠᴇʟᴏᴘᴇʀ ᴄᴏɴᴛʀᴏʟs:</b>
• <code>/sudo</code> - ᴠɪᴇᴡ sᴜᴅᴏ ᴄᴏɴᴛʀᴏʟ ᴘᴀɴᴇʟ
• <code>/addcoins [amt]</code> - (ʀᴇᴘʟʏ) ɢʀᴀɴᴛ ᴄᴏɪɴs
• <code>/rmcoins [amt]</code> - (ʀᴇᴘʟʏ) ᴅᴇᴅᴜᴄᴛ ᴄᴏɪɴs
• <code>/broadcast [txt]</code> - ᴀɴɴᴏᴜɴᴄᴇ ᴛᴏ ᴀʟʟ ᴜsᴇʀs
• <code>/sudolist</code> - ᴠɪᴇᴡ ʙᴏᴛ ᴏᴘᴇʀᴀᴛᴏʀs</blockquote>
"""


async def sudo_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👑 <b>ᴋɪᴛᴛᴜ sᴜᴅᴏ ᴏᴘᴇʀᴀᴛɪᴏɴs ᴄᴇɴᴛᴇʀ</b>\n\n"
        "<blockquote>• <code>/addcoins [amount]</code> — Grant coins to user\n"
        "• <code>/rmcoins [amount]</code> — Deduct coins from user\n"
        "• <code>/sudolist</code> — View authorized sudo IDs\n"
        "• <code>/broadcast [message]</code> — Global announcement</blockquote>"
    )
    await update.message.reply_html(text)


async def addcoins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply = update.message.reply_to_message
    if not reply or not reply.from_user:
        await update.message.reply_html("⚠️ Reply to a user to grant coins!")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_html("⚠️ Provide the amount! E.g. <code>/addcoins 50000</code>")
        return

    amount = int(context.args[0])
    target = reply.from_user
    await ensure_user(target)
    new_bal = await update_balance(target.id, amount)

    await update.message.reply_html(
        f"✅ <b>ɢʀᴀɴᴛᴇᴅ {amount:,} ᴄᴏɪɴs</b> to {target.mention_html()}!\n"
        f"New balance: <code>{new_bal:,}</code>"
    )


async def rmcoins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply = update.message.reply_to_message
    if not reply or not reply.from_user:
        await update.message.reply_html("⚠️ Reply to a user to deduct coins!")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_html("⚠️ Provide amount! E.g. <code>/rmcoins 5000</code>")
        return

    amount = int(context.args[0])
    target = reply.from_user
    await ensure_user(target)
    new_bal = await update_balance(target.id, -amount)

    await update.message.reply_html(
        f"🔻 <b>ᴅᴇᴅᴜᴄᴛᴇᴅ {amount:,} ᴄᴏɪɴs</b> from {target.mention_html()}!\n"
        f"New balance: <code>{new_bal:,}</code>"
    )


async def sudolist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "👑 <b>ᴀᴜᴛʜᴏʀɪᴢᴇᴅ sᴜᴅᴏ ᴏᴘᴇʀᴀᴛᴏʀs:</b>\n\n<blockquote>"
    for s_id in config.SUDO_IDS:
        text += f"• <code>{s_id}</code>\n"
    text += "</blockquote>"
    await update.message.reply_html(text)


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_html("⚠️ Provide message to broadcast! E.g. <code>/broadcast Hello everyone!</code>")
        return

    msg_text = " ".join(context.args)
    cursor = users_col.find({})
    count = 0

    status = await update.message.reply_html("📢 <i>Broadcasting message...</i>")

    async for u in cursor:
        try:
            await context.bot.send_message(chat_id=u["user_id"], text=f"📢 <b>Announcement:</b>\n\n{msg_text}", parse_mode="HTML")
            count += 1
        except Exception:
            pass

    await status.edit_text(f"✅ Broadcast finished! Sent to <b>{count} users</b>.", parse_mode="HTML")


def register_handlers(app: Application):
    app.add_handler(CommandHandler("sudo", sudo_panel, filters=sudo_filter))
    app.add_handler(CommandHandler("addcoins", addcoins_command, filters=sudo_filter))
    app.add_handler(CommandHandler("rmcoins", rmcoins_command, filters=sudo_filter))
    app.add_handler(CommandHandler("sudolist", sudolist_command, filters=sudo_filter))
    app.add_handler(CommandHandler("broadcast", broadcast_command, filters=sudo_filter))
