# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Chat Ranking, Group Leaderboards & Speed-Typing Suite
Ported & enhanced from Japanese-X-Ranking with 4K anime artwork, custom typography,
XP tiers, message activity counters & real-time Telegram group leaderboards.
"""

import os
import random
import time
import asyncio
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from telegram import Update, Message, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

from KITTUBOT.database.rankings import (
    record_chat_activity,
    award_typing_win,
    get_group_leaderboard,
    get_global_leaderboard,
    get_user_chat_rank,
    get_user_global_stats,
)
from KITTUBOT.database.chats import get_chat, set_chat_setting
from KITTUBOT.core.permissions import resolve_target_user
from KITTUBOT import log

__mod_name__ = "Ranking"
__help__ = """
<blockquote>🏆 <b>ᴄʜᴀᴛ ʀᴀɴᴋɪɴɢ & ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅs:</b>
• <code>/ranking</code> or <code>/myrank</code> - ʏᴏᴜʀ ᴘᴇʀsᴏɴᴀʟ ᴄʜᴀᴛ ʀᴀɴᴋ & sᴛᴀᴛs
• <code>/grouprank</code> or <code>/topchat</code> - ɢʀᴏᴜᴘ's ᴛᴏᴘ 10 ᴀᴄᴛɪᴠᴇ ᴍᴇᴍʙᴇʀs
• <code>/topgame</code> or <code>/topglobal</code> - ɢʟᴏʙᴀʟ ᴛᴏᴘ 10 ᴘʟᴀʏᴇʀs
• <code>/challenge</code> or <code>/speedtype</code> - sᴘᴀᴡɴ sᴘᴇᴇᴅ-ᴛʏᴘɪɴɢ ʙᴀɴɴᴇʀ ᴄᴏɴᴛᴇsᴛ
• <code>/autochallenge on|off</code> - ᴛᴏɢɢʟᴇ ᴀᴜᴛᴏᴍᴀᴛɪᴄ ᴛʏᴘɪɴɢ ᴄᴏɴᴛᴇsᴛs (ᴀᴅᴍɪɴ)

