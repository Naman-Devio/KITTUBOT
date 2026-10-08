# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Chat Admin & Permission Utilities
Safe, asynchronous permission checks and universal target user resolution for group management and moderation commands.
"""

import re
from telegram import Chat, User, Update
from telegram.constants import ChatMemberStatus
from telegram.ext import ContextTypes
from KITTUBOT.config import config
from KITTUBOT.database import users_col
from KITTUBOT import log


class TargetUser:
    """Universal wrapper for resolved users supporting ID, username, and HTML mentions."""
    def __init__(self, user_id: int, first_name: str, username: str = "", user_obj: User | None = None):
        self.id = user_id
        self.first_name = first_name or f"User {user_id}"
        self.username = username or ""
        self.user = user_obj

    def mention_html(self, name: str | None = None) -> str:
        if self.user:
            return self.user.mention_html(name)
        display_name = name or self.first_name or f"User {self.id}"
        return f'<a href="tg://user?id={self.id}">{display_name}</a>'


async def is_user_admin(chat: Chat, user_id: int) -> bool:
    """Checks whether a user is a group administrator, owner, or bot sudoer."""
    if user_id in config.SUDO_IDS:
        return True
    if chat.type == "private":
        return True

    try:
        member = await chat.get_member(user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception:
        return False


async def can_bot_restrict(chat: Chat, bot_id: int) -> bool:
    """Checks whether the bot has rights to ban/mute members."""
    try:
        bot_member = await chat.get_member(bot_id)
        if bot_member.status == ChatMemberStatus.ADMINISTRATOR:
            return getattr(bot_member, "can_restrict_members", False) or bot_member.status == ChatMemberStatus.OWNER
        return False
    except Exception:
        return False


async def can_bot_delete(chat: Chat, bot_id: int) -> bool:
    """Checks whether the bot has rights to delete messages."""
    try:
        bot_member = await chat.get_member(bot_id)
        if bot_member.status == ChatMemberStatus.ADMINISTRATOR:
            return getattr(bot_member, "can_delete_messages", False) or bot_member.status == ChatMemberStatus.OWNER
        return False
    except Exception:
        return False


async def resolve_target_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> tuple[TargetUser | None, list[str]]:
    """
    Universally extracts and resolves a target user from:
    1. Reply to a message (update.message.reply_to_message)
    2. Text mention entity in message (clickable mentions without @username)
    3. First argument: @username (Telegram API + DB fallback) or numeric user_id
    Returns:
        (TargetUser | None, remaining_arguments: list[str])
    """
    message = update.effective_message
    if not message:
        return None, list(context.args or [])

    # 1. Reply to message
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        return TargetUser(u.id, u.first_name, u.username or "", u), list(context.args or [])

    # 2. Text mention entity in message
    if message.entities:
        for ent in message.entities:
            if ent.type == "text_mention" and ent.user:
                u = ent.user
                rem = list(context.args or [])
                if rem and (rem[0].startswith("@") or rem[0] == u.first_name):
                    rem = rem[1:]
                return TargetUser(u.id, u.first_name, u.username or "", u), rem

    # 3. Argument resolution
    args = list(context.args or [])
    if not args:
        return None, []

    first_arg = args[0].strip()

    # Case 3A: Numeric User ID
    if first_arg.isdigit() or (first_arg.startswith("-") and first_arg[1:].isdigit()):
        uid = int(first_arg)
        rem = args[1:]
        u_obj = None
        first_name = f"User {uid}"
        username = ""

        # Try chat member
        if update.effective_chat:
            try:
                member = await update.effective_chat.get_member(uid)
                if member and member.user:
                    u_obj = member.user
                    first_name = u_obj.first_name
                    username = u_obj.username or ""
            except Exception:
                pass

        # Try get_chat
        if not u_obj:
            try:
                c = await context.bot.get_chat(uid)
                first_name = c.first_name or f"User {uid}"
                username = c.username or ""
            except Exception:
                pass

        # Try database
        if not u_obj:
            try:
                db_u = await users_col.find_one({"user_id": uid})
                if db_u:
                    first_name = db_u.get("first_name", first_name)
                    username = db_u.get("username", "")
            except Exception:
                pass

        return TargetUser(uid, first_name, username, u_obj), rem

    # Case 3B: Username (@WordGridRobot or WordGridRobot)
    is_mention = first_arg.startswith("@") or bool(re.match(r"^[a-zA-Z0-9_]{3,32}$", first_arg))
    if is_mention:
        raw_username = first_arg.lstrip("@").strip()
        rem = args[1:]
        uid = None
        u_obj = None
        first_name = raw_username
        username = raw_username

        # Step 1: Telegram Bot API get_chat("@username")
        try:
            c = await context.bot.get_chat(f"@{raw_username}")
            if c:
                uid = c.id
                first_name = c.first_name or raw_username
                username = c.username or raw_username
        except Exception as e:
            log.debug(f"get_chat failed for @{raw_username}: {e}")

        # Step 2: Database lookup by username (case-insensitive)
        if not uid:
            try:
                db_u = await users_col.find_one(
                    {"username": {"$regex": f"^{re.escape(raw_username)}$", "$options": "i"}}
                )
                if db_u:
                    uid = db_u.get("user_id")
                    first_name = db_u.get("first_name", raw_username)
                    username = db_u.get("username", raw_username)
            except Exception as e:
                log.debug(f"DB lookup failed for @{raw_username}: {e}")

        # Step 3: Check chat administrators
        if not uid and update.effective_chat:
            try:
                admins = await update.effective_chat.get_administrators()
                for adm in admins:
                    if adm.user.username and adm.user.username.lower() == raw_username.lower():
                        uid = adm.user.id
                        u_obj = adm.user
                        first_name = adm.user.first_name
                        username = adm.user.username
                        break
            except Exception:
                pass

        if uid:
            return TargetUser(uid, first_name, username, u_obj), rem

    return None, args
