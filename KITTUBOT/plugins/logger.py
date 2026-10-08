# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Channel Logger Plugin
Logs bot joins, leaves, new user starts, and crash/error reports to LOGGER_ID.
"""

import time
import html
import traceback
from datetime import datetime
import pytz
from telegram import Update, ChatMemberUpdated, ChatMember
from telegram.constants import ChatMemberStatus
from telegram.ext import Application, CommandHandler, ChatMemberHandler, ContextTypes

from KITTUBOT.config import config
from KITTUBOT import log

__mod_name__ = "Logger"
__help__ = """
<blockquote>📋 <b>ᴄʜᴀɴɴᴇʟ ʟᴏɢɢᴇʀ:</b>
• <code>/logtest</code> - sᴇɴᴅ ᴀ ᴛᴇsᴛ ʟᴏɢ ᴍᴇssᴀɢᴇ ᴛᴏ ᴛʜᴇ ʟᴏɢɢᴇʀ ᴄʜᴀɴɴᴇʟ (ᴏᴡɴᴇʀ ᴏɴʟʏ)
• ᴀᴜᴛᴏ-ʟᴏɢs: ɴᴇᴡ ᴜsᴇʀ sᴛᴀʀᴛs, ɢʀᴏᴜᴘ ᴊᴏɪɴs/ʟᴇᴀᴠᴇs, ᴇʀʀᴏʀ ᴄʀᴀsʜᴇs</blockquote>
"""

IST = pytz.timezone("Asia/Kolkata")


def get_current_time() -> str:
    return datetime.now(IST).strftime("%d-%b-%Y %I:%M:%S %p IST")


async def send_log_message(bot, text: str) -> bool:
    """Dispatches a formatted HTML card to LOGGER_ID safely."""
    logger_id = config.LOGGER_ID
    if not logger_id:
        return False

    try:
        await bot.send_message(
            chat_id=logger_id,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return True
    except Exception as e:
        log.warning(f"Failed to deliver log to channel ({logger_id}): {e}")
        return False


async def log_user_start(bot, user, chat):
    """Dispatches a #NEW_USER_START notification."""
    t_str = get_current_time()
    username_str = f"@{user.username}" if user.username else "None"
    text = (
        "👤 <b>#NEW_USER_START</b> 🌸\n\n"
        f"<blockquote>👤 <b>ᴜsᴇʀ :</b> {user.mention_html()}\n"
        f"🆔 <b>ᴜsᴇʀ ɪᴅ :</b> <code>{user.id}</code>\n"
        f"📛 <b>ᴜsᴇʀɴᴀᴍᴇ :</b> {username_str}\n"
        f"💬 <b>ᴄʜᴀᴛ ᴛʏᴘᴇ :</b> Private DM\n"
        f"📅 <b>ᴛɪᴍᴇ :</b> <code>{t_str}</code></blockquote>"
    )
    await send_log_message(bot, text)


async def log_bot_added_group(bot, chat, user, member_count: int = 0):
    """Dispatches a #BOT_ADDED_TO_GROUP notification."""
    t_str = get_current_time()
    user_mention = user.mention_html() if user else "Unknown User"
    user_id_str = str(user.id) if user else "Unknown"
    user_name_str = f"@{user.username}" if user and user.username else "None"
    count_str = f"{member_count:,}" if member_count else "Unknown"

    text = (
        "📥 <b>#BOT_ADDED_TO_GROUP</b> 🎌✨\n\n"
        f"<blockquote>🏷️ <b>ɢʀᴏᴜᴘ ᴛɪᴛʟᴇ :</b> <b>{html.escape(chat.title or 'Unknown')}</b>\n"
        f"🆔 <b>ɢʀᴏᴜᴘ ɪᴅ :</b> <code>{chat.id}</code>\n"
        f"👥 <b>ᴍᴇᴍʙᴇʀs ᴄᴏᴜɴᴛ :</b> <code>{count_str}</code>\n"
        f"👤 <b>ᴀᴅᴅᴇᴅ ʙʏ :</b> {user_mention} (<code>{user_id_str}</code>)\n"
        f"📛 <b>ᴀᴅᴍɪɴ ᴜsᴇʀɴᴀᴍᴇ :</b> {user_name_str}\n"
        f"📅 <b>ᴛɪᴍᴇ :</b> <code>{t_str}</code></blockquote>"
    )
    await send_log_message(bot, text)