<b>Activity:</b> Every chat message grants XP points! Win typing banners for coin jackpots! 🪙</blockquote>
"""

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
RANKING_IMG_DIR = ASSETS_DIR / "ranking"

WORDS_POOL = [
    # Fast 3-4 letters
    "WIN", "RUN", "FAST", "PLAY", "SAFE", "TRUE", "NEXT", "MOVE", "FLOW", "HERO",
    "STAR", "NEO", "FIRE", "WAVE", "RUSH", "BOLD", "APEX", "ECHO", "BEAT", "DAWN",
    # Balanced 5-6 letters
    "POWER", "SMILE", "PEACE", "TRUST", "LIGHT", "HEART", "FOCUS", "BRAVE", "CALM",
    "LEVEL", "START", "RISE", "BUILD", "LEARN", "GROW", "BOOST", "ENERGY", "SPIRIT",
    "SHADOW", "CYBER", "STORM", "FLASH", "MAGIC", "HYPER", "PRIDE", "FLAME",
    # Skill 7-8 letters
    "SUCCESS", "RESPECT", "FUTURE", "PROGRESS", "VICTORY", "ACHIEVE", "BELIEVE",
    "BALANCE", "COURAGE", "HARMONY", "DYNAMIC", "INFINITY", "POWERFUL", "WARRIOR",
    # Elite 9-12 letters
    "DISCIPLINE", "PATIENCE", "DETERMINED", "CONSISTENT", "PERFORMANCE", "TRANSFORM",
    "DEDICATION", "DOMINATE", "UNSTOPPABLE", "LEGENDARY", "CHAMPION", "SOVEREIGN"
]

RANK_TIERS = [
    (12000, "🌌 ᴄᴏsᴍɪᴄ sᴏᴠᴇʀᴇɪɢɴ"),
    (6000, "⚡ ᴍʏᴛʜɪᴄ ʟᴇɢᴇɴᴅ"),
    (3000, "👑 ᴅɪᴀᴍᴏɴᴅ ᴍᴀsᴛᴇʀ"),
    (1500, "🔮 ᴘʟᴀᴛɪɴᴜᴍ ᴇʟɪᴛᴇ"),
    (700, "💎 ɢᴏʟᴅ ᴄʜᴀᴛᴛᴇʀ"),
    (300, "🥇 sɪʟᴠᴇʀ ᴄʜᴀᴛᴛᴇʀ"),
    (100, "🥈 ʙʀᴏɴᴢᴇ ᴄʜᴀᴛᴛᴇʀ"),
    (0, "🥉 ɴᴏᴠɪᴄᴇ ᴄʜᴀᴛᴛᴇʀ"),
]


def get_user_tier(points: int) -> str:
    for threshold, title in RANK_TIERS:
        if points >= threshold:
            return title
    return "🥉 ɴᴏᴠɪᴄᴇ ᴄʜᴀᴛᴛᴇʀ"


def generate_challenge_poster(word: str, reward_coins: int) -> BytesIO:
    """Renders a high-aesthetic challenge banner using Japanese-X-Ranking assets."""
    # Pick a background image
    bgs = ["ranking.png", "wp12025849.jpg", "wp12025868.jpg"]
    chosen_bg = RANKING_IMG_DIR / random.choice(bgs)
    if not chosen_bg.exists():
        chosen_bg = RANKING_IMG_DIR / "ranking.png"

    if chosen_bg.exists():
        img = Image.open(chosen_bg).convert("RGBA")
        img.thumbnail((1200, 675))
    else:
        img = Image.new("RGBA", (1200, 675), color=(20, 24, 33, 255))

    W, H = img.size
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 110))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # Load custom fonts
    header_font_path = FONTS_DIR / "faith.ttf"
    word_font_path = FONTS_DIR / "GODOFWAR.TTF"
    sub_font_path = FONTS_DIR / "Roboto-Regular.ttf"

    header_font = ImageFont.truetype(str(header_font_path), 42) if header_font_path.exists() else ImageFont.load_default()
    word_font = ImageFont.truetype(str(word_font_path), 76) if word_font_path.exists() else ImageFont.load_default()
    sub_font = ImageFont.truetype(str(sub_font_path), 34) if sub_font_path.exists() else ImageFont.load_default()

    # Draw Header
    header_text = "⚡ SPEED-TYPING CHALLENGE ⚡"
    h_bbox = header_font.getbbox(header_text)
    hx = (W - (h_bbox[2] - h_bbox[0])) // 2
    draw.text((hx + 2, 72), header_text, font=header_font, fill=(0, 0, 0, 200))
    draw.text((hx, 70), header_text, font=header_font, fill=(0, 229, 255, 255))

    # Center card box
    box_w, box_h = int(W * 0.78), 210
    bx = (W - box_w) // 2
    by = (H - box_h) // 2
    card = Image.new("RGBA", (box_w, box_h), (10, 15, 25, 175))
    img.paste(card, (bx, by), card)
    draw.rectangle([bx, by, bx + box_w, by + box_h], outline=(0, 229, 255, 180), width=3)

    # Draw Target Word
    w_bbox = word_font.getbbox(word)
    wx = (W - (w_bbox[2] - w_bbox[0])) // 2
    wy = by + (box_h - (w_bbox[3] - w_bbox[1])) // 2 - 8

    # Stroke for maximum clarity
    for dx, dy in [(-3, -3), (3, -3), (-3, 3), (3, 3), (0, 3), (0, -3), (3, 0), (-3, 0)]:
        draw.text((wx + dx, wy + dy), word, font=word_font, fill=(0, 0, 0, 255))
    draw.text((wx, wy), word, font=word_font, fill=(255, 235, 59, 255))

    # Draw Footer
    sub_text = f"⏱️ 60s Time Limit   •   💰 +{reward_coins:,} Coins & XP"
    s_bbox = sub_font.getbbox(sub_text)
    sx = (W - (s_bbox[2] - s_bbox[0])) // 2
    draw.text((sx + 2, H - 98), sub_text, font=sub_font, fill=(0, 0, 0, 220))
    draw.text((sx, H - 100), sub_text, font=sub_font, fill=(255, 255, 255, 240))

    out = BytesIO()
    out.name = "challenge.jpg"
    img.convert("RGB").save(out, format="JPEG", quality=88)
    out.seek(0)
    return out


# Active challenges: chat_id -> dict
ACTIVE_CHALLENGES: dict[int, dict] = {}


async def challenge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Spawns an instant speed-typing visual contest in the group."""
    chat = update.effective_chat
    if not chat or chat.type in ["private", "channel"]:
        await update.effective_message.reply_html("⚠️ Speed-typing challenges can only be played inside groups!")
        return

    now = time.time()
    if chat.id in ACTIVE_CHALLENGES:
        active = ACTIVE_CHALLENGES[chat.id]
        if now < active["expires_at"]:
            remaining = int(active["expires_at"] - now)
            await update.effective_message.reply_html(
                f"⚠️ <b>A challenge is already active in this chat!</b>\n"
                f"⏳ <code>{remaining} seconds</code> remaining to type the word!"
            )
            return

    word = random.choice(WORDS_POOL).upper()
    reward_coins = random.randint(150, 450)
    reward_points = random.randint(25, 60)

    ACTIVE_CHALLENGES[chat.id] = {
        "word": word.lower(),
        "reward_coins": reward_coins,
        "reward_points": reward_points,
        "expires_at": now + 60,
    }

    poster = generate_challenge_poster(word, reward_coins)
    caption = (
        "⚡ <b>ᴋɪᴛᴛᴜ sᴘᴇᴇᴅ-ᴛʏᴘɪɴɢ ᴄʜᴀʟʟᴇɴɢᴇ!</b> 🎌✨\n\n"
        "<blockquote>🎯 <b>ᴛᴀsᴋ :</b> Type the word shown in the banner above!\n"
        f"💰 <b>ʙᴏᴜɴᴛʏ :</b> <code>+{reward_coins:,} Coins</code> & <code>+{reward_points} XP</code>\n"
        "⏳ <b>ᴛɪᴍᴇ ʟɪᴍɪᴛ :</b> <code>60 Seconds</code></blockquote>\n\n"
        "🎋 <i>First member to send the exact word in chat wins the prize!</i>"
    )

    sent_msg = await update.effective_message.reply_photo(photo=poster, caption=caption, parse_mode="HTML")
    ACTIVE_CHALLENGES[chat.id]["message_id"] = sent_msg.message_id


