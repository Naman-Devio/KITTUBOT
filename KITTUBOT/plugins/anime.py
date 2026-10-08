# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Anime & Manga Discovery Plugin
Powered by AniList GraphQL API.
Instant search for Anime, Manga, Characters, and Airing charts.
"""

import re
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from KITTUBOT import log

__mod_name__ = "Anime"
__help__ = """
<blockquote>⛩️ <b>ᴀɴɪᴍᴇ & ᴍᴀɴɢᴀ ʜᴜʙ:</b>
• <code>/anime [title]</code> - sᴇᴀʀᴄʜ ᴀɴɪᴍᴇ ᴅᴇᴛᴀɪʟs & sᴛᴀᴛs
• <code>/manga [title]</code> - sᴇᴀʀᴄʜ ᴍᴀɴɢᴀ ᴄʜᴀᴘᴛᴇʀs & sʏɴᴏᴘsɪs
• <code>/character [name]</code> - sᴇᴀʀᴄʜ ᴀɴɪᴍᴇ ᴄʜᴀʀᴀᴄᴛᴇʀ ʙɪᴏ
• <code>/airing</code> - ᴛᴏᴘ ᴛʀᴇɴᴅɪɴɢ ᴀɪʀɪɴɢ ᴀɴɪᴍᴇ</blockquote>
"""

ANILIST_API = "https://graphql.anilist.co"


def clean_html(raw_html: str) -> str:
    """Cleans HTML tags into clean plaintext for Telegram captions."""
    if not raw_html:
        return "No description available."
    cleaned = re.sub(r"<br\s*/?>", "\n", raw_html)
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    cleaned = re.sub(r"&[a-z]+;", "", cleaned)
    return cleaned.strip()


async def anime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not context.args:
        await message.reply_html("⚠️ <b>Specify an anime title!</b> E.g. <code>/anime Solo Leveling</code>")
        return

    title_query = " ".join(context.args).strip()
    status_msg = await message.reply_html("⛩️ <i>Searching AniList archives...</i>")

    query = """
    query ($search: String) {
      Media(search: $search, type: ANIME) {
        id
        title {
          romaji
          english
          native
        }
        format
        status
        episodes
        duration
        averageScore
        genres
        description(asHtml: false)
        coverImage {
          large
          extraLarge
        }
        siteUrl
      }
    }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(ANILIST_API, json={"query": query, "variables": {"search": title_query}})
            if res.status_code != 200:
                await status_msg.edit_text("❌ Anime not found on AniList!")
                return

            data = res.json().get("data", {}).get("Media")
            if not data:
                await status_msg.edit_text("❌ Anime not found on AniList!")
                return

            romaji = data.get("title", {}).get("romaji", "Unknown")
            english = data.get("title", {}).get("english") or romaji
            native = data.get("title", {}).get("native", "")
            episodes = data.get("episodes") or "?"
            duration = data.get("duration") or "?"
            score = data.get("averageScore") or "N/A"
            status = data.get("status", "Unknown").replace("_", " ").title()
            genres = ", ".join(data.get("genres", [])[:4]) or "General"
            desc = clean_html(data.get("description", ""))
            if len(desc) > 350:
                desc = desc[:347] + "..."

            img_url = data.get("coverImage", {}).get("extraLarge") or data.get("coverImage", {}).get("large")
            site_url = data.get("siteUrl", "https://anilist.co")

            caption = (
                f"⛩️ <b>{english}</b>\n"
                f"<i>({romaji} • {native})</i>\n\n"
                f"<blockquote>📊 <b>sᴄᴏʀᴇ :</b> <code>{score}/100</code> ⭐\n"
                f"🎞️ <b>ᴇᴘɪsᴏᴅᴇs :</b> <code>{episodes} ({duration} mins)</code>\n"
                f"📡 <b>sᴛᴀᴛᴜs :</b> <b>{status}</b>\n"
                f"🎭 <b>ɢᴇɴʀᴇs :</b> <i>{genres}</i></blockquote>\n\n"
                f"<blockquote>📝 <b>sʏɴᴏᴘsɪs :</b>\n{desc}</blockquote>\n\n"
                f"🔗 <a href='{site_url}'>View on AniList</a>"
            )

            await status_msg.delete()
            if img_url:
                await message.reply_photo(photo=img_url, caption=caption, parse_mode="HTML")
            else:
                await message.reply_html(text=caption)
    except Exception as e:
        log.error(f"Error querying AniList anime: {e}")
        try:
            await status_msg.edit_text(f"❌ Failed to fetch anime: {e}")
        except Exception:
            pass


