# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Character Gacha & Waifu Collection System
Powered by the real 2,865+ character anime MongoDB database.
Supports chat spawning, /grab guessing, personal /harem photo gallery, favorites, and gifting.
"""

import random
import time
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from KITTUBOT.config import config
from KITTUBOT.database.users import ensure_user, update_balance
from KITTUBOT.database.characters import (
    get_random_character,
    get_user_harem,
    add_character_to_harem,
    set_favorite_character,
    transfer_character,
    get_top_collectors,
)
from KITTUBOT import log

__mod_name__ = "Characters"
__help__ = """
<blockquote>🌸 <b>ᴄʜᴀʀᴀᴄᴛᴇʀ ɢᴀᴄʜᴀ & ʜᴀʀᴇᴍ:</b>
• <code>/grab [name]</code> - ɢᴜᴇss & ᴄʟᴀɪᴍ sᴘᴀᴡɴᴇᴅ ᴄʜᴀʀᴀᴄᴛᴇʀ
• <code>/harem</code> - ᴠɪᴇᴡ ʏᴏᴜʀ ᴄᴏʟʟᴇᴄᴛᴇᴅ ᴄʜᴀʀᴀᴄᴛᴇʀs
• <code>/fav [id|name]</code> - sᴇᴛ ʏᴏᴜʀ sʜᴏᴡᴄᴀsᴇ ғᴀᴠᴏʀɪᴛᴇ
• <code>/giftwaifu [id]</code> - (ʀᴇᴘʟʏ) ɢɪғᴛ ᴄʜᴀʀᴀᴄᴛᴇʀ ᴛᴏ ғʀɪᴇɴᴅ
• <code>/spawn</code> - ᴍᴀɴᴜᴀʟʟʏ sᴜᴍᴍᴏɴ ᴀ ᴄʜᴀʀᴀᴄᴛᴇʀ
• <code>/topwaifus</code> - ᴛᴏᴘ 10 ɢʟᴏʙᴀʟ ᴄᴏʟʟᴇᴄᴛᴏʀs</blockquote>
"""

# Fallback character if DB is temporarily unreachable
EMERGENCY_CHARACTER = {
    "id": "c1",
    "name": "Satoru Gojo",
    "anime": "Jujutsu Kaisen",
    "rarity": "🌈 Celestial",
    "bounty": 2500,
    "img": "https://graph.org/file/99723ecdbf561ee6a858e.jpg",
}

# In-memory spawn states: chat_id -> dict
ACTIVE_SPAWNS: dict[int, dict] = {}
CHAT_MSG_COUNTERS: dict[int, int] = {}
SPAWN_INTERVAL = 60  # Spawn every 60 group messages


def get_rarity_bounty(rarity_str: str) -> int:
    r_lower = str(rarity_str).lower()
    if "celestial" in r_lower:
        return 2500
    if "special" in r_lower or "edition" in r_lower:
        return 2000
    if "legendary" in r_lower:
        return 1000
    if "epic" in r_lower:
        return 500
    if "rare" in r_lower:
        return 250
    return 150


async def spawn_character_in_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Spawns a random character from the 2,865+ MongoDB database."""
    char = await get_random_character()
    if not char:
        char = dict(EMERGENCY_CHARACTER)

    bounty = get_rarity_bounty(char.get("rarity", ""))
    char["bounty"] = bounty

    ACTIVE_SPAWNS[chat_id] = {
        "character": char,
        "spawn_time": time.time(),
    }

    img_link = char.get("img") or char.get("img_url", "")
    caption = (
        "🌸 <b>ᴀ ᴡɪʟᴅ ᴄʜᴀʀᴀᴄᴛᴇʀ ʜᴀs ᴀᴘᴘᴇᴀʀᴇᴅ!</b> ✨\n\n"
        f"<blockquote>🎭 <b>ᴀɴɪᴍᴇ :</b> <i>{char.get('anime', 'Anime Series')}</i>\n"
        f"💎 <b>ʀᴀʀɪᴛʏ :</b> <b>{char.get('rarity', '⚪ Common')}</b>\n"
        f"💰 <b>ʙᴏᴜɴᴛʏ :</b> <code>+{bounty:,} Coins</code></blockquote>\n\n"
        "🎋 <i>Quick! Type <code>/grab &lt;name&gt;</code> to claim them into your harem!</i>"
    )

    try:
        if img_link:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=img_link,
                caption=caption,
                parse_mode="HTML",
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode="HTML",
            )
    except Exception as e:
        log.warning(f"Failed to send character photo ({img_link}): {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=caption,
            parse_mode="HTML",
        )


async def manual_spawn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        await update.message.reply_html("⚠️ Characters only spawn in group chats!")
        return

    now = time.time()
    last_spawn = ACTIVE_SPAWNS.get(chat.id, {}).get("spawn_time", 0)
    if user.id not in config.SUDO_IDS and (now - last_spawn) < 90:
        rem = int(90 - (now - last_spawn))
        await update.message.reply_html(f"⏳ <b>A character was spawned recently!</b> Wait {rem}s before spawning again.")
        return

    await spawn_character_in_chat(context, chat.id)