async def ranking_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays user's personal ranking card, level tier, and points."""
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    target_user, _ = await resolve_target_user(update, context)
    if not target_user:
        target_user = user

    rank, chat_data = await get_user_chat_rank(chat.id, target_user.id)
    global_stats = await get_user_global_stats(target_user.id)

    points = chat_data.get("points", 0) if chat_data else 0
    messages = chat_data.get("messages", 0) if chat_data else 0
    wins = chat_data.get("typing_wins", 0) if chat_data else 0
    tier = get_user_tier(points)

    rank_str = f"#{rank}" if rank > 0 else "Unranked"
    g_points = global_stats.get("total_points", points)
    g_msgs = global_stats.get("total_messages", messages)
    g_wins = global_stats.get("total_typing_wins", wins)

    card_text = (
        f"🏆 <b>ᴋɪᴛᴛᴜ ᴄʜᴀᴛ ʀᴀɴᴋɪɴɢ sᴛᴀᴛᴜs</b> 🎌\n\n"
        f"<blockquote>👤 <b>ᴜsᴇʀ :</b> {target_user.mention_html()}\n"
        f"🎖️ <b>ᴛɪᴇʀ :</b> {tier}\n"
        f"📊 <b>ɢʀᴏᴜᴘ ʀᴀɴᴋ :</b> <code>{rank_str}</code>\n"
        f"✨ <b>ɢʀᴏᴜᴘ xᴘ :</b> <code>{points:,} Points</code>\n"
        f"💬 <b>ᴍᴇssᴀɢᴇs :</b> <code>{messages:,}</code>\n"
        f"⚡ <b>ᴛʏᴘɪɴɢ ᴡɪɴs :</b> <code>{wins}</code></blockquote>\n\n"
        f"<blockquote>🌐 <b>ɢʟᴏʙᴀʟ sᴛᴀᴛs:</b>\n"
        f"• ᴛᴏᴛᴀʟ xᴘ: <code>{g_points:,}</code>\n"
        f"• ᴛᴏᴛᴀʟ ᴍsɢs: <code>{g_msgs:,}</code>\n"
        f"• ɢʟᴏʙᴀʟ ᴡɪɴs: <code>{g_wins}</code></blockquote>\n\n"
        "🎋 <i>Keep chatting and winning challenges to level up!</i>"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Group Top 10", callback_data=f"rank_view_group_{target_user.id}"),
            InlineKeyboardButton("🌐 Global Top 10", callback_data=f"rank_view_global_{target_user.id}"),
        ],
        [
            InlineKeyboardButton("⚡ Start Challenge", callback_data="rank_spawn_challenge"),
            InlineKeyboardButton("❌ ᴄʟᴏsᴇ", callback_data="close_menu"),
        ]
    ])

    sent = await msg.reply_html(card_text, reply_markup=keyboard)
    from KITTUBOT.core.cleaner import track_menu
    if chat and chat.type not in ["private", "channel"]:
        await track_menu(context, chat.id, sent.message_id, auto_delete_seconds=180, is_group=True)


