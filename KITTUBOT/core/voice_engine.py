# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
Voice Engine — Complete STT + TTS + Audio Conversion pipeline.
Handles incoming voice notes (transcription via Groq Whisper),
generates voice replies (ElevenLabs + Google TTS fallback),
and manages audio format conversions via FFmpeg.
"""

import io
import re
import random
import asyncio
import subprocess
import httpx
from dataclasses import dataclass
from KITTUBOT.config import config
from KITTUBOT.database.voice_cache import (
    get_cached_voice,
    cache_voice,
    is_quota_available,
    add_chars_used,
)
from KITTUBOT import log


@dataclass
class TranscriptionResult:
    """Result from speech-to-text processing."""
    text: str
    language: str  # ISO 639-1 code: "hi", "en", "ja", etc.
    duration_seconds: float


# ─── Voice ID Pools (language → list of ElevenLabs voice IDs) ───
VOICE_POOLS: dict[str, list[str]] = {
    "hi": ["CNKl99QEbWm8RQ4D8GfC", "MhnQB6oLKSlS0AIJzxtO"],
    "en": ["xYrwTY3IRh6VBodoZUNN", "JTlYtJrcTzPC71hMLOxo"],
    "ja": ["RxivyypsDodFBfmDDOZF"],
    "default": ["nUX4UWK0Tf1qh5zvFZWR", "ljCTqT1biPnI7ZjS5gyi"],
}

# Pre-written bored/spontaneous voice lines
BORED_LINES = [
    "yawr me bol rhi koii hai hi nhi mera timepass karao na",
    "hello koi zinda h yaha pe ya sb so gye",
    "kya boring log h yaha koi memes bhi nhi daal rha",
    "achaa toh koi baat hi nhi krega aaj sab busy h kya",
    "hellooo earth to humans koi respond karo yaar",
    "me akeli bore ho rhi hu idhar koi toh aao baat karo",
]

SAVAGE_REJECTIONS = [
    "thobda dekha h apna? hatt bhai",
    "bhai tu kyu propose karva rha mujhse apne aap ko lol",
    "shakal dekhi h apni kya bolti h mirror se puch",
    "itni himmat kaha se laate ho tum log haha",
    "mere se bolva rha h ye sab sharam nhi aati kya",
    "nevla dikhta h tu mujhe ye boldun voice me lol",
]


def _pick_voice_id(language: str) -> str:
    """Selects a random voice ID from the appropriate language pool."""
    pool = VOICE_POOLS.get(language, VOICE_POOLS["default"])
    return random.choice(pool)


def clean_text_for_speech(text: str) -> str:
    """
    Cleans text before feeding to TTS:
    - Removes markdown formatting (*bold*, _italic_, `code`, etc.)
    - Removes roleplay actions (*laughs*, (giggles))
    - Removes URLs
    - Removes emojis and kaomojis (^.^, ^_^, (◕‿◕), etc.)
    - Retains natural spoken Hindi/English characters and basic sentence punctuation
    """
    if not text:
        return ""
    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)
    # Remove roleplay actions like *laughs*, *sighs*, (giggles)
    text = re.sub(r"\*[^*]+\*", "", text)
    text = re.sub(r"\([a-zA-Z\s]+\)", "", text)
    # Remove markdown formatting characters
    text = re.sub(r"[*_~`#|]", "", text)
    # Remove [SEND_STICKER] or any bracketed tags
    text = re.sub(r"\[.*?\]", "", text)
    # Strip emojis, kaomojis, and symbols: retain alphanumeric (including Devanagari/Unicode),
    # basic speech punctuation, and whitespace
    text = re.sub(r"[^\w\s\?,.!'\-]", "", text)
    # Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+([?.!,])", r"\1", text)
    return text.strip()


def _detect_voice_request(text: str) -> tuple[bool, str | None]:
    """
    Detects if the user is asking Kittu to speak/say something specific.
    Returns (is_voice_request, requested_text_or_None).
    """
    patterns = [
        # 1. 'kittu [meko/mujhe/merko]? [yeh/ye]? bolkr/bol ke/bol kar bata/batao/suna/sunao/de/do <something>'
        re.compile(
            r"(?i)(?:kittu|kitu|billu)\s+(?:meko|mujhe|merko)?\s*(?:ye|yeh)?\s*(?:bol\s*(?:kr|ke|kar)?\s*(?:bata|batao|suna|sunao|de|do))\s+(.+)",
            re.DOTALL,
        ),
        # 2. 'voice me bol/bata/suna/bhej <something>' or 'vn me ...'
        re.compile(
            r"(?i)(?:voice\s*(?:me|mein|mai)?|vn\s*(?:me|mein)?)\s+(?:bol|bata|suna|bhej)\s+(.+)",
            re.DOTALL,
        ),
        # 3. 'kittu ye/yeh bol de/do/na <something>' (strictly requiring ye/yeh so 'kittu bol na' doesn't match!)
        re.compile(
            r"(?i)(?:kittu|kitu)\s+(?:ye|yeh)\s+(?:bol\s*(?:de|do|na)|bata\s*(?:de|do)?|suna\s*(?:de|do)?)\s+(.+)",
            re.DOTALL,
        ),
        # 4. Propose / I love you requests: 'kittu [meko/mujhe]? propose kar/karo/kardo'
        re.compile(
            r"(?i)(?:kittu|kitu)?\s*(?:meko|mujhe|merko)?\s*(?:propose\s+(?:kar\s*do|kardo|kr\s*do|kar|karo)|say\s+(?:i\s+love\s+you|ily)|i\s+love\s+you\s+(?:bol|bolo|bol\s*de|bol\s*do))\s*(?:voice\s*(?:me|mein)?)?",
            re.DOTALL,
        ),
    ]

    for pat in patterns:
        m = pat.search(text)
        if m:
            requested = m.group(1).strip() if m.lastindex and m.lastindex >= 1 else None
            return True, requested

    # Keyword check for general requests to speak in voice
    lower = text.lower()
    voice_keywords = ["voice me bol", "vn bhej", "voice note bhej", "awaaz sunu", "bol ke suna", "voice me bata"]
    for kw in voice_keywords:
        if kw in lower:
            return True, None

    return False, None


detect_voice_request = _detect_voice_request


async def convert_oga_to_wav(oga_bytes: bytes) -> bytes | None:
    """Converts Telegram .oga voice note to 16kHz mono WAV for Whisper."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-i", "pipe:0",
            "-ar", "16000", "-ac", "1", "-f", "wav",
            "-y", "pipe:1",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(input=oga_bytes), timeout=15.0)
        if proc.returncode == 0 and stdout:
            return stdout
        log.warning(f"[VoiceEngine] FFmpeg oga→wav failed: {stderr.decode()[:200]}")
    except asyncio.TimeoutError:
        log.warning("[VoiceEngine] FFmpeg oga→wav timed out")
    except FileNotFoundError:
        log.error("[VoiceEngine] FFmpeg not found! Install ffmpeg.")
    except Exception as e:
        log.error(f"[VoiceEngine] oga→wav error: {e}")
    return None


