# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Social Media & Video Downloader Engine
High-speed asynchronous media extraction for Instagram Reels, TikTok, YouTube, Twitter/X, and Pinterest.
"""

import os
import re
import glob
import tempfile
import asyncio
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import yt_dlp
from KITTUBOT.config import config
from KITTUBOT import log

__mod_name__ = "Downloader"
__help__ = """
<blockquote>📥 <b>sᴏᴄɪᴀʟ ᴍᴇᴅɪᴀ & ʏᴏᴜᴛᴜʙᴇ ᴅᴏᴡɴʟᴏᴀᴅᴇʀ:</b>
• <code>/dl [link]</code> - ᴅᴏᴡɴʟᴏᴀᴅ ɪɢ ʀᴇᴇʟ, ᴛɪᴋᴛᴏᴋ, ʏᴛ, x
• <code>/song [title/link]</code> - ʜɪɢʜ-sᴘᴇᴇᴅ ᴍᴜsɪᴄ & ᴀᴜᴅɪᴏ (ʏᴜᴋɪ ᴀᴘɪ)
• <code>/video [title/link]</code> - sᴇᴀʀᴄʜ & ᴅᴏᴡɴʟᴏᴀᴅ ᴠɪᴅᴇᴏ</blockquote>
"""

YT_ID_REGEX = re.compile(r"(?:v=|\/|youtu\.be\/|shorts\/)([0-9A-Za-z_-]{11})")


def _get_youtube_info(query_or_url: str) -> dict | None:
    """Extracts video metadata and 11-char ID without full download."""
    is_url = query_or_url.startswith("http://") or query_or_url.startswith("https://")
    match = YT_ID_REGEX.search(query_or_url)
    if match:
        video_id = match.group(1)
        url = f"https://www.youtube.com/watch?v={video_id}"
    elif is_url:
        url = query_or_url
    else:
        url = f"ytsearch1:{query_or_url}"

    ydl_opts = {
        "extract_flat": True,
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return None
            if "entries" in info and info["entries"]:
                entry = info["entries"][0]
            else:
                entry = info
            return {
                "id": entry.get("id"),
                "title": entry.get("title", "Audio Track"),
                "uploader": entry.get("uploader", "Artist"),
                "duration": entry.get("duration", 0),
            }
    except Exception as e:
        log.warning(f"Error fetching YouTube info: {e}")
        return None


def _download_yuki_stream(video_id: str, out_file: str) -> bool:
    """Streams audio from Yuki API gateways directly into out_file."""
    key = config.YUKI_API_KEY
    gateways = [
        f"https://play.yukiapi.site/stream/{video_id}?key={key}",
        f"https://music.yukiapi.site/stream/{video_id}?key={key}",
    ]

    for gw_url in gateways:
        try:
            resp = requests.get(gw_url, stream=True, timeout=20)
            if resp.status_code == 200:
                with open(out_file, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                if os.path.exists(out_file) and os.path.getsize(out_file) > 10000:
                    log.info(f"Successfully streamed audio from Yuki API for {video_id}")
                    return True
        except Exception as e:
            log.warning(f"Yuki API gateway error on {gw_url}: {e}")
    return False


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
        await update.message.reply_html("🎵 <b>Usage:</b> <code>/song <title or link></code> (e.g. <code>/song Believer Imagine Dragons</code>)")
        return

    query = " ".join(context.args).strip()
    status_msg = await update.message.reply_html(f"🔎 <i>Searching track via Yuki Gateway:</i> <b>{query}</b>...")

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # 1. Fetch metadata & Video ID
            yt_info = await asyncio.to_thread(_get_youtube_info, query)
            title = "Audio Track"
            performer = "Artist"
            duration = 0
            video_id = None

            if yt_info:
                video_id = yt_info.get("id")
                title = yt_info.get("title", "Audio Track")
                performer = yt_info.get("uploader", "Artist")
                duration = yt_info.get("duration", 0)

            audio_file_path = os.path.join(tmpdir, "track.mp3")
            success = False

            # 2. Fast Yuki Stream Download
            if video_id:
                await status_msg.edit_text("⚡ <i>Streaming audio from Yuki Gateway...</i>", parse_mode="HTML")
                success = await asyncio.to_thread(_download_yuki_stream, video_id, audio_file_path)

            # 3. Fallback to yt-dlp if Yuki API failed
            if not success or not os.path.exists(audio_file_path):
                await status_msg.edit_text("⏳ <i>Yuki fallback: extracting directly via local engine...</i>", parse_mode="HTML")
                search_query = f"https://www.youtube.com/watch?v={video_id}" if video_id else f"ytsearch1:{query}"
                info = await asyncio.to_thread(_extract_media, search_query, tmpdir, audio_only=True)
                if info:
                    files = glob.glob(os.path.join(tmpdir, "*"))
                    if files:
                        audio_file_path = files[0]
                        success = True
                        if not video_id:
                            entry = info["entries"][0] if "entries" in info and info["entries"] else info
                            title = entry.get("title", title)
                            performer = entry.get("uploader", performer)
                            duration = entry.get("duration", duration)

            if not success or not os.path.exists(audio_file_path):
                await status_msg.edit_text("❌ <b>Audio extraction failed!</b> Please try a different title or link.", parse_mode="HTML")
                return

            await status_msg.edit_text("📤 <i>Uploading audio to Telegram...</i>", parse_mode="HTML")

            caption = (
                f"🎵 <b>{title}</b>\n\n"
                f"<blockquote>⚡ <b>Provider :</b> <code>Yuki Stream API</code>\n"
                f"👤 <b>Requested by :</b> {user.mention_html()}</blockquote>"
            )

            with open(audio_file_path, "rb") as audio_file:
                await context.bot.send_audio(
                    chat_id=chat.id,
                    audio=audio_file,
                    title=title,
                    performer=performer,
                    duration=duration,
                    caption=caption,
                    parse_mode="HTML",
                )

            await status_msg.delete()
        except Exception as e:
            log.error(f"Error handling /song: {e}")
            await status_msg.edit_text(f"❌ Error uploading audio: <code>{e}</code>", parse_mode="HTML")


def register_handlers(app: Application):
    app.add_handler(CommandHandler(["dl", "download", "reel", "tt"], download_command))
    app.add_handler(CommandHandler(["song", "music"], song_command))
