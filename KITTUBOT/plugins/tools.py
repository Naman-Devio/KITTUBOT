# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Group Utilities & Tools Engine
Identity info (/id, /info), Google Translate (/tr), Wikipedia search (/wiki), and Pastebin (/paste).
"""

import aiohttp
import urllib.parse
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from KITTUBOT.config import config
from KITTUBOT.database.users import get_user
from KITTUBOT.core.permissions import resolve_target_user, TargetUser

__mod_name__ = "Tools"
__help__ = """
<blockquote>🛠️ <b>ᴜᴛɪʟɪᴛɪᴇs & ᴛᴏᴏʟs:</b>
• <code>/info [reply|@user|id]</code> - ᴜsᴇʀ ɪᴅ, ᴅᴄ & ᴘʀᴏғɪʟᴇ sᴛᴀᴛs
• <code>/id</code> - ᴠɪᴇᴡ ʏᴏᴜʀs ᴏʀ ᴄʜᴀᴛ's ɪᴅ
• <code>/tr [lang] [txt]</code> - ᴛʀᴀɴsʟᴀᴛᴇ ᴀɴʏ ᴛᴇxᴛ
• <code>/wiki [query]</code> - ɪɴsᴛᴀɴᴛ ᴡɪᴋɪᴘᴇᴅɪᴀ sᴜᴍᴍᴀʀʏ
• <code>/paste [txt]</code> - (ʀᴇᴘʟʏ) ᴜᴘʟᴏᴀᴅ ᴄᴏᴅᴇ ᴛᴏ ᴘᴀsᴛᴇʙɪɴ</blockquote>
"""


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    reply = update.message.reply_to_message

    text = f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
    if reply and reply.from_user:
        text += f"👤 <b>Replied User ID:</b> <code>{reply.from_user.id}</code>\n"
    if chat.type != "private":
        text += f"💬 <b>Chat ID:</b> <code>{chat.id}</code>\n"
    if reply and reply.forward_from:
        text += f"🔄 <b>Forwarded From ID:</b> <code>{reply.forward_from.id}</code>\n"

    await update.message.reply_html(f"<blockquote>{text.strip()}</blockquote>")


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target, _ = await resolve_target_user(update, context)
    if not target:
        user = update.effective_user
        target = TargetUser(user.id, user.first_name, user.username or "", user)

    u_data = await get_user(target.id)
    balance = u_data.get("balance", 0) if u_data else 0
    kills = u_data.get("kills", 0) if u_data else 0
    deaths = u_data.get("deaths", 0) if u_data else 0

    username_str = f"@{target.username}" if target.username else "None"
    premium_str = "Yes ⭐" if (target.user and target.user.is_premium) else "No"

    text = (
        f"👤 <b>ᴜsᴇʀ ɪɴғᴏʀᴍᴀᴛɪᴏɴ — {target.first_name}</b>\n\n"
        f"<blockquote>• <b>First Name :</b> {target.first_name}\n"
        f"• <b>User ID :</b> <code>{target.id}</code>\n"
        f"• <b>Username :</b> {username_str}\n"
        f"• <b>Telegram Premium :</b> {premium_str}\n"
        f"• <b>Kittu Wallet :</b> <code>{balance:,} Coins</code>\n"
        f"• <b>RPG Stats :</b> {kills} Kills | {deaths} Deaths</blockquote>\n\n"
        f"🔗 <a href=\"tg://user?id={target.id}\">Permanent Profile Link</a>"
    )

    await update.message.reply_html(text)


async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply = update.message.reply_to_message
    target_lang = "en"
    text_to_tr = ""

    if context.args:
        # Check if first arg is language code
        if len(context.args[0]) in [2, 3]:
            target_lang = context.args[0].lower()
            text_to_tr = " ".join(context.args[1:]).strip()
        else:
            text_to_tr = " ".join(context.args).strip()

    if not text_to_tr and reply and reply.text:
        text_to_tr = reply.text

    if not text_to_tr:
        await update.message.reply_html(
            "🌐 <b>Usage:</b> <code>/tr [language_code] [text]</code>\n"
            "Or reply to a message with <code>/tr [lang]</code> (e.g. <code>/tr hi</code> for Hindi)"
        )
        return

    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_lang}&dt=t&q={urllib.parse.quote(text_to_tr)}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    translated = "".join(part[0] for part in data[0] if part[0])
                    detected_lang = data[2] if len(data) > 2 else "auto"

                    await update.message.reply_html(
                        f"🌐 <b>ᴛʀᴀɴsʟᴀᴛɪᴏɴ ({detected_lang.upper()} ➡️ {target_lang.upper()}):</b>\n\n"
                        f"<blockquote>{translated}</blockquote>"
                    )
                else:
                    await update.message.reply_html("❌ Translation API error!")
    except Exception as e:
        await update.message.reply_html(f"❌ Failed to translate: <code>{e}</code>")


async def wiki_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_html("📚 <b>Usage:</b> <code>/wiki <query></code> (e.g. <code>/wiki Albert Einstein</code>)")
        return

    query = " ".join(context.args).strip()
    encoded = urllib.parse.quote(query.replace(" ", "_"))
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    title = data.get("title", query)
                    extract = data.get("extract", "No summary found.")
                    page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")

                    await update.message.reply_html(
                        f"📖 <b>{title} — Wikipedia</b>\n\n"
                        f"<blockquote>{extract[:800]}...</blockquote>\n\n"
                        f"🔗 <a href=\"{page_url}\">Read full article</a>"
                    )
                else:
                    await update.message.reply_html(f"❌ No Wikipedia page found for '<b>{query}</b>'.")
    except Exception as e:
        await update.message.reply_html(f"❌ Failed to fetch Wikipedia: <code>{e}</code>")


async def paste_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply = update.message.reply_to_message
    content = ""
    if context.args:
        content = " ".join(context.args)
    elif reply and reply.text:
        content = reply.text
    else:
        await update.message.reply_html("📋 <b>Reply to text</b> or provide text to upload to pastebin!")
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://paste.rs", data=content, timeout=10) as resp:
                if resp.status in [200, 201]:
                    paste_url = (await resp.text()).strip()
                    await update.message.reply_html(
                        f"📋 <b>ᴘᴀsᴛᴇ sᴜᴄᴄᴇssғᴜʟ!</b>\n\n"
                        f"<blockquote>🔗 <b>Link:</b> {paste_url}</blockquote>"
                    )
                else:
                    await update.message.reply_html("❌ Failed to paste content.")
    except Exception as e:
        await update.message.reply_html(f"❌ Paste error: <code>{e}</code>")


def register_handlers(app: Application):
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler(["info", "whois"], info_command))
    app.add_handler(CommandHandler(["tr", "translate"], translate_command))
    app.add_handler(CommandHandler(["wiki", "wikipedia"], wiki_command))
    app.add_handler(CommandHandler("paste", paste_command))