async def convert_mp3_to_ogg(mp3_bytes: bytes) -> bytes | None:
    """Converts MP3 audio to OGG Opus format for Telegram voice notes."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-i", "pipe:0",
            "-c:a", "libopus", "-b:a", "48k", "-ac", "1",
            "-f", "ogg", "-y", "pipe:1",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(input=mp3_bytes), timeout=15.0)
        if proc.returncode == 0 and stdout:
            return stdout
        log.warning(f"[VoiceEngine] FFmpeg mp3→ogg failed: {stderr.decode()[:200]}")
    except asyncio.TimeoutError:
        log.warning("[VoiceEngine] FFmpeg mp3→ogg timed out")
    except FileNotFoundError:
        log.error("[VoiceEngine] FFmpeg not found! Install ffmpeg.")
    except Exception as e:
        log.error(f"[VoiceEngine] mp3→ogg error: {e}")
    return None


# ─────────────────── SPEECH-TO-TEXT ───────────────────

async def transcribe_voice(voice_bytes: bytes) -> TranscriptionResult | None:
    """
    Transcribes voice note bytes using Groq Whisper (primary) or Gemini (fallback).
    Returns TranscriptionResult with text, detected language, and duration.
    """
    wav_data = await convert_oga_to_wav(voice_bytes)
    if not wav_data:
        log.warning("[VoiceEngine] Could not convert voice note to WAV")
        return None

    # Primary: Groq Whisper
    result = await _transcribe_groq(wav_data)
    if result:
        return result

    # Fallback: Gemini multimodal
    result = await _transcribe_gemini(wav_data)
    if result:
        return result

    log.warning("[VoiceEngine] All STT backends failed")
    return None


async def _transcribe_groq(wav_data: bytes) -> TranscriptionResult | None:
    """Transcribes audio using Groq's Whisper API."""
    if not config.GROQ_API_KEY:
        return None

    for model in ["whisper-large-v3-turbo", "whisper-large-v3"]:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                files = {"file": ("voice.wav", wav_data, "audio/wav")}
                data = {
                    "model": model,
                    "response_format": "verbose_json",
                }
                res = await client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
                    files=files,
                    data=data,
                )
                if res.status_code == 200:
                    j = res.json()
                    text = j.get("text", "").strip()
                    lang = j.get("language", "en")
                    duration = j.get("duration", 0.0)

                    # Map common language names to ISO codes
                    lang_map = {
                        "hindi": "hi", "english": "en", "japanese": "ja",
                        "spanish": "es", "french": "fr", "korean": "ko",
                        "german": "de", "russian": "ru", "arabic": "ar",
                    }
                    lang = lang_map.get(lang.lower(), lang.lower()[:2]) if lang else "en"

                    if text:
                        log.info(f"[VoiceEngine] Groq STT ({model}): '{text[:60]}' lang={lang}")
                        return TranscriptionResult(text=text, language=lang, duration_seconds=duration)
                else:
                    log.warning(f"[VoiceEngine] Groq STT {model} → {res.status_code}: {res.text[:100]}")
        except Exception as e:
            log.warning(f"[VoiceEngine] Groq STT error ({model}): {e}")

    return None