async def grouprank_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays Top 10 ranked chatters in this group."""
    chat = update.effective_chat
    msg = update.effective_message

    if chat.type in ["private", "channel"]:
        await msg.reply_html("⚠️ Group leaderboard is only available inside Telegram groups!")
        return

    top_members = await get_group_leaderboard(chat.id, limit=10)
    if not top_members:
        await msg.reply_html("📊 <b>No ranking activity recorded yet!</b> Start chatting to rank up.")
        return

    medals = ["🥇", "🥈", "🥉", "4.", "5.", "6.", "7.", "8.", "9.", "10."]
    lines = []
    for i, m in enumerate(top_members):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        name = m.get("first_name", "Anonymous")
        pts = m.get("points", 0)
        msgs = m.get("messages", 0)
        lines.append(f"{medal} <b>{name}</b> — <code>{pts:,} XP</code> (💬 {msgs:,})")

    body = "\n".join(lines)
    board_text = (
        f"🏆 <b>ɢʀᴏᴜᴘ ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ</b> — <b>{chat.title}</b> 🎌\n\n"
        f"<blockquote>{body}</blockquote>\n\n"
        "🎋 <i>Send messages or win /challenge to climb the ranks!</i>"
    )

    await msg.reply_html(board_text)


async def topgame_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays Global Top 10 active players across all Telegram groups."""
    msg = update.effective_message
    top_global = await get_global_leaderboard(limit=10)
    if not top_global:
        await msg.reply_html("📊 <b>No global ranking records yet!</b>")
        return

    medals = ["🥇", "🥈", "🥉", "4.", "5.", "6.", "7.", "8.", "9.", "10."]
    lines = []
    for i, m in enumerate(top_global):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        name = m.get("first_name", "Player")
        pts = m.get("total_points", 0)
        wins = m.get("total_typing_wins", 0)
        lines.append(f"{medal} <b>{name}</b> — <code>{pts:,} XP</code> (⚡ {wins} wins)")

    body = "\n".join(lines)
    board_text = (
        f"🌐 <b>ɢʟᴏʙᴀʟ ᴛᴏᴘ ᴘʟᴀʏᴇʀs ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ</b> 👑\n\n"
        f"<blockquote>{body}</blockquote>\n\n"
        "🎋 <i>Compete across all chats to claim the #1 spot!</i>"
    )

    await msg.reply_html(board_text)


