# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Start Plugin
Signature cinematic animation, full-screen effects & menus.
"""

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from KITTUBOT.database.users import ensure_user
from KITTUBOT.core.animations import play_start_animation
from KITTUBOT.core.keyboards import get_main_menu_keyboard
from KITTUBOT.config import config
from KITTUBOT.core.fonts import to_small_caps

__mod_name__ = "General"
__help__ = """
<blockquote>🐾 <b>ɢᴇɴᴇʀᴀʟ ᴄᴏᴍᴍᴀɴᴅs:</b>
• <code>/start</code> - ʟᴀᴜɴᴄʜ ᴛʜᴇ ʙᴏᴛ & ᴠɪᴇᴡ ᴍᴀɪɴ ᴍᴇɴᴜ
• <code>/help</code> - ɪɴᴛᴇʀᴀᴄᴛɪᴠᴇ 3-ᴄᴏʟᴜᴍɴ ᴄᴏᴍᴍᴀɴᴅ ʜᴜʙ
• <code>/ping</code> - ᴄʜᴇᴄᴋ ʟᴀᴛᴇɴᴄʏ & ᴏɴʟɪɴᴇ ᴜᴘᴛɪᴍᴇ</blockquote>
"""


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    # Persist user asynchronously
    await ensure_user(user)

    if chat.type == "private":
        await play_start_animation(update, context)
    else:
        # Group greeting
        bot_info = await context.bot.get_me()
        bot_title = to_small_caps(config.BOT_NAME)
        await update.message.reply_html(
            f"⊚ <b>ʜєʏ ㅤ- {user.mention_html()}</b> 💢 ✨\n"
            f"💮 <b>ʏᴏᴜ ᴀʀᴇ ᴜsɪɴɢ ˹ {bot_title} ˼</b>\n\n"
            f"<blockquote>ᴛʜᴇ ᴜʟᴛɪᴍᴀᴛᴇ ᴅᴇsᴛɪɴᴀᴛɪᴏɴ ғᴏʀ ᴍᴜʟᴛɪᴘʟᴀʏᴇʀ ɢᴀᴍᴇs & ɢʀᴏᴜᴘ ᴍᴀɴᴀɢᴇᴍᴇɴᴛ.</blockquote>\n\n"
            f"🎋 <i>ᴛʏᴘᴇ /game ᴛᴏ ʙᴀᴛᴛʟᴇ ᴏʀ /economy ᴛᴏ ᴄʜᴇᴄᴋ ᴄᴏɪɴs.</i>",
            reply_markup=get_main_menu_keyboard(bot_info.username),
        )


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    bot_info = await context.bot.get_me()
    user = update.effective_user
    bot_title = to_small_caps(config.BOT_NAME)

    text = (
        f"⊚ <b>ᴍᴀɪɴ ᴍᴇɴᴜ — ˹ {bot_title} ˼</b> ✨\n\n"
        f"<blockquote>ʜᴇʏ {user.mention_html()}, ᴄʜᴏᴏsᴇ ᴀɴ ᴏᴘᴛɪᴏɴ ʙᴇʟᴏᴡ ᴛᴏ ᴘʟᴀʏ ɢᴀᴍᴇs, ᴇᴀʀɴ ᴄᴏɪɴs, "
        f"ᴏʀ ᴍᴀɴᴀɢᴇ ʏᴏᴜʀ ᴄᴏᴍᴍᴜɴɪᴛʏ!</blockquote>"
    )
    try:
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(bot_info.username),
        )
    except Exception:
        pass


async def close_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer("Closed!")
        await query.message.delete()
    except Exception:
        pass


async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass


def register_handlers(app: Application):
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern=r"^main_menu$"))
    app.add_handler(CallbackQueryHandler(close_menu_callback, pattern=r"^close_menu$"))
    app.add_handler(CallbackQueryHandler(noop_callback, pattern=r"^noop$"))
