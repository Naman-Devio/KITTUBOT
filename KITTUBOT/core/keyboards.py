# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Keyboard & Pagination Engine
Aesthetic typography with 3-column category grid and smooth navigation controls.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from KITTUBOT.config import config
from KITTUBOT.core.fonts import format_category_name


def get_main_menu_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    """Aesthetic, high-impact main menu buttons."""
    buttons = [
        [
            InlineKeyboardButton(
                "➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ",
                url=f"https://t.me/{bot_username}?startgroup=true",
            )
        ],
        [
            InlineKeyboardButton("🎮 ɢᴀᴍᴇ ʜᴜʙ & ᴄᴏᴍᴍᴀɴᴅs", callback_data="kittu_help"),
            InlineKeyboardButton("🌸 ᴄʜᴀʀᴀᴄᴛᴇʀ ɢᴀᴄʜᴀ", callback_data="helpmod_characters_1"),
        ],
        [
            InlineKeyboardButton("💬 sᴜᴘᴘᴏʀᴛ", url=config.SUPPORT_CHAT_LINK),
            InlineKeyboardButton("📢 ᴜᴘᴅᴀᴛᴇs", url=config.SUPPORT_CHANNEL_LINK),
        ],
        [
            InlineKeyboardButton("👑 ᴏᴡɴᴇʀ", url=config.OWNER_LINK),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def get_paginated_help_keyboard(
    module_names: list[str], page: int = 1, items_per_page: int = 12
) -> InlineKeyboardMarkup:
    """3-column dynamic paginated grid with smooth aesthetic navigation controls."""
    total_modules = len(module_names)
    total_pages = max(1, (total_modules + items_per_page - 1) // items_per_page)
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    current_page_modules = module_names[start_idx:end_idx]

    # Build 3-column rows of module buttons with aesthetic font
    buttons = [
        InlineKeyboardButton(
            format_category_name(name), callback_data=f"helpmod_{name.lower()}_{page}"
        )
        for name in current_page_modules
    ]
    rows = [buttons[i : i + 3] for i in range(0, len(buttons), 3)]

    # Bottom pagination controls
    nav_row = []
    if total_pages > 1:
        if page > 1:
            nav_row.append(InlineKeyboardButton("« ᴘʀᴇᴠ", callback_data=f"helppage_{page - 1}"))
        nav_row.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop"))
        if page < total_pages:
            nav_row.append(InlineKeyboardButton("ɴᴇxᴛ »", callback_data=f"helppage_{page + 1}"))
        rows.append(nav_row)

    rows.append([
        InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="main_menu"),
        InlineKeyboardButton("❌ ᴄʟᴏsᴇ", callback_data="close_menu"),
    ])

    return InlineKeyboardMarkup(rows)
