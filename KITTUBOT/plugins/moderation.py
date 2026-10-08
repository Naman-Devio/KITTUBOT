# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Group Moderation & Administration Engine
Enterprise-grade moderation tools: Ban, Unban, Mute, Unmute, Kick, Strike Warnings,
Bulk Message Purge, Pinning, and Customizable Welcome Greetings.
"""

import time
import re
from datetime import datetime, timedelta
from telegram import Update, ChatPermissions, ChatMemberUpdated
from telegram.ext import (
    Application,
    CommandHandler,
    ChatMemberHandler,
    ContextTypes,
    filters,
)
from KITTUBOT.config import config
from KITTUBOT.core.permissions import is_user_admin, can_bot_restrict, can_bot_delete
from KITTUBOT.database import warns_col, chats_col

__mod_name__ = "Moderation"
__help__ = """
<blockquote>🛡️ <b>ɢʀᴏᴜᴘ ᴍᴏᴅᴇʀᴀᴛɪᴏɴ & ᴛᴏᴏʟs:</b>
• <code>/ban [reason]</code> - (ʀᴇᴘʟʏ) ʙᴀɴ ᴜsᴇʀ ғʀᴏᴍ ɢʀᴏᴜᴘ
• <code>/unban</code> - (ʀᴇᴘʟʏ|ɪᴅ) ᴜɴʙᴀɴ ᴀ ᴍᴇᴍʙᴇʀ
• <code>/mute [time]</code> - (ʀᴇᴘʟʏ) ᴍᴜᴛᴇ ᴍᴇᴍʙᴇʀ (ᴇ.ɢ. 10m, 2h)
• <code>/unmute</code> - (ʀᴇᴘʟʏ) ʀᴇsᴛᴏʀᴇ ᴠᴏɪᴄᴇ
• <code>/kick</code> - (ʀᴇᴘʟʏ) ᴋɪᴄᴋ ᴜsᴇʀ ғʀᴏᴍ ᴄʜᴀᴛ
• <code>/warn [reason]</code> - (ʀᴇᴘʟʏ) ɪssᴜᴇ sᴛʀɪᴋᴇ (3 ᴡᴀʀɴs = ʙᴀɴ)
• <code>/warns</code> - (ʀᴇᴘʟʏ) ᴄʜᴇᴄᴋ sᴛʀɪᴋᴇ ᴄᴏᴜɴᴛ
• <code>/rmwarn</code> - (ʀᴇᴘʟʏ) ʀᴇsᴇᴛ ᴜsᴇʀ ᴡᴀʀɴɪɴɢs
• <code>/purge</code> - (ʀᴇᴘʟʏ) ʙᴜʟᴋ ᴅᴇʟᴇᴛᴇ ᴍᴇssᴀɢᴇs
• <code>/del</code> - (ʀᴇᴘʟʏ) ᴅᴇʟᴇᴛᴇ ᴀ sɪɴɢʟᴇ ᴍᴇssᴀɢᴇ
• <code>/pin</code> & <code>/unpin</code> - (ʀᴇᴘʟʏ) ᴘɪɴ ᴀɴɴᴏᴜɴᴄᴇᴍᴇɴᴛ
• <code>/setwelcome [txt]</code> - ᴄᴜsᴛᴏᴍ ᴡᴇʟᴄᴏᴍᴇ ᴍᴇssᴀɢᴇ
• <code>/welcome [on|off]</code> - ᴛᴏɢɢʟᴇ ɢʀᴏᴜᴘ ᴡᴇʟᴄᴏᴍᴇs</blockquote>
"""


def parse_time_duration(time_str: str) -> timedelta | None:
    """Parses strings like 10m, 2h, 1d into timedelta."""
    match = re.match(r"^(\d+)([smhd])$", time_str.lower().strip())
    if not match:
        return None
    val, unit = int(match.group(1)), match.group(2)
    if unit == "s":
        return timedelta(seconds=val)
    elif unit == "m":
        return timedelta(minutes=val)
    elif unit == "h":
        return timedelta(hours=val)
    elif unit == "d":
        return timedelta(days=val)
    return None


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    bot_info = await context.bot.get_me()

    if chat.type == "private":
        await update.message.reply_html("⚠️ This command is only for group chats!")
        return

    if not await is_user_admin(chat, user.id):
        await update.message.reply_html("⚠️ Only administrators can use /ban!")
        return

    if not await can_bot_restrict(chat, bot_info.id):
        await update.message.reply_html("❌ I need <b>Ban Users</b> admin permissions to execute this!")
        return

    reply = update.message.reply_to_message
    if not reply or not reply.from_user:
        await update.message.reply_html("⚠️ <b>Reply to the member</b> you wish to ban!")
        return

    target = reply.from_user
    if target.id == user.id:
        await update.message.reply_html("😂 You cannot ban yourself!")
        return
    if target.id == bot_info.id:
        await update.message.reply_html("😂 I cannot ban myself!")
        return
    if await is_user_admin(chat, target.id):
        await update.message.reply_html("🛡️ You cannot ban a fellow administrator!")
        return

    reason = " ".join(context.args) if context.args else "No reason specified"

    try:
        await chat.ban_member(target.id)
        await update.message.reply_html(
            f"🚫 <b>ᴍᴇᴍʙᴇʀ ʙᴀɴɴᴇᴅ!</b>\n\n"
            f"<blockquote>👤 <b>User:</b> {target.mention_html()} (<code>{target.id}</code>)\n"
            f"👮 <b>Admin:</b> {user.mention_html()}\n"
            f"📝 <b>Reason:</b> <i>{reason}</i></blockquote>"
        )
    except Exception as e:
        await update.message.reply_html(f"❌ Failed to ban member: <code>{e}</code>")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    bot_info = await context.bot.get_me()

    if chat.type == "private":
        return

    if not await is_user_admin(chat, user.id):
        await update.message.reply_html("⚠️ Only administrators can use /unban!")
        return

    reply = update.message.reply_to_message
    target_id = None
    target_name = "User"

    if reply and reply.from_user:
        target_id = reply.from_user.id
        target_name = reply.from_user.first_name
    elif context.args and context.args[0].isdigit():
        target_id = int(context.args[0])
        target_name = f"<code>{target_id}</code>"
    else:
        await update.message.reply_html("⚠️ Reply to a message or provide user ID: <code>/unban 12345678</code>")
        return

    try:
        await chat.unban_member(target_id)
        await update.message.reply_html(
            f"✅ <b>ᴍᴇᴍʙᴇʀ ᴜɴʙᴀɴɴᴇᴅ!</b>\n\n"
            f"<blockquote>👤 <b>Target:</b> {target_name}\n"
            f"👮 <b>Admin:</b> {user.mention_html()}</blockquote>"
        )
    except Exception as e:
        await update.message.reply_html(f"❌ Failed to unban: <code>{e}</code>")


async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    bot_info = await context.bot.get_me()

    if chat.type == "private":
        return

    if not await is_user_admin(chat, user.id):
        await update.message.reply_html("⚠️ Only administrators can use /mute!")
        return

    if not await can_bot_restrict(chat, bot_info.id):
        await update.message.reply_html("❌ I need <b>Restrict Users</b> admin permission to mute!")
        return

    reply = update.message.reply_to_message
    if not reply or not reply.from_user:
        await update.message.reply_html("⚠️ <b>Reply to the user</b> you want to mute!")
        return

    target = reply.from_user
    if await is_user_admin(chat, target.id):
        await update.message.reply_html("🛡️ You cannot mute an administrator!")
        return

    duration = None
    time_str = "Indefinitely"
    if context.args:
        td = parse_time_duration(context.args[0])
        if td:
            duration = datetime.utcnow() + td
            time_str = context.args[0]

    try:
        permissions = ChatPermissions(
            can_send_messages=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
        )
        await chat.restrict_member(target.id, permissions=permissions, until_date=duration)
        await update.message.reply_html(
            f"🤐 <b>ᴍᴇᴍʙᴇʀ ᴍᴜᴛᴇᴅ!</b>\n\n"
            f"<blockquote>👤 <b>User:</b> {target.mention_html()}\n"
            f"👮 <b>Admin:</b> {user.mention_html()}\n"
            f"⏳ <b>Duration:</b> <code>{time_str}</code></blockquote>"
        )
    except Exception as e:
        await update.message.reply_html(f"❌ Failed to mute member: <code>{e}</code>")


async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        return

    if not await is_user_admin(chat, user.id):
        await update.message.reply_html("⚠️ Only administrators can use /unmute!")
        return

    reply = update.message.reply_to_message
    if not reply or not reply.from_user:
        await update.message.reply_html("⚠️ <b>Reply to the user</b> to unmute them!")
        return

    target = reply.from_user
    try:
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_audios=True,
            can_send_documents=True,
            can_send_photos=True,
            can_send_videos=True,
            can_send_video_notes=True,
            can_send_voice_notes=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
        )
        await chat.restrict_member(target.id, permissions=permissions)
        await update.message.reply_html(
            f"🔊 <b>ᴍᴇᴍʙᴇʀ ᴜɴᴍᴜᴛᴇᴅ!</b>\n\n"
            f"<blockquote>{target.mention_html()} is now free to chat again!</blockquote>"
        )
    except Exception as e:
        await update.message.reply_html(f"❌ Failed to unmute: <code>{e}</code>")


async def kick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    bot_info = await context.bot.get_me()

    if chat.type == "private":
        return

    if not await is_user_admin(chat, user.id):
        await update.message.reply_html("⚠️ Only administrators can kick members!")
        return

    reply = update.message.reply_to_message
    if not reply or not reply.from_user:
        await update.message.reply_html("⚠️ <b>Reply to the member</b> you want to kick!")
        return

    target = reply.from_user
    if await is_user_admin(chat, target.id):
        await update.message.reply_html("🛡️ You cannot kick an administrator!")
        return

    try:
        # Ban then immediately unban = kick
        await chat.ban_member(target.id)
        await chat.unban_member(target.id)
        await update.message.reply_html(
            f"👢 <b>ᴍᴇᴍʙᴇʀ ᴋɪᴄᴋᴇᴅ!</b>\n\n"
            f"<blockquote>{target.mention_html()} was removed from the group by {user.mention_html()}.</blockquote>"
        )
    except Exception as e:
        await update.message.reply_html(f"❌ Failed to kick: <code>{e}</code>")


async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    bot_info = await context.bot.get_me()

    if chat.type == "private":
        return

    if not await is_user_admin(chat, user.id):
        await update.message.reply_html("⚠️ Only administrators can issue warnings!")
        return

    reply = update.message.reply_to_message
    if not reply or not reply.from_user:
        await update.message.reply_html("⚠️ <b>Reply to the user</b> you want to warn!")
        return

    target = reply.from_user
    if await is_user_admin(chat, target.id):
        await update.message.reply_html("🛡️ You cannot warn an administrator!")
        return

    reason = " ".join(context.args) if context.args else "Rule violation"

    # Increment warning count in DB
    res = await warns_col.find_one_and_update(
        {"chat_id": chat.id, "user_id": target.id},
        {"$inc": {"warns": 1}, "$push": {"reasons": reason}},
        upsert=True,
        return_document=True,
    )
    warn_count = res.get("warns", 1)

    if warn_count >= 3:
        # 3 strikes reached: AUTO BAN!
        await warns_col.delete_one({"chat_id": chat.id, "user_id": target.id})
        try:
            await chat.ban_member(target.id)
            await update.message.reply_html(
                f"🚨 <b>3/3 sᴛʀɪᴋᴇs ʀᴇᴀᴄʜᴇᴅ — ʙᴀɴɴᴇᴅ!</b> 🚫\n\n"
                f"<blockquote>{target.mention_html()} accumulated <b>3 warnings</b> and has been banned from the chat!</blockquote>"
            )
        except Exception:
            await update.message.reply_html(f"🚨 {target.mention_html()} reached 3 warnings, but I lack ban permission!")
    else:
        await update.message.reply_html(
            f"⚠️ <b>ᴡᴀʀɴɪɴɢ ɪssᴜᴇᴅ ({warn_count}/3)!</b>\n\n"
            f"<blockquote>👤 <b>Target:</b> {target.mention_html()}\n"
            f"👮 <b>Admin:</b> {user.mention_html()}\n"
            f"📝 <b>Reason:</b> <i>{reason}</i>\n"
            f"⚡ <i>3 warnings will result in an automatic ban!</i></blockquote>"
        )


async def warns_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    reply = update.message.reply_to_message
    target = reply.from_user if reply and reply.from_user else update.effective_user

    doc = await warns_col.find_one({"chat_id": chat.id, "user_id": target.id})
    count = doc.get("warns", 0) if doc else 0

    await update.message.reply_html(
        f"📋 <b>ᴡᴀʀɴɪɴɢ sᴛᴀᴛᴜs ғᴏʀ {target.mention_html()}:</b>\n\n"
        f"<blockquote>⚠️ Current Strikes: <b>{count} / 3</b></blockquote>"
    )


async def rmwarn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not await is_user_admin(chat, user.id):
        await update.message.reply_html("⚠️ Only administrators can reset warnings!")
        return

    reply = update.message.reply_to_message
    if not reply or not reply.from_user:
        await update.message.reply_html("⚠️ <b>Reply to the user</b> to reset their warnings!")
        return

    target = reply.from_user
    await warns_col.delete_one({"chat_id": chat.id, "user_id": target.id})
    await update.message.reply_html(
        f"✨ <b>ᴡᴀʀɴɪɴɢs ʀᴇsᴇᴛ!</b>\n\n"
        f"<blockquote>All warnings for {target.mention_html()} have been cleared. (0/3)</blockquote>"
    )


async def purge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    bot_info = await context.bot.get_me()

    if chat.type == "private":
        return

    if not await is_user_admin(chat, user.id):
        await update.message.reply_html("⚠️ Only administrators can purge messages!")
        return

    if not await can_bot_delete(chat, bot_info.id):
        await update.message.reply_html("❌ I need <b>Delete Messages</b> admin permission!")
        return

    reply = update.message.reply_to_message
    if not reply:
        await update.message.reply_html("⚠️ <b>Reply to the message</b> from where you want to start purging!")
        return

    start_id = reply.message_id
    end_id = update.message.message_id

    # Telegram limits batch delete to 100 messages at a time
    msg_ids = list(range(start_id, end_id + 1))
    if len(msg_ids) > 100:
        msg_ids = msg_ids[-100:]

    try:
        await context.bot.delete_messages(chat_id=chat.id, message_ids=msg_ids)
        notice = await context.bot.send_message(
            chat_id=chat.id,
            text=f"🗑️ <b>Purged {len(msg_ids)} messages!</b>",
            parse_mode="HTML",
        )
        await asyncio.sleep(3)
        await notice.delete()
    except Exception:
        # Fallback single message deletions
        deleted = 0
        for m_id in msg_ids:
            try:
                await context.bot.delete_message(chat_id=chat.id, message_id=m_id)
                deleted += 1
            except Exception:
                pass
        notice = await context.bot.send_message(
            chat_id=chat.id,
            text=f"🗑️ <b>Purged {deleted} messages!</b>",
            parse_mode="HTML",
        )
        await asyncio.sleep(3)
        await notice.delete()


async def del_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not await is_user_admin(chat, user.id):
        return

    reply = update.message.reply_to_message
    if not reply:
        return

    try:
        await reply.delete()
        await update.message.delete()
    except Exception:
        pass


async def pin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not await is_user_admin(chat, user.id):
        await update.message.reply_html("⚠️ Only administrators can pin messages!")
        return

    reply = update.message.reply_to_message
    if not reply:
        await update.message.reply_html("⚠️ <b>Reply to the message</b> you want to pin!")
        return

    try:
        await reply.pin()
        await update.message.reply_html("📌 <b>Message successfully pinned!</b>")
    except Exception as e:
        await update.message.reply_html(f"❌ Failed to pin: <code>{e}</code>")


async def unpin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not await is_user_admin(chat, user.id):
        await update.message.reply_html("⚠️ Only administrators can unpin messages!")
        return

    reply = update.message.reply_to_message
    try:
        if reply:
            await reply.unpin()
        else:
            await chat.unpin_all_messages()
        await update.message.reply_html("📌 <b>Message unpinned!</b>")
    except Exception as e:
        await update.message.reply_html(f"❌ Failed to unpin: <code>{e}</code>")


async def set_welcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not await is_user_admin(chat, user.id):
        await update.message.reply_html("⚠️ Only administrators can configure welcome messages!")
        return

    if not context.args:
        await update.message.reply_html(
            "⚠️ <b>Specify welcome message!</b>\n\n"
            "Supported variables:\n"
            "• <code>{mention}</code> - User mention\n"
            "• <code>{name}</code> - User name\n"
            "• <code>{chat}</code> - Group title\n\n"
            "Example: <code>/setwelcome Welcome {mention} to {chat}! Have fun!</code>"
        )
        return

    welcome_text = " ".join(context.args)
    await chats_col.update_one(
        {"chat_id": chat.id},
        {"$set": {"welcome_text": welcome_text, "welcome_enabled": True}},
        upsert=True,
    )
    await update.message.reply_html(
        f"✅ <b>ᴡᴇʟᴄᴏᴍᴇ ᴍᴇssᴀɢᴇ sᴀᴠᴇᴅ!</b>\n\n"
        f"<blockquote>{welcome_text}</blockquote>"
    )


async def toggle_welcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not await is_user_admin(chat, user.id):
        await update.message.reply_html("⚠️ Only administrators can toggle welcomes!")
        return

    state = context.args[0].lower() if context.args else ""
    enable = state in ["on", "true", "enable", "yes"]

    await chats_col.update_one(
        {"chat_id": chat.id},
        {"$set": {"welcome_enabled": enable}},
        upsert=True,
    )
    status_str = "Enabled ✅" if enable else "Disabled ❌"
    await update.message.reply_html(f"🎋 <b>Welcome greetings {status_str} for this chat!</b>")


async def chat_member_join_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets new members when they join the group."""
    result: ChatMemberUpdated = update.chat_member
    if not result or not result.new_chat_member:
        return

    chat = update.effective_chat
    # Check if newly joined member
    if result.old_chat_member.status in ["left", "kicked"] and result.new_chat_member.status == "member":
        new_user = result.new_chat_member.user
        if new_user.is_bot:
            return

        chat_settings = await chats_col.find_one({"chat_id": chat.id})
        if not chat_settings or not chat_settings.get("welcome_enabled", True):
            return

        custom_text = chat_settings.get("welcome_text")
        if custom_text:
            msg = (
                custom_text
                .replace("{mention}", new_user.mention_html())
                .replace("{name}", new_user.first_name)
                .replace("{chat}", chat.title or "Group")
            )
        else:
            msg = (
                f"✨ <b>ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ {chat.title}, {new_user.mention_html()}!</b> 🌸\n\n"
                f"<blockquote>We are thrilled to have you here!\n"
                f"Type /help to discover games, economy & commands!</blockquote>"
            )

        try:
            await context.bot.send_message(
                chat_id=chat.id,
                text=msg,
                parse_mode="HTML",
            )
        except Exception:
            pass


def register_handlers(app: Application):
    app.add_handler(CommandHandler(["ban", "sban"], ban_command))
    app.add_handler(CommandHandler("unban", unban_command))
    app.add_handler(CommandHandler("mute", mute_command))
    app.add_handler(CommandHandler("unmute", unmute_command))
    app.add_handler(CommandHandler("kick", kick_command))
    app.add_handler(CommandHandler("warn", warn_command))
    app.add_handler(CommandHandler("warns", warns_command))
    app.add_handler(CommandHandler(["rmwarn", "resetwarns"], rmwarn_command))
    app.add_handler(CommandHandler("purge", purge_command))
    app.add_handler(CommandHandler("del", del_command))
    app.add_handler(CommandHandler("pin", pin_command))
    app.add_handler(CommandHandler("unpin", unpin_command))
    app.add_handler(CommandHandler("setwelcome", set_welcome_command))
    app.add_handler(CommandHandler("welcome", toggle_welcome_command))

    app.add_handler(ChatMemberHandler(chat_member_join_handler, ChatMemberHandler.CHAT_MEMBER))
