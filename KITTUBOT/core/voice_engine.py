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
import base64
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
# Uses verified premade voices that work on BOTH Free and Paid ElevenLabs tiers
VOICE_POOLS: dict[str, list[str]] = {
    "hi": ["cgSgspJ2msm6clMCkdW9", "FGY2WhTYpPnrIDTdsKH5"],
    "en": ["cgSgspJ2msm6clMCkdW9", "EXAVITQu4vr4xnSDxMaL", "FGY2WhTYpPnrIDTdsKH5"],
    "ja": ["pFZP5JQG7iQjIQuC4Bku", "cgSgspJ2msm6clMCkdW9"],
    "default": ["cgSgspJ2msm6clMCkdW9", "FGY2WhTYpPnrIDTdsKH5", "EXAVITQu4vr4xnSDxMaL"],
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
    Detects if the user is asking Kittu for a voice note or to say something.

    Returns (is_voice_request, directive_context_or_None).
    - directive_context: A structured context string extracted from the request,
      which tells ask_kittu_voice WHAT to do (sing, say ily to X, etc.)
      so the LLM gets a clean, pre-parsed instruction instead of raw user text.
    """
    if not text:
        return False, None

    lower = text.lower().strip()

    # ── 1. Literal parrot quote: 'kittu ye bol: "hello world"'
    # Only match if it looks like a real quoted string, not an instruction
    quote_pat = re.compile(
        r"""(?i)(?:kittu|kitu|billu)?\s*(?:ye|yeh)\s*(?:bol|bolo|bol\s*de|bol\s*do|bata|batao)\s*[:"']\s*(.+?)["']?$""",
        re.DOTALL,
    )
    m = quote_pat.search(text)
    if m:
        extracted = m.group(1).strip()
        instruction_words = (
            "gana", "gaana", "order", "bhejo", "bhej", "sunao", "suna", "gao",
            "karo", "batao", "kuch", "shanti", "song", "sing", "say", "voice", "vn",
        )
        if extracted and not any(w in extracted.lower() for w in instruction_words):
            return True, f"[PARROT] {extracted}"

    # ── 2. Third-party message: '[name] ko [message] bol de'
    # "apne anshu ko pyar se ily bolde", "Rahul ko bol de main usse pyar karti hu"
    third_party_pat = re.compile(
        r"""(?i)(?:apne?\s+|mere?\s+)?(\w+)\s+ko\s+(.+?)\s+(?:bol\s*de|bol\s*do|bol\s*do|keh\s*de|keh\s*do|bolde|kardo|bolo)""",
        re.DOTALL,
    )
    m2 = third_party_pat.search(lower)
    if m2:
        target_name = m2.group(1).strip().title()
        message_intent = m2.group(2).strip()
        # Filter out non-person triggers
        non_person_words = ("voice", "gana", "song", "kuch", "mujhe", "meko", "yeh", "ye", "woh")
        if target_name.lower() not in non_person_words:
            return True, f"[TELL:{target_name}] {message_intent}"

    # ── 3. General Voice & Speech Triggers
    triggers = [
        # Voice note / message keywords
        "voice message", "voice msg", "voice note", "voice bhejo", "voice bhej", "voice send",
        "vn bhejo", "vn bhej", "vn send", "audio bhejo", "audio bhej",
        "voice me", "voice mein", "voice mai", "vn me", "vn mein",
        # Spoken request keywords
        "bol ke", "bol kar", "bolke", "bolkar", "bol de na", "bol do na", "bol do", "bol de",
        "bol na voice", "bolo na voice", "bol ke suna", "bol ke sunao", "bolke suna", "bolke sunao",
        # Awaz / Voice
        "awaz sunao", "awaaz sunao", "awaz suna", "awaaz suna",
        "awaz sunni", "awaaz sunni", "awaz sunna", "awaaz sunna",
        "apni awaz", "apni awaaz", "awaz sunau", "awaaz sunau",
        # Singing / Song
        "gana sunao", "gaana sunao", "gana gao", "gaana gao", "gana suna", "gaana suna",
        "gaana suna de", "gana suna do", "gana suna na", "gaana suna na",
        "sing a song", "sing for me", "sing song", "singing",
        # English voice
        "send voice", "send me voice", "send me a voice", "send voice note", "send voice message",
        "speak in voice", "talk in voice", "send audio",
        # Propose / ily
        "propose kar", "propose karo", "propose kardo", "propose kr",
        "i love you bol", "ily bol",
    ]

    for trig in triggers:
        if trig in lower:
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
        log.debug("[VoiceEngine] FFmpeg not installed - falling back to direct OGG stream (install ffmpeg for better compatibility)")
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
        log.debug("[VoiceEngine] FFmpeg not installed - skipping WAV->OGG conversion (Sarvam/Rumik return native OGG)")
    except Exception as e:
        log.error(f"[VoiceEngine] mp3→ogg error: {e}")
    return None


# ─────────────────── SPEECH-TO-TEXT ───────────────────

async def transcribe_voice(voice_bytes: bytes) -> TranscriptionResult | None:
    """
    Transcribes voice note bytes using Groq Whisper (primary) or Gemini (fallback).
    Supports direct OGG transmission so FFmpeg is not strictly required.
    """
    wav_data = await convert_oga_to_wav(voice_bytes)
    audio_data = wav_data if wav_data else voice_bytes
    audio_format = "wav" if wav_data else "ogg"

    # Primary: Groq Whisper
    result = await _transcribe_groq(audio_data, audio_format=audio_format)
    if result:
        return result

    # Fallback: Gemini multimodal
    result = await _transcribe_gemini(audio_data, audio_format=audio_format)
    if result:
        return result

    log.warning("[VoiceEngine] All STT backends failed")
    return None


async def _transcribe_groq(audio_data: bytes, audio_format: str = "wav") -> TranscriptionResult | None:
    """Transcribes audio using Groq's Whisper API."""
    if not config.GROQ_API_KEY:
        return None

    filename = f"voice.{audio_format}"
    mime = "audio/wav" if audio_format == "wav" else "audio/ogg"

    for model in ["whisper-large-v3-turbo", "whisper-large-v3"]:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                files = {"file": (filename, audio_data, mime)}
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


async def _transcribe_gemini(audio_data: bytes, audio_format: str = "wav") -> TranscriptionResult | None:
    """Transcribes audio using Gemini Flash multimodal API as fallback."""
    api_key = config.GEMINI_API_KEY
    if not api_key:
        return None

    import base64
    audio_b64 = base64.b64encode(audio_data).decode()
    mime = "audio/wav" if audio_format == "wav" else "audio/ogg" 

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            res = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={api_key}",
                json={
                    "contents": [{
                        "parts": [
                            {"text": "Transcribe this audio exactly as spoken. On a new line write LANGUAGE: followed by the ISO 639-1 language code (hi, en, ja, etc). Nothing else."},
                            {"inline_data": {"mime_type": mime, "data": audio_b64}},
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
    Uses Sarvam AI Bulbul (primary for Indian Hindi/Hinglish),
    then ElevenLabs, with Google TTS fallback.
    """
    clean_text = clean_text_for_speech(text)
    if not clean_text:
        return None, ""

    # 1. Primary: Sarvam AI Bulbul (Expressive, natural Indian Hindi/Hinglish)
    if config.SARVAM_API_KEY:
        ogg_data = await _tts_sarvam(
            clean_text,
            speaker=config.SARVAM_SPEAKER or "simran_enhi_companion",
            model=config.SARVAM_MODEL or "bulbul:v4-flash",
        )
        if ogg_data:
            return ogg_data, f"sarvam:{config.SARVAM_SPEAKER}"

    # 2. Secondary: Rumik AI Silk TTS (Direct Opus, expressive voice)
    if config.RUMIK_API_KEY:
        ogg_data = await _tts_rumik(clean_text, model=config.RUMIK_MODEL or "mulberry")
        if ogg_data:
            return ogg_data, f"rumik:{config.RUMIK_MODEL}"

    voice_id = force_voice_id or _pick_voice_id(language)

    # 3. Tertiary: ElevenLabs
    if config.ELEVENLABS_API_KEY and await is_quota_available(len(clean_text)):
        ogg_data = await _tts_elevenlabs(clean_text, voice_id)
        if ogg_data:
            await add_chars_used(len(clean_text))
            return ogg_data, voice_id

    # 4. Fallback: Google TTS
    ogg_data = await _tts_google(clean_text, language)
    if ogg_data:
        return ogg_data, voice_id

    return None, voice_id


async def _tts_sarvam(
    text: str,
    speaker: str = "simran_enhi_companion",
    model: str = "bulbul:v4-flash",
) -> bytes | None:
    """Generates natural Indian voice audio via Sarvam AI Bulbul TTS."""
    api_key = config.SARVAM_API_KEY
    if not api_key:
        return None

    text_to_speak = text[:500] if len(text) > 500 else text
    url = "https://api.sarvam.ai/text-to-speech"
    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json",
    }

    candidates = [
        (model, speaker),
        ("bulbul:v3", "simran"),
        ("bulbul:v3", "kavya"),
    ]

    for m, spk in candidates:
        payload = {
            "inputs": [text_to_speak],
            "target_language_code": "hi-IN",
            "speaker": spk,
            "model": m,
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    audios = data.get("audios", [])
                    if audios:
                        wav_bytes = base64.b64decode(audios[0])
                        ogg_bytes = await convert_mp3_to_ogg(wav_bytes)
                        if ogg_bytes:
                            log.info(f"[VoiceEngine] Sarvam Bulbul TTS OK ({len(text)} chars, model={m}, speaker={spk})")
                            return ogg_bytes
                        log.info(f"[VoiceEngine] Sarvam Bulbul TTS OK (raw WAV, {len(text)} chars)")
                        return wav_bytes
                else:
                    log.warning(f"[VoiceEngine] Sarvam TTS ({m}/{spk}) → {res.status_code}: {res.text[:150]}")
        except Exception as e:
            log.warning(f"[VoiceEngine] Sarvam TTS error ({m}/{spk}): {e}")

    return None


async def _tts_rumik(
    text: str,
    model: str = "mulberry",
) -> bytes | None:
    """Generates expressive voice audio via Rumik AI Silk TTS in native Opus format."""
    api_key = config.RUMIK_API_KEY
    if not api_key:
        return None

    url = "https://silk-api.rumik.ai/v1/tts"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    if model == "muga":
        lower = text.lower()
        if any(w in lower for w in ("i love you", "ily", "pyar", "jaan", "shona", "sweet", "suno na")):
            tone = "[happy]"
        elif any(w in lower for w in ("arre", "bhai", "haha", "suno suno", "party", "nacho", "jeet")):
            tone = "[excited]"
        elif any(w in lower for w in ("sad", "dukh", "dard", "sorry", "rona")):
            tone = "[sad]"
        elif any(w in lower for w in ("gussa", "pagal", "chup", "hatt")):
            tone = "[angry]"
        else:
            tone = "[happy]"

        payload = {
            "model": "muga",
            "text": f"{tone} {text[:500]}",
            "audio_format": "opus",
            "temperature": 0.7,
        }
    else:
        lower = text.lower()
        desc = "Young cheerful Indian girl speaking sweet casual Hindi"
        if any(w in lower for w in ("i love you", "ily", "pyar", "jaan")):
            desc = "Young affectionate Indian girl speaking soft sweet Hinglish"
        payload = {
            "model": "mulberry",
            "text": text[:500],
            "description": desc,
            "audio_format": "opus",
        }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code == 200 and len(res.content) > 500:
                log.info(f"[VoiceEngine] Rumik Silk TTS OK ({len(text)} chars, model={model})")
                return res.content
            else:
                log.warning(f"[VoiceEngine] Rumik TTS → {res.status_code}: {res.text[:150]}")
    except Exception as e:
        log.warning(f"[VoiceEngine] Rumik TTS error: {e}")

    return None


async def _tts_elevenlabs(text: str, voice_id: str) -> bytes | None:
    """Generates voice audio via ElevenLabs REST API in native Opus format."""
    fallback_voice = "cgSgspJ2msm6clMCkdW9"
    voices_to_try = [voice_id]
    if voice_id != fallback_voice:
        voices_to_try.append(fallback_voice)

    for vid in voices_to_try:
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{vid}?output_format=opus_48000_64",
                    headers={
                        "xi-api-key": config.ELEVENLABS_API_KEY,
                        "Content-Type": "application/json",
                        "Accept": "audio/ogg",
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
                    log.info(f"[VoiceEngine] ElevenLabs TTS OK ({len(text)} chars, voice={vid[:8]})")
                    return res.content
                elif res.status_code == 402:
                    log.warning(f"[VoiceEngine] ElevenLabs voice {vid} requires paid plan (402). Falling back to premade voice...")
                    continue
                else:
                    log.warning(f"[VoiceEngine] ElevenLabs TTS ({vid}) → {res.status_code}: {res.text[:150]}")
        except Exception as e:
            log.warning(f"[VoiceEngine] ElevenLabs TTS error ({vid}): {e}")
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
                log.info(f"[VoiceEngine] Google TTS fallback OK (direct audio, {safe_lang})")
                return res.content
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
