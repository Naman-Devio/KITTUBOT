# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Cinematic Animation & Effects Engine
Built for high-concurrency PTB v22 with top-positioned video and aesthetic typography.
"""

import asyncio
import random
from telegram import Update, ReactionTypeEmoji, LinkPreviewOptions
from telegram.ext import ContextTypes
from KITTUBOT.config import config
from KITTUBOT.core.keyboards import get_main_menu_keyboard
from KITTUBOT.core.fonts import to_small_caps
from KITTUBOT import log


async def play_start_animation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Executes the signature multi-stage start animation."""
    message = update.effective_message
    user = update.effective_user
    chat_id = update.effective_chat.id

    # Stage 1: Big animated Unicorn 🦄 reaction
    try:
        await message.set_reaction(ReactionTypeEmoji("🦄"), is_big=True)
    except Exception as e:
        log.debug(f"Reaction ignored (chat restriction/private): {e}")

    # Stage 2: Fast frame-by-frame loading text
    try:
        loader = await message.reply_text(f"🐾 <code>Starting {config.BOT_NAME} Engine...</code>", parse_mode="HTML")
        await asyncio.sleep(0.3)
        await loader.edit_text("⚡ <code>Calibrating Game Hub & AI Brain...</code>", parse_mode="HTML")
        await asyncio.sleep(0.35)
        await loader.edit_text("✨ <code>System Ready!</code>", parse_mode="HTML")
        await asyncio.sleep(0.25)
        await loader.delete()
    except Exception as e:
        log.debug(f"Frame animation step: {e}")

    # Stage 3: Welcome sticker burst
    if config.START_STICKER_FILE_ID:
        try:
            await context.bot.send_sticker(chat_id=chat_id, sticker=config.START_STICKER_FILE_ID)
            await asyncio.sleep(0.2)
        except Exception as e:
            log.debug(f"Sticker send fallback: {e}")

    # Stage 4: Cinematic greeting with Video on Top (show_above_text=True)
    bot_info = await context.bot.get_me()
    random_media = random.choice(config.START_IMG_URL) if config.START_IMG_URL else ""

    bot_title = to_small_caps(config.BOT_NAME)
    text = (
        f'<a href="{random_media}">&#8203;</a>'
        f"⊚ <b>ʜєʏ ㅤ- {user.mention_html()}</b> 💢 ✨\n"
        f"💮 <b>ʏᴏᴜ ᴀʀᴇ ᴜsɪɴɢ ˹ {bot_title} ˼</b>\n\n"
        f"<blockquote>ᴧ ᴘʀєᴍɪᴜᴍ ᴅєꜱɪɢηєᴅ ᴍᴜʟᴛɪᴘʟᴀʏᴇʀ ɢᴀᴍᴇ ʜᴜʙ, ᴇᴄᴏɴᴏᴍʏ & ɢʀᴏᴜᴘ ᴍᴀɴᴀɢᴇʀ.\n"
        f"ᴛʜᴇ ᴜʟᴛɪᴍᴀᴛᴇ ᴅᴇsᴛɪɴᴀᴛɪᴏɴ ғᴏʀ ɢʀᴏᴜᴘ ᴇɴᴛᴇʀᴛᴀɪɴᴍᴇɴᴛ & ᴀɪ ᴄᴏᴍᴘᴀɴɪᴏɴsʜɪᴘ.</blockquote>\n\n"
        f"● <b>ʙᴜɪʟᴅ :</b> <code>ᴠ3.0 sᴛᴀʙʟᴇ</code>\n"
        f"● <b>ᴄᴏʀᴇ :</b> <code>ᴘᴛʙ ᴀsʏɴᴄ ᴇɴɢɪɴᴇ</code>\n"
        f"● <b>ʟᴀᴛᴇɴᴄʏ :</b> <code>ᴢᴇʀᴏ ᴅᴇʟᴀʏ</code>\n\n"
        f"🎋 <b>ᴄʟɪᴄᴋ ʜᴇʟᴘ ᴛᴏ sᴇᴇ ᴀʟʟ ᴀᴠᴀɪʟᴀʙʟᴇ ᴄᴏᴍᴍᴀɴᴅs.</b>"
    )

    kwargs = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": get_main_menu_keyboard(bot_info.username),
    }

    # Place video on the UPPER side of the caption
    if random_media:
        kwargs["link_preview_options"] = LinkPreviewOptions(
            url=random_media,
            is_disabled=False,
            prefer_large_media=True,
            show_above_text=True,  # Video appears ABOVE the caption!
        )

    if config.MESSAGE_EFFECT_ID:
        kwargs["message_effect_id"] = config.MESSAGE_EFFECT_ID

    try:
        await context.bot.send_message(**kwargs)
    except Exception as e:
        log.warning(f"Failed with message_effect_id, falling back: {e}")
        kwargs.pop("message_effect_id", None)
        await context.bot.send_message(**kwargs)
