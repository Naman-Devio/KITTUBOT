# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Chatbot & AI Companion Plugin
Expressive, Hinglish AI companion that talks naturally in DMs and group mentions.
"""

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from KITTUBOT.core.ai_brain import ask_kittu
from KITTUBOT.database.users import ensure_user

__mod_name__ = "Chatbot"
__help__ = """
<blockquote>🤖 <b>ᴀɪ ʙᴇsᴛɪᴇ ᴄʜᴀᴛʙᴏᴛ:</b>
• ᴛᴀʟᴋ ɪɴ ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀᴛ ᴏʀ ᴍᴇɴᴛɪᴏɴ <b>ᴋɪᴛᴛᴜ</b> ɪɴ ɢʀᴏᴜᴘs!
• <code>/ask [query]</code> - ᴀsᴋ ᴋɪᴛᴛᴜ ᴀɴʏ ǫᴜᴇsᴛɪᴏɴ ᴅɪʀᴇᴄᴛʟʏ</blockquote>
"""


async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_html("🐾 Haan bolo! Kya puchna hai? Example: <code>/ask who is the best?</code>")
        return

    query = " ".join(context.args)
    user = update.effective_user
    await ensure_user(user)

    reply_text = await ask_kittu(query, user.first_name)
    await update.message.reply_text(reply_text)


async def handle_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text or message.text.startswith("/"):
        return

    user = update.effective_user
    chat = update.effective_chat
    bot_info = await context.bot.get_me()

    text_lower = message.text.lower()
    is_private = chat.type == "private"
    is_reply_to_bot = (
        message.reply_to_message
        and message.reply_to_message.from_user
        and message.reply_to_message.from_user.id == bot_info.id
    )
    is_mentioned = "kittu" in text_lower or f"@{bot_info.username.lower()}" in text_lower or "किट्टू" in message.text

    if is_private or is_reply_to_bot or is_mentioned:
        await ensure_user(user)
        try:
            await context.bot.send_chat_action(chat_id=chat.id, action="typing")
        except Exception:
            pass
        reply_text = await ask_kittu(message.text, user.first_name)
        await message.reply_text(reply_text)


def register_handlers(app: Application):
    app.add_handler(CommandHandler("ask", ask_command))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat_message),
        group=20,
    )
