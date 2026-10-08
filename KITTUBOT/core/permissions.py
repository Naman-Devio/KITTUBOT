# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Chat Admin & Permission Utilities
Safe, asynchronous permission checks for group management and moderation commands.
"""

from telegram import Chat, User
from telegram.constants import ChatMemberStatus
from KITTUBOT.config import config


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
