# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Social, Marriage & Couple Plugin
Generates real high-resolution graphic couple frames (cppic.png) with circular Telegram profile avatars!
Also handles propose, marry, divorce, and relationship tracking.
"""

import os
import io
import random
from pathlib import Path
from datetime import datetime
import pytz
from PIL import Image, ImageDraw, ImageOps
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from KITTUBOT.config import config
from KITTUBOT.database.users import ensure_user, get_user, update_balance
from KITTUBOT.database.chats import get_chat_active_members
from KITTUBOT.database import couples_col, users_col
from KITTUBOT import log

__mod_name__ = "Social"
__help__ = """
<blockquote>❤️ <b>sᴏᴄɪᴀʟ & ʀᴇʟᴀᴛɪᴏɴsʜɪᴘs:</b>
• <code>/couple</code> - ɢᴇɴᴇʀᴀᴛᴇ ᴛᴏᴅᴀʏ's ɢʀᴀᴘʜɪᴄ ᴄᴏᴜᴘʟᴇ ᴘʜᴏᴛᴏ!
• <code>/propose</code> - (ʀᴇᴘʟʏ) ᴘʀᴏᴘᴏsᴇ ᴍᴀʀʀɪᴀɢᴇ
• <code>/divorce</code> - ᴅɪssᴏʟᴠᴇ ᴍᴀʀʀɪᴀɢᴇ ᴛɪᴇs</blockquote>
"""

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
BG_FRAME_PATH = ASSETS_DIR / "cppic.png"
FALLBACK_AVATAR_PATH = ASSETS_DIR / "upic.png"
TEMP_DIR = Path("temp_couples")
TEMP_DIR.mkdir(parents=True, exist_ok=True)


async def get_circular_avatar(bot, user_id: int) -> Image.Image:
    """Downloads user Telegram profile avatar and crops into high-res circle for couple frame."""
    size = (437, 437)
    temp_avatar = TEMP_DIR / f"avatar_{user_id}.png"
    img = None

    try:
        photos = await bot.get_user_profile_photos(user_id, limit=1)
        if photos and photos.total_count > 0:
            file = await bot.get_file(photos.photos[0][-1].file_id)
            await file.download_to_drive(temp_avatar)
            img = Image.open(temp_avatar).convert("RGBA")
    except Exception as e:
        log.warning(f"Failed to fetch profile photo for {user_id}: {e}")

    if not img:
        if FALLBACK_AVATAR_PATH.exists():
            img = Image.open(FALLBACK_AVATAR_PATH).convert("RGBA")
        else:
            img = Image.new("RGBA", size, (255, 105, 180, 255))

    img = img.resize(size, Image.LANCZOS)
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + size, fill=255)

    output = ImageOps.fit(img, size, centering=(0.5, 0.5))
    output.putalpha(mask)

    if temp_avatar.exists():
        try:
            os.remove(temp_avatar)
        except Exception:
            pass

    return output


async def couple_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_html("⚠️ This command is for group chats!")
        return

    today_str = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%d/%m/%Y")
    existing = await couples_col.find_one({"chat_id": chat.id, "date": today_str})

    if existing:
        c1 = existing.get("user1_name", "Someone")
        c2 = existing.get("user2_name", "Someone")
        compat = existing.get("compatibility", 95)
        saved_img = existing.get("img_path")
        caption = (
            f"❤️ <b>ᴛᴏᴅᴀʏ's ʙʟᴇssᴇᴅ ᴄᴏᴜᴘʟᴇ ({today_str}):</b>\n\n"
            f"<blockquote>👑 <b>{c1}</b>  💖  <b>{c2}</b>\n"
            f"💍 <b>ʟᴏᴠᴇ ᴄᴏᴍᴘᴀᴛɪʙɪʟɪᴛʏ :</b> <code>{compat}%</code></blockquote>\n\n"
            f"🎋 <i>Next couple will be crowned tomorrow!</i>"
        )
        if saved_img and os.path.exists(saved_img):
            await update.message.reply_photo(photo=open(saved_img, "rb"), caption=caption, parse_mode="HTML")
            return
        await update.message.reply_html(caption)
        return

    status_msg = await update.message.reply_html("💘 <i>Selecting today's couple & generating romantic portrait...</i>")

    # Pick 2 members: prefer active members tracked in chat, fallback to general users
    active_m = await get_chat_active_members(chat.id)
    if len(active_m) >= 2:
        pair = random.sample(active_m, 2)
        u1_id, name1 = pair[0]["id"], pair[0]["name"]
        u2_id, name2 = pair[1]["id"], pair[1]["name"]
    else:
        cursor = users_col.find({}).limit(50)
        user_list = await cursor.to_list(length=50)
        if len(user_list) < 2:
            await status_msg.edit_text("⚠️ Need at least 2 active players in the bot to select a couple!")
            return
        pair = random.sample(user_list, 2)
        u1_id, name1 = pair[0]["user_id"], pair[0].get("first_name", "Romeo")
        u2_id, name2 = pair[1]["user_id"], pair[1].get("first_name", "Juliet")

    compat = random.randint(75, 100)

    # Generate visual couple image
    final_img_path = str(TEMP_DIR / f"couple_{chat.id}_{today_str.replace('/', '_')}.png")
    photo_generated = False

    if BG_FRAME_PATH.exists():
        try:
            base = Image.open(BG_FRAME_PATH).convert("RGBA")
            p1_img = await get_circular_avatar(context.bot, u1_id)
            p2_img = await get_circular_avatar(context.bot, u2_id)

            # Paste circular avatars at frame coordinate cutouts
            base.paste(p1_img, (116, 160), p1_img)
            base.paste(p2_img, (789, 160), p2_img)

            base.save(final_img_path, "PNG")
            photo_generated = True
        except Exception as e:
            log.error(f"Error generating couple photo: {e}")

    await couples_col.insert_one({
        "chat_id": chat.id,
        "date": today_str,
        "user1_id": u1_id,
        "user1_name": name1,
        "user2_id": u2_id,
        "user2_name": name2,
        "compatibility": compat,
        "img_path": final_img_path if photo_generated else "",
    })

    caption = (
        f"💘 <b>ᴋɪᴛᴛᴜ ᴍᴀᴛᴄʜᴍᴀᴋᴇʀ ʜᴀs sᴘᴏᴋᴇɴ!</b> 💍✨\n\n"
        f"<blockquote>✨ <b>ᴛᴏᴅᴀʏ's ᴄᴏᴜᴘʟᴇ ({today_str}):</b>\n"
        f"👑 <b>{name1}</b>  💖  <b>{name2}</b>\n"
        f"👩‍❤️‍👨 <b>ʟᴏᴠᴇ ᴄᴏᴍᴘᴀᴛɪʙɪʟɪᴛʏ :</b> <code>{compat}%</code></blockquote>\n\n"
        f"🎋 <i>May your love story be filled with coins and victories!</i> 🥂"
    )

    try:
        await status_msg.delete()
    except Exception:
        pass

    if photo_generated and os.path.exists(final_img_path):
        await update.message.reply_photo(
            photo=open(final_img_path, "rb"),
            caption=caption,
            parse_mode="HTML",
        )
    else:
        await update.message.reply_html(caption)


async def propose_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    reply = update.message.reply_to_message

    if not reply or not reply.from_user or reply.from_user.is_bot:
        await update.message.reply_html("⚠️ <b>Reply to the person</b> you want to propose to!")
        return

    target = reply.from_user
    if target.id == user.id:
        await update.message.reply_html("😂 You cannot propose to yourself!")
        return

    u_data = await ensure_user(user)
    if u_data.get("spouse_id"):
        await update.message.reply_html("💍 You are already married! Divorce first using <code>/divorce</code>.")
        return

    target_data = await ensure_user(target)
    if target_data.get("spouse_id"):
        await update.message.reply_html(f"💔 {target.mention_html()} is already married to someone else!")
        return

    if u_data.get("balance", 0) < config.PROPOSE_COST:
        await update.message.reply_html(
            f"❌ You need <b>{config.PROPOSE_COST:,} Coins</b> to buy an engagement ring!"
        )
        return

    await update_balance(user.id, -config.PROPOSE_COST)
    await users_col.update_one({"user_id": user.id}, {"$set": {"spouse_id": target.id}})
    await users_col.update_one({"user_id": target.id}, {"$set": {"spouse_id": user.id}})

    await update.message.reply_html(
        f"💍 <b>ᴍᴀʀʀɪᴀɢᴇ ᴄᴏɴɢʀᴀᴛᴜʟᴀᴛɪᴏɴs!</b>\n\n"
        f"<blockquote>{user.mention_html()} put a ring on {target.mention_html()}'s finger! 🥂🎉\n"
        f"Ring fee paid: <b>{config.PROPOSE_COST:,} Coins</b>.</blockquote>"
    )


async def divorce_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u_data = await ensure_user(user)
    spouse_id = u_data.get("spouse_id", 0)

    if not spouse_id:
        await update.message.reply_html("🤷 You are not married to anyone!")
        return

    if u_data.get("balance", 0) < config.DIVORCE_COST:
        await update.message.reply_html(f"❌ Divorce lawyer fees cost <b>{config.DIVORCE_COST:,} Coins</b>!")
        return

    await update_balance(user.id, -config.DIVORCE_COST)
    await users_col.update_one({"user_id": user.id}, {"$set": {"spouse_id": 0}})
    await users_col.update_one({"user_id": spouse_id}, {"$set": {"spouse_id": 0}})

    await update.message.reply_html(
        f"💔 <b>ᴅɪᴠᴏʀᴄᴇ ғɪɴᴀʟɪᴢᴇᴅ!</b>\n\n"
        f"<blockquote>{user.mention_html()} has officially broken their marriage ties.\n"
        f"Legal fee paid: <b>{config.DIVORCE_COST:,} Coins</b>.</blockquote>"
    )


def register_handlers(app: Application):
    app.add_handler(CommandHandler(["couple", "ship"], couple_command))
    app.add_handler(CommandHandler("propose", propose_command))
    app.add_handler(CommandHandler("divorce", divorce_command))