async def grab_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.id not in ACTIVE_SPAWNS:
        await update.message.reply_html("🌸 <b>No character is currently spawned here!</b> Keep chatting to summon one.")
        return

    if not context.args:
        await update.message.reply_html("⚠️ <b>Specify the character's name!</b> E.g. <code>/grab Gojo</code>")
        return

    user_guess = " ".join(context.args).strip().lower()
    spawn_data = ACTIVE_SPAWNS[chat.id]
    char = spawn_data["character"]
    char_name = char.get("name", "").strip().lower()

    # Intelligent match: full name, first name, last name, or aliases
    name_tokens = [p.strip().lower() for p in char_name.split() if len(p.strip()) >= 2]
    matched = (user_guess == char_name) or (user_guess in name_tokens) or any(a in user_guess for a in char.get("aliases", []))

    if not matched:
        await update.message.reply_html(f"❌ <b>Wrong guess, {user.first_name}!</b> Think carefully and try again!")
        return

    # Claim character!
    del ACTIVE_SPAWNS[chat.id]
    await ensure_user(user)
    await add_character_to_harem(user, char)

    bounty = char.get("bounty", 250)
    await update_balance(user.id, bounty)

    await update.message.reply_html(
        f"🎉 <b>ᴄʜᴀʀᴀᴄᴛᴇʀ ᴄʟᴀɪᴍᴇᴅ!</b> 💖\n\n"
        f"<blockquote>👑 {user.mention_html()} successfully grabbed <b>{char.get('name')}</b>!\n"
        f"🌸 <b>Series:</b> <i>{char.get('anime')}</i>\n"
        f"💎 <b>Rarity:</b> <b>{char.get('rarity')}</b>\n"
        f"💰 <b>Reward Earned:</b> <code>+{bounty:,} Coins</code>! 🪙</blockquote>\n\n"
        "🎋 <i>View your full collection anytime with /harem!</i>"
    )


async def harem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    harem_doc = await get_user_harem(user.id)
    characters = harem_doc.get("characters", [])

    if not characters:
        await update.message.reply_html(
            f"🌸 <b>{user.mention_html()}'s Harem is Empty!</b>\n\n"
            "<blockquote>You haven't claimed any characters yet!\n"
            "Keep chatting in groups and type <code>/grab &lt;name&gt;</code> when a character appears!</blockquote>"
        )
        return

    page = 0
    await send_harem_page(update, context, user, characters, page, harem_doc)