async def log_bot_left_group(bot, chat, user):
    """Dispatches a #BOT_REMOVED_FROM_GROUP notification."""
    t_str = get_current_time()
    user_mention = user.mention_html() if user else "Unknown User"
    user_id_str = str(user.id) if user else "Unknown"

    text = (
        "📤 <b>#BOT_REMOVED_FROM_GROUP</b> 🛑\n\n"
        f"<blockquote>🏷️ <b>ɢʀᴏᴜᴘ ᴛɪᴛʟᴇ :</b> <b>{html.escape(chat.title or 'Unknown')}</b>\n"
        f"🆔 <b>ɢʀᴏᴜᴘ ɪᴅ :</b> <code>{chat.id}</code>\n"
        f"👤 <b>ʀᴇᴍᴏᴠᴇᴅ ʙʏ :</b> {user_mention} (<code>{user_id_str}</code>)\n"
        f"📅 <b>ᴛɪᴍᴇ :</b> <code>{t_str}</code></blockquote>"
    )
    await send_log_message(bot, text)


async def log_crash_error(bot, update, error: Exception):
    """Formats and dispatches unhandled exception crash report."""
    t_str = get_current_time()
    error_name = type(error).__name__
    error_msg = html.escape(str(error)[:200])

    chat_id = "N/A"
    chat_title = "N/A"
    user_id = "N/A"
    user_name = "N/A"

    if update and hasattr(update, "effective_chat") and update.effective_chat:
        chat_id = str(update.effective_chat.id)
        chat_title = html.escape(update.effective_chat.title or update.effective_chat.type)
    if update and hasattr(update, "effective_user") and update.effective_user:
        user_id = str(update.effective_user.id)
        user_name = html.escape(update.effective_user.first_name)

    # Format traceback snippet
    tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
    tb_text = "".join(tb_lines)
    # Truncate safely
    if len(tb_text) > 3000:
        tb_text = tb_text[-3000:]
    tb_escaped = html.escape(tb_text)

    text = (
        "⚠️ <b>#CRASH_ALERT / #ERROR_LOG</b> 💥\n\n"
        f"<blockquote>💥 <b>ᴇʀʀᴏʀ :</b> <code>{error_name}: {error_msg}</code>\n"
        f"📍 <b>ᴄʜᴀᴛ :</b> <code>{chat_id}</code> ({chat_title})\n"
        f"👤 <b>ᴜsᴇʀ :</b> <code>{user_id}</code> ({user_name})\n"
        f"📅 <b>ᴛɪᴍᴇ :</b> <code>{t_str}</code></blockquote>\n\n"
        f"<pre><code class=\"language-python\">{tb_escaped}</code></pre>"
    )
    await send_log_message(bot, text)


async def chat_member_updated_listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Monitors additions and removals of Kittu Bot in groups."""
    result: ChatMemberUpdated = update.my_chat_member
    if not result:
        return

    chat = result.chat
    actor = result.from_user

    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status

    active_statuses = [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]
    inactive_statuses = [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]

    # Added to group
    if new_status in active_statuses and old_status not in active_statuses:
        member_count = 0
        try:
            member_count = await chat.get_member_count()
        except Exception:
            pass
        await log_bot_added_group(context.bot, chat, actor, member_count)

    # Removed from group
    elif new_status in inactive_statuses and old_status in active_statuses:
        await log_bot_left_group(context.bot, chat, actor)


async def logtest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a test log to verify channel permissions."""
    user = update.effective_user
    if user.id != config.OWNER_ID and user.id not in config.SUDO_IDS:
        return

    sent = await send_log_message(
        context.bot,
        f"✅ <b>#LOGGER_TEST_SUCCESSFUL</b> 🐾\n\n"
        f"<blockquote>Logger channel configured properly!\n"
        f"• <b>Logger ID:</b> <code>{config.LOGGER_ID}</code>\n"
        f"• <b>Triggered by:</b> {user.mention_html()}\n"
        f"• <b>Time:</b> <code>{get_current_time()}</code></blockquote>"
    )
    if sent:
        await update.message.reply_html(f"✅ Successfully dispatched test log to <code>{config.LOGGER_ID}</code>!")
    else:
        await update.message.reply_html(
            f"❌ Failed to send log to <code>{config.LOGGER_ID}</code>. "
            "Make sure the bot is added as an <b>Admin</b> with <i>Post Messages</i> permission in your logger channel!"
        )


def register_handlers(app: Application):
    # Monitor bot being added/removed in groups
    app.add_handler(ChatMemberHandler(chat_member_updated_listener, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(CommandHandler("logtest", logtest_command))
