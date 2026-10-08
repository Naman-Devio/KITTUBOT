# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Paginated Help Plugin
Dynamic 3-column category grid with back/next navigation and aesthetic formatting.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from KITTUBOT.plugins import HELP_MODULES
from KITTUBOT.core.keyboards import get_paginated_help_keyboard
from KITTUBOT.core.fonts import to_small_caps, format_category_name

__mod_name__ = "Help"
__help__ = """
<blockquote>📖 <b>ᴄᴏᴍᴍᴀɴᴅ ʜᴜʙ & ᴅɪʀᴇᴄᴛᴏʀʏ</b>
ʙʀᴏᴡsᴇ ᴄᴀᴛᴇɢᴏʀɪᴇs ᴜsɪɴɢ ᴛʜᴇ ɪɴᴛᴇʀᴀᴄᴛɪᴠᴇ ʙᴜᴛᴛᴏɴs ʙᴇʟᴏᴡ.</blockquote>
"""


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    module_names = sorted(HELP_MODULES.keys())
    keyboard = get_paginated_help_keyboard(module_names, page=1)

    text = (
        "⊚ <b>ᴋɪᴛᴛᴜ ʙᴏᴛ — ᴄᴏᴍᴍᴀɴᴅ & ғᴇᴀᴛᴜʀᴇ ᴅɪʀᴇᴄᴛᴏʀʏ</b> ✨\n\n"
        "<blockquote>ᴄʟɪᴄᴋ ᴀɴʏ ᴄᴀᴛᴇɢᴏʀʏ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ ᴛᴏ ᴠɪᴇᴡ ᴀʟʟ ᴀᴠᴀɪʟᴀʙʟᴇ ᴄᴏᴍᴍᴀɴᴅs.\n"
        "ᴜsᴇ ᴛʜᴇ ᴀʀʀᴏᴡ ʙᴜᴛᴛᴏɴs ᴛᴏ ɴᴀᴠɪɢᴀᴛᴇ ᴘᴀɢᴇs!</blockquote>"
    )
    if update.callback_query:
        try:
            await update.callback_query.answer()
        except Exception:
            pass
        await update.callback_query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update.message.reply_html(text=text, reply_markup=keyboard)


async def help_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    page = int(query.data.split("_")[1])
    module_names = sorted(HELP_MODULES.keys())
    keyboard = get_paginated_help_keyboard(module_names, page=page)

    try:
        await query.edit_message_reply_markup(reply_markup=keyboard)
    except Exception:
        pass


async def help_module_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    parts = query.data.split("_")
    mod_name = parts[1]
    return_page = int(parts[2])

    found_key = next((k for k in HELP_MODULES if k.lower() == mod_name.lower()), mod_name)
    mod_help = HELP_MODULES.get(found_key, "No instructions available.")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data=f"helppage_{return_page}")]
    ])

    title = format_category_name(found_key)
    text = (
        f"<b>{title}</b>\n\n"
        f"{mod_help}"
    )

    try:
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except Exception:
        pass


def register_handlers(app: Application):
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(help_command, pattern=r"^kittu_help$"))
    app.add_handler(CallbackQueryHandler(help_page_callback, pattern=r"^helppage_\d+$"))
    app.add_handler(CallbackQueryHandler(help_module_callback, pattern=r"^helpmod_\w+_\d+$"))
