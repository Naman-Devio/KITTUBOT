# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Text-to-Speech (TTS) Voice Plugin
Converts text into high-quality spoken audio notes in multiple languages.
"""

import io
import urllib.parse
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from KITTUBOT import log

__mod_name__ = "Voice"
__help__ = """
<blockquote>🎙️ <b>ᴛᴇxᴛ-ᴛᴏ-sᴘᴇᴇᴄʜ (ᴛᴛs):</b>
• <code>/tts [text]</code> - ᴄᴏɴᴠᴇʀᴛ ᴛᴇxᴛ ᴛᴏ ᴠᴏɪᴄᴇ ɴᴏᴛᴇ
• <code>/tts [lang] [text]</code> - sᴘᴇᴀᴋ ɪɴ sᴘᴇᴄɪғɪᴄ ʟᴀɴɢᴜᴀɢᴇ
• <code>/tts</code> (ʀᴇᴘʟʏ) - sᴘᴇᴀᴋ ᴛʜᴇ ʀᴇᴘʟɪᴇᴅ ᴍᴇssᴀɢᴇ

<i>🌍 Languages: <code>en</code>, <code>hi</code>, <code>ja</code>, <code>es</code>, <code>fr</code>, <code>ru</code>, <code>de</code>, <code>ko</code></i></blockquote>
"""

SUPPORTED_LANGS = {"en", "hi", "ja", "es", "fr", "ru", "de", "ko", "it", "pt", "ar"}


async def tts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    reply = message.reply_to_message

    lang = "en"
    text_to_speak = ""

    if context.args:
        first_arg = context.args[0].lower()
        if first_arg in SUPPORTED_LANGS and len(context.args) > 1:
            lang = first_arg
            text_to_speak = " ".join(context.args[1:]).strip()
        elif first_arg in SUPPORTED_LANGS and reply and (reply.text or reply.caption):
            lang = first_arg
            text_to_speak = (reply.text or reply.caption).strip()
        else:
            text_to_speak = " ".join(context.args).strip()
    elif reply and (reply.text or reply.caption):
        text_to_speak = (reply.text or reply.caption).strip()

    if not text_to_speak:
        await message.reply_html(
            "⚠️ <b>Provide text or reply to a message!</b>\n"
            "E.g. <code>/tts Hello there!</code> or <code>/tts hi नमस्ते आप कैसे हैं?</code>"
        )
        return

    if len(text_to_speak) > 300:
        text_to_speak = text_to_speak[:300]

    status_msg = await message.reply_html("🎙️ <i>Synthesizing voice note...</i>")

    try:
        encoded_text = urllib.parse.quote(text_to_speak)
        url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={encoded_text}&tl={lang}&client=tw-ob"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            res = await client.get(url)
            if res.status_code != 200 or len(res.content) < 100:
                await status_msg.edit_text("❌ Failed to synthesize audio.")
                return

            audio_data = io.BytesIO(res.content)
            audio_data.name = f"voice_{lang}.mp3"
            audio_data.seek(0)

            await status_msg.delete()
            await message.reply_voice(
                voice=audio_data,
                caption=f"🗣️ <i>Language: <code>{lang}</code></i>",
                parse_mode="HTML",
            )
    except Exception as e:
        log.error(f"TTS error: {e}")
        try:
            await status_msg.edit_text(f"❌ Error synthesizing speech: {e}")
        except Exception:
            pass


def register_handlers(app: Application):
    app.add_handler(CommandHandler(["tts", "voice", "speak"], tts_command))