async def manga_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not context.args:
        await message.reply_html("⚠️ <b>Specify a manga title!</b> E.g. <code>/manga Berserk</code>")
        return

    title_query = " ".join(context.args).strip()
    status_msg = await message.reply_html("📖 <i>Searching Manga archives...</i>")

    query = """
    query ($search: String) {
      Media(search: $search, type: MANGA) {
        id
        title {
          romaji
          english
        }
        status
        chapters
        volumes
        averageScore
        genres
        description(asHtml: false)
        coverImage {
          large
          extraLarge
        }
        siteUrl
      }
    }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(ANILIST_API, json={"query": query, "variables": {"search": title_query}})
            if res.status_code != 200:
                await status_msg.edit_text("❌ Manga not found on AniList!")
                return

            data = res.json().get("data", {}).get("Media")
            if not data:
                await status_msg.edit_text("❌ Manga not found on AniList!")
                return

            romaji = data.get("title", {}).get("romaji", "Unknown")
            english = data.get("title", {}).get("english") or romaji
            chapters = data.get("chapters") or "?"
            volumes = data.get("volumes") or "?"
            score = data.get("averageScore") or "N/A"
            status = data.get("status", "Unknown").replace("_", " ").title()
            genres = ", ".join(data.get("genres", [])[:4]) or "Manga"
            desc = clean_html(data.get("description", ""))
            if len(desc) > 350:
                desc = desc[:347] + "..."

            img_url = data.get("coverImage", {}).get("extraLarge") or data.get("coverImage", {}).get("large")
            site_url = data.get("siteUrl", "https://anilist.co")

            caption = (
                f"📖 <b>{english}</b>\n"
                f"<i>({romaji})</i>\n\n"
                f"<blockquote>📊 <b>sᴄᴏʀᴇ :</b> <code>{score}/100</code> ⭐\n"
                f"📚 <b>ᴄʜᴀᴘᴛᴇʀs :</b> <code>{chapters} (Vols: {volumes})</code>\n"
                f"📡 <b>sᴛᴀᴛᴜs :</b> <b>{status}</b>\n"
                f"🎭 <b>ɢᴇɴʀᴇs :</b> <i>{genres}</i></blockquote>\n\n"
                f"<blockquote>📝 <b>sʏɴᴏᴘsɪs :</b>\n{desc}</blockquote>\n\n"
                f"🔗 <a href='{site_url}'>View on AniList</a>"
            )

            await status_msg.delete()
            if img_url:
                await message.reply_photo(photo=img_url, caption=caption, parse_mode="HTML")
            else:
                await message.reply_html(text=caption)
    except Exception as e:
        log.error(f"Error querying AniList manga: {e}")
        try:
            await status_msg.edit_text(f"❌ Failed to fetch manga: {e}")
        except Exception:
            pass


async def character_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not context.args:
        await message.reply_html("⚠️ <b>Specify character name!</b> E.g. <code>/character Gojo Satoru</code>")
        return

    char_name = " ".join(context.args).strip()
    status_msg = await message.reply_html("🌸 <i>Searching Character archives...</i>")

    query = """
    query ($search: String) {
      Character(search: $search) {
        id
        name {
          full
          native
          alternative
        }
        image {
          large
        }
        description
        siteUrl
      }
    }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(ANILIST_API, json={"query": query, "variables": {"search": char_name}})
            if res.status_code != 200:
                await status_msg.edit_text("❌ Character not found!")
                return

            data = res.json().get("data", {}).get("Character")
            if not data:
                await status_msg.edit_text("❌ Character not found!")
                return

            full_name = data.get("name", {}).get("full", "Unknown")
            native = data.get("name", {}).get("native", "")
            aliases = ", ".join(data.get("name", {}).get("alternative", [])[:3]) or "None"
            desc = clean_html(data.get("description", ""))
            if len(desc) > 350:
                desc = desc[:347] + "..."

            img_url = data.get("image", {}).get("large")
            site_url = data.get("siteUrl", "https://anilist.co")

            caption = (
                f"🌸 <b>{full_name}</b> {f'({native})' if native else ''}\n\n"
                f"<blockquote>🎭 <b>ᴀʟɪᴀsᴇs :</b> <i>{aliases}</i>\n"
                f"🆔 <b>ᴀɴɪʟɪsᴛ ɪᴅ :</b> <code>{data.get('id')}</code></blockquote>\n\n"
                f"<blockquote>📖 <b>ʙɪᴏ :</b>\n{desc}</blockquote>\n\n"
                f"🔗 <a href='{site_url}'>View Profile</a>"
            )

            await status_msg.delete()
            if img_url:
                await message.reply_photo(photo=img_url, caption=caption, parse_mode="HTML")
            else:
                await message.reply_html(text=caption)
    except Exception as e:
        log.error(f"Error querying character: {e}")
        try:
            await status_msg.edit_text(f"❌ Failed to fetch character: {e}")
        except Exception:
            pass