async def send_harem_page(update: Update, context: ContextTypes.DEFAULT_TYPE, user, characters: list, page: int, harem_doc: dict):
    total = len(characters)
    page = max(0, min(page, total - 1))
    char = characters[page]

    fav_char = harem_doc.get("favorite_character")
    is_fav = fav_char and str(fav_char.get("id")) == str(char.get("id"))
    fav_badge = " ⭐ <b>[FAVORITE]</b>" if is_fav else ""

    img_link = char.get("img_url") or char.get("img") or ""
    char_id = str(char.get("id", char.get("_id", "0")))

    text = (
        f"🌸 <b>{user.first_name}'s ʜᴀʀᴇᴍ ɢᴀʟʟᴇʀʏ</b> ({page + 1}/{total})\n\n"
        f"<blockquote>👤 <b>ɴᴀᴍᴇ :</b> <b>{char.get('name')}</b>{fav_badge}\n"
        f"🎭 <b>ᴀɴɪᴍᴇ :</b> <i>{char.get('anime', 'Series')}</i>\n"
        f"💎 <b>ʀᴀʀɪᴛʏ :</b> <b>{char.get('rarity', '⚪ Common')}</b>\n"
        f"🆔 <b>ɪᴅ :</b> <code>{char_id}</code></blockquote>\n\n"
        f"🎋 <i>Type <code>/fav {char_id}</code> to set as your profile favorite!</i>"
    )

    nav_buttons = []
    if total > 1:
        prev_idx = (page - 1) % total
        next_idx = (page + 1) % total
        nav_buttons.append(InlineKeyboardButton("« ᴘʀᴇᴠ", callback_data=f"harem_{user.id}_{prev_idx}"))
        nav_buttons.append(InlineKeyboardButton(f"📄 {page + 1}/{total}", callback_data="noop"))
        nav_buttons.append(InlineKeyboardButton("ɴᴇxᴛ »", callback_data=f"harem_{user.id}_{next_idx}"))

    action_row = [
        InlineKeyboardButton("⭐ sᴇᴛ ғᴀᴠ", callback_data=f"harem_fav_{user.id}_{char_id}"),
        InlineKeyboardButton("❌ ᴄʟᴏsᴇ", callback_data="close_menu"),
    ]

    rows = []
    if nav_buttons:
        rows.append(nav_buttons)
    rows.append(action_row)

    keyboard = InlineKeyboardMarkup(rows)

    if update.callback_query:
        query = update.callback_query
        try:
            await query.answer()
            if img_link:
                await query.edit_message_media(
                    media=InputMediaPhoto(media=img_link, caption=text, parse_mode="HTML"),
                    reply_markup=keyboard,
                )
            else:
                await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
        except Exception:
            pass
    else:
        if img_link:
            try:
                await update.message.reply_photo(
                    photo=img_link,
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
            except Exception:
                await update.message.reply_html(text=text, reply_markup=keyboard)
        else:
            await update.message.reply_html(text=text, reply_markup=keyboard)


async def harem_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_")
    owner_id = int(parts[1])
    page = int(parts[2])
    user = update.effective_user

    if user.id != owner_id:
        try:
            await query.answer("This is not your harem gallery!", show_alert=True)
        except Exception:
            pass
        return

    harem_doc = await get_user_harem(user.id)
    characters = harem_doc.get("characters", [])
    if not characters:
        return

    await send_harem_page(update, context, user, characters, page, harem_doc)


async def harem_fav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_")
    owner_id = int(parts[2])
    char_id = parts[3]
    user = update.effective_user

    if user.id != owner_id:
        try:
            await query.answer("This is not your harem!", show_alert=True)
        except Exception:
            pass
        return

    fav = await set_favorite_character(user.id, char_id)
    if fav:
        try:
            await query.answer(f"⭐ Set {fav.get('name')} as your favorite!", show_alert=True)
        except Exception:
            pass
    else:
        try:
            await query.answer("Character not found!", show_alert=True)
        except Exception:
            pass


async def set_fav_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_html("⚠️ <b>Specify character ID!</b> E.g. <code>/fav 1241</code>")
        return

    char_id = context.args[0].strip()
    fav = await set_favorite_character(user.id, char_id)
    if not fav:
        await update.message.reply_html("❌ You don't own this character! Check <code>/harem</code>.")
        return

    await update.message.reply_html(
        f"⭐ <b>sʜᴏᴡᴄᴀsᴇ ғᴀᴠᴏʀɪᴛᴇ sᴇᴛ!</b>\n\n"
        f"<blockquote><b>{fav.get('name')}</b> ({fav.get('rarity')}) is now pinned as your favorite character! 💖</blockquote>"
    )


async def gift_waifu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    reply = update.message.reply_to_message

    if not reply or not reply.from_user or reply.from_user.is_bot:
        await update.message.reply_html("⚠️ <b>Reply to the friend</b> you want to gift a character to!")
        return

    target = reply.from_user
    if target.id == user.id:
        await update.message.reply_html("😂 You cannot gift characters to yourself!")
        return

    if not context.args:
        await update.message.reply_html("⚠️ <b>Specify character ID!</b> E.g. <code>/giftwaifu 1241</code>")
        return

    char_id = context.args[0].strip()
    success, msg = await transfer_character(user.id, target, char_id)

    if success:
        await update.message.reply_html(
            f"🎁 <b>ᴄʜᴀʀᴀᴄᴛᴇʀ ɢɪғᴛ sᴜᴄᴄᴇssғᴜʟ!</b>\n\n"
            f"<blockquote>{user.mention_html()} gifted a character to {target.mention_html()}! 🤝\n"
            f"<i>{msg}</i></blockquote>"
        )
    else:
        await update.message.reply_html(f"❌ {msg}")


async def top_waifus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = await get_top_collectors(limit=10)
    if not top:
        await update.message.reply_html("No collectors recorded yet.")
        return

    text = "👑 <b>ᴋɪᴛᴛᴜ ɢʟᴏʙᴀʟ ʜᴀʀᴇᴍ ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ</b> 🌸\n\n<blockquote>"
    for idx, col in enumerate(top, start=1):
        name = col.get("first_name", "Unknown")
        count = col.get("total_count", 0)
        fav = col.get("favorite")
        fav_str = f" (Fav: {fav.get('name')})" if fav else ""
        medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
        text += f"{medal} <b>{name}</b> — <code>{count} characters</code>{fav_str}\n"
    text += "</blockquote>"

    await update.message.reply_html(text)


async def track_chat_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Counts messages in groups and triggers periodic character spawns."""
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return

    CHAT_MSG_COUNTERS[chat.id] = CHAT_MSG_COUNTERS.get(chat.id, 0) + 1

    if CHAT_MSG_COUNTERS[chat.id] >= SPAWN_INTERVAL:
        CHAT_MSG_COUNTERS[chat.id] = 0
        if chat.id not in ACTIVE_SPAWNS:
            await spawn_character_in_chat(context, chat.id)


def register_handlers(app: Application):
    app.add_handler(CommandHandler(["grab", "guesswaifu"], grab_command))
    app.add_handler(CommandHandler(["harem", "myharem"], harem_command))
    app.add_handler(CommandHandler(["fav", "setfav"], set_fav_command))
    app.add_handler(CommandHandler(["giftwaifu", "tradewaifu"], gift_waifu_command))
    app.add_handler(CommandHandler(["spawn", "spawnwaifu"], manual_spawn_command))
    app.add_handler(CommandHandler(["topwaifus", "topharem"], top_waifus_command))

    app.add_handler(CallbackQueryHandler(harem_page_callback, pattern=r"^harem_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(harem_fav_callback, pattern=r"^harem_fav_\d+_\w+$"))

    # Background message counter for natural spawns
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, track_chat_messages),
        group=25,
    )
