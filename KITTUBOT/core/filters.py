# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Custom PTB Filters
"""

from telegram.ext.filters import MessageFilter
from telegram import Message
from KITTUBOT.config import config


class _SudoFilter(MessageFilter):
    def filter(self, message: Message) -> bool:
        if not message.from_user:
            return False
        return message.from_user.id in config.SUDO_IDS


class _OwnerFilter(MessageFilter):
    def filter(self, message: Message) -> bool:
        if not message.from_user:
            return False
        return message.from_user.id == config.OWNER_ID


sudo_filter = _SudoFilter()
owner_filter = _OwnerFilter()