async def airing_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    query = """
    query {
      Page(page: 1, perPage: 10) {
        media(type: ANIME, status: RELEASING, sort: POPULARITY_DESC) {
          title {
            english
            romaji
          }
          episodes
          averageScore
        }
      }
    }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(ANILIST_API, json={"query": query})
            if res.status_code != 200:
                await message.reply_html("❌ Failed to fetch airing anime schedule.")
                return

            items = res.json().get("data", {}).get("Page", {}).get("media", [])
            text = "📺 <b>ᴛᴏᴘ ᴛʀᴇɴᴅɪɴɢ ᴀɪʀɪɴɢ ᴀɴɪᴍᴇ</b> ✨\n\n<blockquote>"
            for idx, item in enumerate(items, 1):
                title = item.get("title", {}).get("english") or item.get("title", {}).get("romaji", "Unknown")
                score = item.get("averageScore") or "N/A"
                text += f"{idx}. <b>{title}</b> — ⭐ <code>{score}%</code>\n"
            text += "</blockquote>"

            await message.reply_html(text)
    except Exception as e:
        await message.reply_html(f"❌ Error fetching airing anime: {e}")


ANIME_QUOTES = [
    ("Believe in yourself. Not in the you who believes in me. Not the me who believes in you. Believe in the you who believes in yourself.", "Kamina", "Tengen Toppa Gurren Lagann"),
    ("It's not the face that makes someone a monster, it's the choices they make with their lives.", "Naruto Uzumaki", "Naruto"),
    ("The only thing that can defeat power is more power. However, there is no point in power if it consumes itself.", "Itachi Uchiha", "Naruto"),
    ("No one knows what the future holds. That's why its potential is infinite.", "Rintarou Okabe", "Steins;Gate"),
    ("The only thing we're allowed to do is to believe that we won't regret the choice we made.", "Levi Ackerman", "Attack on Titan"),
    ("Whatever you do, enjoy it to the fullest. That is the secret of life.", "Iskandar", "Fate/Zero"),
    ("If you don't take risks, you can't create a future.", "Monkey D. Luffy", "One Piece"),
    ("In order to grow, you must face the pain of the past. Accept it and move forward.", "Erza Scarlet", "Fairy Tail"),
    ("If you wanna make people dream, you've gotta start by believing in that dream yourself!", "Shoyo Hinata", "Haikyuu!!"),
    ("Being weak is nothing to be ashamed of. Staying weak is.", "Fuegoleon Vermillion", "Black Clover"),
    ("The world's not perfect, but it's there for us trying the best it can. That's what makes it so damn beautiful.", "Roy Mustang", "Fullmetal Alchemist: Brotherhood"),
    ("In this world, wherever there is light – there are also shadows.", "Madara Uchiha", "Naruto"),
]

ANIME_WALLPAPERS = [
    "https://i.imgur.com/Iub4RYj.jpg",
    "https://i.imgur.com/uvNMdIl.jpg",
    "https://i.imgur.com/YOBOntg.jpg",
    "https://i.imgur.com/fFpO2ZQ.jpg",
    "https://i.imgur.com/f0xZceK.jpg",
    "https://i.imgur.com/RlVcCip.jpg",
    "https://i.imgur.com/CjpqLRF.jpg",
]


async def animequote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quote_text, character, anime = random.choice(ANIME_QUOTES)
    wallpaper = random.choice(ANIME_WALLPAPERS)

    caption = (
        "📜 <b>ɪᴄᴏɴɪᴄ ᴀɴɪᴍᴇ ǫᴜᴏᴛᴇ</b> ✨\n\n"
        f"<blockquote><i>\"{quote_text}\"</i>\n\n"
        f"👑 <b>{character}</b>\n"
        f"⛩️ <b>{anime}</b></blockquote>"
    )

    try:
        await update.message.reply_photo(photo=wallpaper, caption=caption, parse_mode="HTML")
    except Exception:
        await update.message.reply_html(caption)


def register_handlers(app: Application):
    app.add_handler(CommandHandler("anime", anime_command))
    app.add_handler(CommandHandler("manga", manga_command))
    app.add_handler(CommandHandler(["character", "char"], character_command))
    app.add_handler(CommandHandler(["airing", "trendinganime"], airing_command))
    app.add_handler(CommandHandler(["animequote", "aq"], animequote_command))