async def _transcribe_gemini(wav_data: bytes) -> TranscriptionResult | None:
    """Transcribes audio using Gemini Flash multimodal API as fallback."""
    api_key = config.GEMINI_API_KEY
    if not api_key:
        return None

    import base64
    audio_b64 = base64.b64encode(wav_data).decode()

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            res = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
                json={
                    "contents": [{
                        "parts": [
                            {"text": "Transcribe this audio exactly as spoken. On a new line write LANGUAGE: followed by the ISO 639-1 language code (hi, en, ja, etc). Nothing else."},
                            {"inline_data": {"mime_type": "audio/wav", "data": audio_b64}},
                        ]
                    }]
                },
            )
            if res.status_code == 200:
                j = res.json()
                raw = j.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                lines = raw.strip().split("\n")
                lang = "en"
                text_lines = []
                for line in lines:
                    line_s = line.strip()
                    if line_s.upper().startswith("LANGUAGE:"):
                        lang = line_s.split(":", 1)[1].strip().lower()[:2]
                    elif line_s:
                        text_lines.append(line_s)
                text = " ".join(text_lines).strip()
                if text:
                    log.info(f"[VoiceEngine] Gemini STT: '{text[:60]}' lang={lang}")
                    return TranscriptionResult(text=text, language=lang, duration_seconds=0.0)
            else:
                log.warning(f"[VoiceEngine] Gemini STT → {res.status_code}: {res.text[:100]}")
    except Exception as e:
        log.warning(f"[VoiceEngine] Gemini STT error: {e}")

    return None


# ─────────────────── TEXT-TO-SPEECH ───────────────────

async def generate_voice_note(
    text: str,
    language: str = "hi",
    force_voice_id: str | None = None,
) -> tuple[bytes | None, str]:
    """
    Generates a voice note from text. Returns (ogg_bytes, voice_id_used).
    Cleans text for speech (removes emojis, kaomojis, actions) before TTS.
    Uses ElevenLabs (primary) with Google TTS fallback.
    """
    clean_text = clean_text_for_speech(text)
    if not clean_text:
        return None, ""

    voice_id = force_voice_id or _pick_voice_id(language)

    # Primary: ElevenLabs
    if config.ELEVENLABS_API_KEY and await is_quota_available(len(clean_text)):
        ogg_data = await _tts_elevenlabs(clean_text, voice_id)
        if ogg_data:
            await add_chars_used(len(clean_text))
            return ogg_data, voice_id

    # Fallback: Google TTS
    ogg_data = await _tts_google(clean_text, language)
    if ogg_data:
        return ogg_data, voice_id

    return None, voice_id


async def _tts_elevenlabs(text: str, voice_id: str) -> bytes | None:
    """Generates voice audio via ElevenLabs streaming REST API."""
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            res = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream",
                headers={
                    "xi-api-key": config.ELEVENLABS_API_KEY,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json={
                    "text": text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {
                        "stability": 0.40,
                        "similarity_boost": 0.80,
                        "style": 0.35,
                    },
                },
            )
            if res.status_code == 200 and len(res.content) > 500:
                mp3_bytes = res.content
                ogg_bytes = await convert_mp3_to_ogg(mp3_bytes)
                if ogg_bytes:
                    log.info(f"[VoiceEngine] ElevenLabs TTS OK ({len(text)} chars, voice={voice_id[:8]})")
                    return ogg_bytes
            else:
                log.warning(f"[VoiceEngine] ElevenLabs TTS → {res.status_code}: {res.text[:150]}")
    except Exception as e:
        log.warning(f"[VoiceEngine] ElevenLabs TTS error: {e}")
    return None


async def _tts_google(text: str, language: str = "hi") -> bytes | None:
    """Generates voice audio via Google Translate TTS as unlimited fallback."""
    import urllib.parse
    valid_langs = {"hi", "en", "ja", "es", "fr", "de", "ru", "ko", "ar", "pt", "it", "tr"}
    safe_lang = language.lower()[:2] if language and language.lower()[:2] in valid_langs else "hi"

    # Truncate for Google TTS limit
    if len(text) > 200:
        text = text[:200]
    encoded = urllib.parse.quote(text)
    url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={encoded}&tl={safe_lang}&client=tw-ob"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
            if res.status_code == 200 and len(res.content) > 100:
                ogg_bytes = await convert_mp3_to_ogg(res.content)
                if ogg_bytes:
                    log.info(f"[VoiceEngine] Google TTS fallback OK ({safe_lang})")
                    return ogg_bytes
            else:
                log.warning(f"[VoiceEngine] Google TTS → {res.status_code}")
    except Exception as e:
        log.warning(f"[VoiceEngine] Google TTS error: {e}")
    return None


def get_bored_line() -> str:
    """Returns a random pre-written bored/spontaneous voice line."""
    return random.choice(BORED_LINES)


def get_savage_rejection() -> str:
    """Returns a random savage rejection line for non-owner voice requests."""
    return random.choice(SAVAGE_REJECTIONS)
