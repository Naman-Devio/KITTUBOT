# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Ping & System Monitor
"""

import time
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from KITTUBOT import START_TIME, __version__

__mod_name__ = "Ping"
__help__ = """
<blockquote>⚡ <b>ᴘɪɴɢ & sʏsᴛᴇᴍ:</b>
• <code>/ping</code> - ᴄʜᴇᴄᴋ ʙᴏᴛ ʟᴀᴛᴇɴᴄʏ & ᴏɴʟɪɴᴇ ᴜᴘᴛɪᴍᴇ</blockquote>
"""


def _get_readable_time(seconds: int) -> str:
    mins, sec = divmod(seconds, 60)
    hours, mins = divmod(mins, 60)
    days, hours = divmod(hours, 24)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins:
        parts.append(f"{mins}m")
    parts.append(f"{sec}s")
    return " ".join(parts)


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start = time.perf_counter()
    msg = await update.message.reply_html("⚡ <i>ᴘɪɴɢɪɴɢ ᴛᴇʟᴇɢʀᴀᴍ sᴇʀᴠᴇʀs...</i>")
    delta_ms = (time.perf_counter() - start) * 1000

    uptime = _get_readable_time(int(time.time() - START_TIME))

    await msg.edit_text(
        f"🐾 <b>ᴘᴏɴɢ!</b> <code>{delta_ms:.2f} ms</code>\n\n"
        f"<blockquote>⏳ <b>ᴜᴘᴛɪᴍᴇ :</b> <code>{uptime}</code>\n"
        f"📦 <b>ʙᴜɪʟᴅ  :</b> <code>ᴠ{__version__} sᴛᴀʙʟᴇ</code>\n"
        f"⚡ <b>ᴄᴏʀᴇ   :</b> <code>ᴘᴛʙ ᴀsʏɴᴄ ᴇɴɢɪɴᴇ</code></blockquote>",
        parse_mode="HTML",
    )


def register_handlers(app: Application):
    app.add_handler(CommandHandler("ping", ping_command))
