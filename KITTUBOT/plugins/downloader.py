# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Social Media & Video Downloader Engine
High-speed asynchronous media extraction for Instagram Reels, TikTok, YouTube, Twitter/X, and Pinterest.
"""

import os
import glob
import tempfile
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import yt_dlp
from KITTUBOT import log

__mod_name__ = "Downloader"
__help__ = """
<blockquote>📥 <b>sᴏᴄɪᴀʟ ᴍᴇᴅɪᴀ ᴅᴏᴡɴʟᴏᴀᴅᴇʀ:</b>
• <code>/dl [link]</code> - ᴅᴏᴡɴʟᴏᴀᴅ ɪɢ ʀᴇᴇʟ, ᴛɪᴋᴛᴏᴋ, ʏᴛ, x
• <code>/song [title]</code> - ᴅᴏᴡɴʟᴏᴀᴅ ᴍᴜsɪᴄ & ᴀᴜᴅɪᴏ
• <code>/video [title]</code> - sᴇᴀʀᴄʜ & ᴅᴏᴡɴʟᴏᴀᴅ ʏᴛ ᴠɪᴅᴇᴏ</blockquote>
"""


def _extract_media(url: str, download_dir: str, audio_only: bool = False) -> dict | None:
    """Synchronous worker executed in a background thread."""
    out_tmpl = os.path.join(download_dir, "%(title).50s.%(ext)s")
    ydl_opts = {
        "outtmpl": out_tmpl,
        "format": "bestaudio/best" if audio_only else "best[filesize<50M]/bestvideo[filesize<40M]+bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "max_filesize": 50 * 1024 * 1024,  # 50MB limit
        "noplaylist": True,
    }
    if audio_only:
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return info
    except Exception as e:
        log.warning(f"yt_dlp extraction error for {url}: {e}")
        return None


async def download_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not context.args:
        await update.message.reply_html(
            "📥 <b>Usage:</b> <code>/dl <url></code>\n\n"
            "Supported platforms:\n"
            "• <b>Instagram Reels & Posts</b>\n"
            "• <b>TikTok (No Watermark)</b>\n"
            "• <b>YouTube Shorts & Videos</b>\n"
            "• <b>Twitter / X Videos</b>\n"
            "• <b>Pinterest Videos</b>"
        )
        return

    url = context.args[0].strip()
    status_msg = await update.message.reply_html("⏳ <i>Fetching media details...</i>")

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            info = await asyncio.to_thread(_extract_media, url, tmpdir, audio_only=False)
            if not info:
                await status_msg.edit_text("❌ <b>Could not download video!</b> Link may be private, unsupported, or exceeds 50MB.", parse_mode="HTML")
                return

            # Find downloaded file
            files = glob.glob(os.path.join(tmpdir, "*"))
            if not files:
                await status_msg.edit_text("❌ Downloaded file not found.", parse_mode="HTML")
                return

            file_path = files[0]
            title = info.get("title", "Video")
            duration = info.get("duration", 0)

            await status_msg.edit_text("📤 <i>Uploading video to Telegram...</i>", parse_mode="HTML")

            caption = (
                f"🎬 <b>{title[:100]}</b>\n\n"
                f"<blockquote>📥 <b>Downloader :</b> <code>Kittu Engine</code>\n"
                f"👤 <b>Requested by :</b> {user.mention_html()}</blockquote>"
            )

            with open(file_path, "rb") as video_file:
                await context.bot.send_video(
                    chat_id=chat.id,
                    video=video_file,
                    caption=caption,
                    duration=duration,
                    parse_mode="HTML",
                )

            await status_msg.delete()
        except Exception as e:
            log.error(f"Error handling download: {e}")
            await status_msg.edit_text(f"❌ Error uploading video: <code>{e}</code>", parse_mode="HTML")


async def song_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not context.args:
        await update.message.reply_html("🎵 <b>Usage:</b> <code>/song <song name or link></code> (e.g. <code>/song Believer Imagine Dragons</code>)")
        return

    query = " ".join(context.args).strip()
    if not (query.startswith("http://") or query.startswith("https://")):
        query = f"ytsearch1:{query}"

    status_msg = await update.message.reply_html(f"🔎 <i>Searching and extracting audio for:</i> <b>{query.replace('ytsearch1:', '')}</b>...")

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            info = await asyncio.to_thread(_extract_media, query, tmpdir, audio_only=True)
            if not info:
                await status_msg.edit_text("❌ <b>Audio extraction failed!</b> Try another title.", parse_mode="HTML")
                return

            files = glob.glob(os.path.join(tmpdir, "*"))
            if not files:
                await status_msg.edit_text("❌ Extracted audio file not found.", parse_mode="HTML")
                return

            file_path = files[0]
            # If search, info may contain 'entries'
            entry = info["entries"][0] if "entries" in info and info["entries"] else info
            title = entry.get("title", "Audio Track")
            performer = entry.get("uploader", "Unknown Artist")
            duration = entry.get("duration", 0)

            await status_msg.edit_text("📤 <i>Uploading audio track...</i>", parse_mode="HTML")

            with open(file_path, "rb") as audio_file:
                await context.bot.send_audio(
                    chat_id=chat.id,
                    audio=audio_file,
                    title=title,
                    performer=performer,
                    duration=duration,
                    caption=f"🎵 <b>{title}</b>\n<blockquote>👤 Requested by {user.mention_html()}</blockquote>",
                    parse_mode="HTML",
                )

            await status_msg.delete()
        except Exception as e:
            log.error(f"Error handling /song: {e}")
            await status_msg.edit_text(f"❌ Error uploading audio: <code>{e}</code>", parse_mode="HTML")


def register_handlers(app: Application):
    app.add_handler(CommandHandler(["dl", "download", "reel", "tt"], download_command))
    app.add_handler(CommandHandler(["song", "music"], song_command))
