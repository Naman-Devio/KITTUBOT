# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Quotly & Quote Sticker Generator Plugin
Generates high-aesthetic Telegram quote stickers from replied messages or custom text.
Dual-engine: Quotly API + High-fidelity built-in Pillow offline renderer.
"""

import os
import io
import time
import textwrap
import base64
import httpx
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from KITTUBOT import log

__mod_name__ = "Quotes"
__help__ = """
<blockquote>💬 <b>ǫᴜᴏᴛʟʏ sᴛɪᴄᴋᴇʀ ɢᴇɴᴇʀᴀᴛᴏʀ:</b>
• <code>/q</code> or <code>/quote</code> - (ʀᴇᴘʟʏ) ᴛᴜʀɴ ᴍᴇssᴀɢᴇ ɪɴᴛᴏ ᴀ sᴛɪᴄᴋᴇʀ
• <code>/fakequote [name] | [text]</code> - ᴄʀᴇᴀᴛᴇ ᴀ ғᴜɴ ғᴀᴋᴇ ǫᴜᴏᴛᴇ

<i>✨ Works with emojis, user avatars, and custom colors!</i></blockquote>
"""

ACCENT_COLORS = [
    (255, 126, 182),  # Pink
    (79, 172, 254),   # Sky blue
    (0, 242, 254),    # Cyan
    (254, 209, 54),   # Gold
    (168, 85, 247),   # Purple
    (52, 211, 153),   # Emerald
]


def render_local_quote(
    name: str,
    text: str,
    avatar_image: Image.Image | None = None,
    color_seed: int = 0,
) -> io.BytesIO:
    """Renders a beautiful Telegram dark-mode message bubble sticker using Pillow."""
    width = 512
    margin = 16
    avatar_size = 56

    accent_color = ACCENT_COLORS[abs(color_seed) % len(ACCENT_COLORS)]

    # Word wrapping text
    wrapped_lines = textwrap.wrap(text, width=32)
    if not wrapped_lines:
        wrapped_lines = ["..."]

    # Calculate bubble height
    line_height = 24
    content_height = max(avatar_size, 30 + len(wrapped_lines) * line_height)
    height = min(600, content_height + 40)

    # Base transparent canvas
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Bubble background
    bubble_x0 = margin + avatar_size + 12
    bubble_y0 = margin
    bubble_x1 = width - margin
    bubble_y1 = height - margin

    draw.rounded_rectangle(
        [(bubble_x0, bubble_y0), (bubble_x1, bubble_y1)],
        radius=18,
        fill=(24, 27, 36, 245),
        outline=(45, 52, 70, 200),
        width=1,
    )

    # Avatar
    av_x = margin
    av_y = margin
    if avatar_image:
        try:
            av = avatar_image.resize((avatar_size, avatar_size)).convert("RGBA")
            # Circular mask
            mask = Image.new("L", (avatar_size, avatar_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
            img.paste(av, (av_x, av_y), mask)
        except Exception:
            avatar_image = None

    if not avatar_image:
        # Fallback stylish avatar circle with user's initial
        draw.ellipse([(av_x, av_y), (av_x + avatar_size, av_y + avatar_size)], fill=accent_color)
        initial = name[0].upper() if name else "?"
        draw.text((av_x + 18, av_y + 12), initial, fill=(255, 255, 255, 255))

    # Name text
    text_x = bubble_x0 + 16
    text_y = bubble_y0 + 12
    draw.text((text_x, text_y), name[:25], fill=accent_color)

    # Body text
    cur_y = text_y + 24
    for line in wrapped_lines:
        draw.text((text_x, cur_y), line, fill=(240, 243, 246, 255))
        cur_y += line_height

    out = io.BytesIO()
    img.save(out, format="WEBP")
    out.seek(0)
    return out


async def generate_quote_from_api(name: str, user_id: int, text: str, avatar_url: str = "") -> io.BytesIO | None:
    """Attempts to generate a quote using public Quotly API."""
    url = "https://bot.lyo.su/quote/generate"
    payload = {
        "type": "quote",
        "format": "webp",
        "backgroundColor": "#18191E",
        "width": 512,
        "height": 768,
        "scale": 2,
        "messages": [
            {
                "entities": [],
                "chatId": user_id,
                "avatar": True,
                "from": {
                    "id": user_id,
                    "first_name": name,
                    "name": name,
                },
                "text": text,
            }
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code == 200:
                data = res.json()
                if data.get("ok") and "image" in data.get("result", {}):
                    raw = base64.b64decode(data["result"]["image"])
                    buf = io.BytesIO(raw)
                    buf.seek(0)
                    return buf
    except Exception:
        pass
    return None


async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    reply = message.reply_to_message

    if not reply:
        await message.reply_html("⚠️ <b>Reply to any message</b> to generate a quote sticker! E.g. <code>/q</code>")
        return

    author = reply.from_user
    name = author.first_name if author else (reply.sender_chat.title if reply.sender_chat else "Anonymous")
    text = reply.text or reply.caption or "..."
    user_id = author.id if author else 0

    status_msg = await message.reply_html("🎨 <i>Crafting quote sticker...</i>")

    # Try Quotly API first
    sticker_buf = await generate_quote_from_api(name, user_id, text)

    # Offline fallback renderer with user avatar
    if not sticker_buf:
        avatar_img = None
        if author:
            try:
                photos = await context.bot.get_user_profile_photos(author.id, limit=1)
                if photos and photos.total_count > 0:
                    photo_file = await photos.photos[0][0].get_file()
                    photo_bytes = await photo_file.download_as_bytearray()
                    avatar_img = Image.open(io.BytesIO(photo_bytes))
            except Exception:
                pass

        sticker_buf = render_local_quote(
            name=name,
            text=text,
            avatar_image=avatar_img,
            color_seed=user_id,
        )

    try:
        await status_msg.delete()
    except Exception:
        pass

    try:
        await message.reply_sticker(sticker=sticker_buf)
    except Exception as e:
        log.warning(f"Failed to send quote sticker: {e}")
        sticker_buf.seek(0)
        await message.reply_photo(photo=sticker_buf, caption=f"💬 <b>Quote by {name}</b>", parse_mode="HTML")


async def fakequote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not context.args:
        await message.reply_html("⚠️ <b>Usage:</b> <code>/fakequote [name] | [quote text]</code>")
        return

    raw = " ".join(context.args)
    if "|" in raw:
        parts = raw.split("|", 1)
        name = parts[0].strip()
        text = parts[1].strip()
    else:
        name = "Kittu"
        text = raw.strip()

    sticker_buf = render_local_quote(
        name=name,
        text=text,
        color_seed=len(name),
    )

    try:
        await message.reply_sticker(sticker=sticker_buf)
    except Exception:
        sticker_buf.seek(0)
        await message.reply_photo(photo=sticker_buf, caption=f"💬 <b>Fake Quote by {name}</b>", parse_mode="HTML")


def register_handlers(app: Application):
    app.add_handler(CommandHandler(["q", "quote"], quote_command))
    app.add_handler(CommandHandler(["fakequote", "fq"], fakequote_command))