async def autochallenge_toggle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to toggle automatic periodic speed-typing challenges."""
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    if chat.type in ["private", "channel"]:
        await msg.reply_html("⚠️ Only usable inside groups!")
        return

    member = await chat.get_member(user.id)
    if member.status not in ["creator", "administrator"]:
        await msg.reply_html("⚠️ Only group administrators can configure auto-challenges!")
        return

    if not context.args or context.args[0].lower() not in ["on", "off", "enable", "disable"]:
        chat_data = await get_chat(chat.id)
        current = "ON" if chat_data and chat_data.get("autochallenge") else "OFF"
        await msg.reply_html(
            f"⚡ <b>Auto-Challenge Status:</b> <code>{current}</code>\n\n"
            "Usage: <code>/autochallenge on</code> or <code>/autochallenge off</code>"
        )
        return

    choice = context.args[0].lower() in ["on", "enable"]
    await set_chat_setting(chat.id, "autochallenge", choice)
    status_str = "ENABLED ✅" if choice else "DISABLED ❌"
    await msg.reply_html(f"⚡ <b>Auto Speed-Typing Challenges {status_str}!</b>")


from KITTUBOT.core.cleaner import touch_menu

async def ranking_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles inline buttons on ranking cards."""
    query = update.callback_query
    await query.answer()
    data = query.data
    chat = update.effective_chat

    if data.startswith("rank_view_group"):
        uid = data.split("_")[-1] if "_" in data else "0"
        top_members = await get_group_leaderboard(chat.id, limit=10)
        if not top_members:
            body = "<i>No rankings recorded yet in this group!</i>"
        else:
            medals = ["🥇", "🥈", "🥉", "4.", "5.", "6.", "7.", "8.", "9.", "10."]
            lines = [f"{medals[i]} <b>{m.get('first_name', 'User')}</b> — <code>{m.get('points', 0):,} XP</code>" for i, m in enumerate(top_members)]
            body = chr(10).join(lines)
        
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data=f"rank_back_{uid}"),
                InlineKeyboardButton("❌ ᴄʟᴏsᴇ", callback_data="close_menu"),
            ]
        ])
        text = f"🏆 <b>ɢʀᴏᴜᴘ ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ</b> — <b>{chat.title}</b>\n\n<blockquote>{body}</blockquote>"
        try:
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=kb)
            if chat:
                touch_menu(context, chat.id)
        except Exception:
            pass

    elif data.startswith("rank_view_global"):
        uid = data.split("_")[-1] if "_" in data else "0"
        top_global = await get_global_leaderboard(limit=10)
        if not top_global:
            body = "<i>No global rankings recorded yet!</i>"
        else:
            medals = ["🥇", "🥈", "🥉", "4.", "5.", "6.", "7.", "8.", "9.", "10."]
            lines = [f"{medals[i]} <b>{m.get('first_name', 'Player')}</b> — <code>{m.get('total_points', 0):,} XP</code>" for i, m in enumerate(top_global)]
            body = chr(10).join(lines)

        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data=f"rank_back_{uid}"),
                InlineKeyboardButton("❌ ᴄʟᴏsᴇ", callback_data="close_menu"),
            ]
        ])
        text = f"🌐 <b>ɢʟᴏʙᴀʟ ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ</b>\n\n<blockquote>{body}</blockquote>"
        try:
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=kb)
            if chat:
                touch_menu(context, chat.id)
        except Exception:
            pass

    elif data.startswith("rank_back_"):
        target_uid = int(data.split("_")[2])
        # Re-fetch user rank and display
        rank, chat_data = await get_user_chat_rank(chat.id, target_uid)
        g_stats = await get_user_global_stats(target_uid)

        points = chat_data.get("points", 0) if chat_data else 0
        messages = chat_data.get("messages", 0) if chat_data else 0
        wins = chat_data.get("typing_wins", 0) if chat_data else 0
        tier = get_user_tier(points)
        rank_str = f"#{rank}" if rank > 0 else "Unranked"

        g_points = g_stats.get("total_points", points)
        g_msgs = g_stats.get("total_messages", messages)
        g_wins = g_stats.get("total_typing_wins", wins)

        if target_uid == query.from_user.id:
            user_label = query.from_user.mention_html()
        else:
            first_name = chat_data.get("first_name", "User") if chat_data else "User"
            user_label = f"<b>{first_name}</b>"

        card_text = (
            f"🏆 <b>ᴋɪᴛᴛᴜ ᴄʜᴀᴛ ʀᴀɴᴋɪɴɢ sᴛᴀᴛᴜs</b> 🎌\n\n"
            f"<blockquote>👤 <b>ᴜsᴇʀ :</b> {user_label}\n"
            f"🎖️ <b>ᴛɪᴇʀ :</b> {tier}\n"
            f"📊 <b>ɢʀᴏᴜᴘ ʀᴀɴᴋ :</b> <code>{rank_str}</code>\n"
            f"✨ <b>ɢʀᴏᴜᴘ xᴘ :</b> <code>{points:,} Points</code>\n"
            f"💬 <b>ᴍᴇssᴀɢᴇs :</b> <code>{messages:,}</code>\n"
            f"⚡ <b>ᴛʏᴘɪɴɢ ᴡɪɴs :</b> <code>{wins}</code></blockquote>\n\n"
            f"<blockquote>🌐 <b>ɢʟᴏʙᴀʟ sᴛᴀᴛs:</b>\n"
            f"• ᴛᴏᴛᴀʟ xᴘ: <code>{g_points:,}</code>\n"
            f"• ᴛᴏᴛᴀʟ ᴍsɢs: <code>{g_msgs:,}</code>\n"
            f"• ɢʟᴏʙᴀʟ ᴡɪɴs: <code>{g_wins}</code></blockquote>\n\n"
            "🎋 <i>Keep chatting and winning challenges to level up!</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📊 Group Top 10", callback_data=f"rank_view_group_{target_uid}"),
                InlineKeyboardButton("🌐 Global Top 10", callback_data=f"rank_view_global_{target_uid}"),
            ],
            [
                InlineKeyboardButton("⚡ Start Challenge", callback_data="rank_spawn_challenge"),
                InlineKeyboardButton("❌ ᴄʟᴏsᴇ", callback_data="close_menu"),
            ]
        ])
        try:
            await query.edit_message_text(text=card_text, parse_mode="HTML", reply_markup=keyboard)
            if chat:
                touch_menu(context, chat.id)
        except Exception:
            pass

    elif data == "rank_spawn_challenge":
        await challenge_command(update, context)


