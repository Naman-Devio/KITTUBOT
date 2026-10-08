# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Chat Anti-Clutter & Menu Cleaner Engine
Manages interactive menu states in group chats to prevent clutter and spam:
- Ensures only ONE interactive menu is open per group chat at any time.
- Automatically deletes previous menus when a new one is opened.
- Auto-expires/deletes abandoned menus after inactivity (default 180s).
- Provides universal [ ❌ Close ] handling.
"""

import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from KITTUBOT import log

# Maps chat_id -> message_id of the currently active menu in that chat
ACTIVE_MENUS: dict[int, int] = {}

# Maps chat_id -> asyncio.Task for scheduled auto-deletion
MENU_TIMERS: dict[int, asyncio.Task] = {}


async def _auto_delete_worker(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, delay_seconds: int):
    """Background worker that cleanly deletes an abandoned menu after delay_seconds."""
    try:
        await asyncio.sleep(delay_seconds)
        # Check if this menu is still the active one
        if ACTIVE_MENUS.get(chat_id) == message_id:
            del ACTIVE_MENUS[chat_id]
            MENU_TIMERS.pop(chat_id, None)
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                log.info(f"[Cleaner] Auto-cleaned inactive menu {message_id} in chat {chat_id}")
            except Exception:
                pass
    except asyncio.CancelledError:
        pass
    except Exception as e:
        log.debug(f"[Cleaner] Error in auto-delete worker: {e}")


async def track_menu(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    auto_delete_seconds: int = 180,
    is_group: bool = True,
):
    """
    Registers a new interactive menu message in the chat:
    1. If a previous menu exists in this chat, immediately deletes the old one.
    2. Registers the new menu message.
    3. If in a group chat, schedules auto-deletion after inactivity.
    """
    if not is_group:
        return

    # Delete previous active menu in this chat if one exists
    old_msg_id = ACTIVE_MENUS.get(chat_id)
    if old_msg_id and old_msg_id != message_id:
        # Cancel old timer
        old_task = MENU_TIMERS.pop(chat_id, None)
        if old_task:
            old_task.cancel()
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=old_msg_id)
            log.info(f"[Cleaner] Removed previous menu {old_msg_id} in chat {chat_id}")
        except Exception:
            pass

    # Record new active menu
    ACTIVE_MENUS[chat_id] = message_id

    # Cancel any existing timer for this chat
    existing_task = MENU_TIMERS.get(chat_id)
    if existing_task:
        existing_task.cancel()

    # Schedule auto-delete
    MENU_TIMERS[chat_id] = asyncio.create_task(
        _auto_delete_worker(context, chat_id, message_id, auto_delete_seconds)
    )


def touch_menu(context: ContextTypes.DEFAULT_TYPE, chat_id: int, auto_delete_seconds: int = 180):
    """Resets the auto-delete countdown whenever a user interacts with the menu."""
    message_id = ACTIVE_MENUS.get(chat_id)
    if not message_id:
        return

    existing_task = MENU_TIMERS.get(chat_id)
    if existing_task:
        existing_task.cancel()

    MENU_TIMERS[chat_id] = asyncio.create_task(
        _auto_delete_worker(context, chat_id, message_id, auto_delete_seconds)
    )


async def close_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Universal close callback handler. Deletes the menu and cleans state."""
    query = update.callback_query
    chat_id = update.effective_chat.id if update.effective_chat else None

    if chat_id:
        # Cancel timer
        timer_task = MENU_TIMERS.pop(chat_id, None)
        if timer_task:
            timer_task.cancel()
        ACTIVE_MENUS.pop(chat_id, None)

    try:
        await query.answer("Menu closed.")
        await query.message.delete()
    except Exception:
        pass