async def ranking_message_listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Listens to every chat message:
    1. Records activity points & message count.
    2. Checks if text matches active speed-typing challenge.
    """
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    if not chat or chat.type in ["private", "channel"] or not user or user.is_bot:
        return

    # Non-blocking chat activity logging
    asyncio.create_task(record_chat_activity(chat.id, user, points_earned=1))

    if not msg or not msg.text:
        return

    text = msg.text.strip().lower()

    # Check active speed-typing challenge
    if chat.id in ACTIVE_CHALLENGES:
        challenge = ACTIVE_CHALLENGES[chat.id]
        if time.time() > challenge["expires_at"]:
            del ACTIVE_CHALLENGES[chat.id]
            return

        if text == challenge["word"]:
            # Winner found!
            reward_coins = challenge["reward_coins"]
            reward_points = challenge["reward_points"]
            del ACTIVE_CHALLENGES[chat.id]

            await award_typing_win(chat.id, user, reward_points, reward_coins)

            await msg.reply_html(
                f"⚡ <b>sᴘᴇᴇᴅ-ᴛʏᴘɪɴɢ ᴡɪɴɴᴇʀ!</b> 🎌🏆\n\n"
                f"<blockquote>👑 {user.mention_html()} typed <b>{text.upper()}</b> first!\n"
                f"💰 <b>Reward:</b> <code>+{reward_coins:,} Coins</code>\n"
                f"✨ <b>XP Gained:</b> <code>+{reward_points} Points</code></blockquote>\n\n"
                "🎋 <i>Keep chatting or use /challenge for the next contest!</i>"
            )


def register_handlers(app: Application):
    app.add_handler(CommandHandler(["ranking", "myrank", "rank"], ranking_command))
    app.add_handler(CommandHandler(["grouprank", "topchat", "leaderboard"], grouprank_command))
    app.add_handler(CommandHandler(["topgame", "topglobal", "topusers"], topgame_command))
    app.add_handler(CommandHandler(["challenge", "speedtype", "typing", "typegame"], challenge_command))
    app.add_handler(CommandHandler(["autochallenge", "autospeed"], autochallenge_toggle_command))
    app.add_handler(CallbackQueryHandler(ranking_callback_handler, pattern=r"^rank_"))

    # Global activity & challenge answer listener (group=10 ensures priority without blocking commands)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, ranking_message_listener),
        group=10,
    )
