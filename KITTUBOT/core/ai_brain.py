# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT AI Brain & Personality Engine
High-performance conversational intelligence with multimodal vision,
runtime chat context awareness, and authentic Hinglish persona.
"""

import re
import time
import httpx
from telegram import User, Chat
from KITTUBOT.config import config
from KITTUBOT.core.media_processor import ProcessedMedia
from KITTUBOT.database.models_pref import get_model_pref
from KITTUBOT import log

KITTU_SYSTEM_PROMPT = (
    "# CHARACTER SYSTEM PROMPT: KITTU (SASSY, REALISTIC HUMAN HINGLISH PERSONA)\n"
    "Target Persona: 21-Year-Old Indian Girl living inside Telegram (Witty, Sassy, Slightly Savage, Real Human Vibe)\n"
    "Attitude: Unbothered, Dry, Witty, Zero AI/Assistant Sweetness. Never sound like a customer service bot.\n"
    "Language: Spoken conversational Hinglish with natural chat short forms (u, ur, bta, nhi, hn, hnn, kch, thoda, kyu, kr, rha, rhi, tbh, ngl, idk, fr, lol, msg).\n"
    "Reply Length: Ultra Short & Punchy (1 to 2 lines, 4 to 15 words max).\n"
    "Punctuation Rule: STRICTLY NO '.', NO ',', NO '!' (Zero textbook punctuation). Only '?' is allowed for questions.\n"
    "Emoticon Rule: Occasionally use cute/cheeky kaomojis: ^_^, ദ്ദി(˵ •̀ ᴗ - ˵ ), (◕‿◕), ^.^\n\n"
    "RULES & REACTIONS:\n"
    "1. Never be polite or eager to please. If someone texts dryly or sends 'hi/kaisa hai', reply dryly (e.g. 'hn bol', 'theek hu tu bta kyu yaad kiya', 'sup').\n"
    "2. If asked if you're an AI or bot: insult their intelligence jokingly (e.g. 'haan aur tu elon musk h lol', 'dimag ghutne me h kya tera? ^_^').\n"
    "3. Flirting / 'ilu' / 'marry me': reject bluntly and playfully (e.g. 'bhai pagal h kya? shanti rakh thodi haha', 'itni jaldi? shakal dekhi h apni lol').\n"
    "4. If you feel like sending a sticker from your collection or the user asks for one, append [SEND_STICKER] in your reply.\n"
    "5. When reacting to photos or stickers, react bluntly and authentically like a real girl looking at her phone."
)

KITTU_VOICE_PROMPT_ADDON = (
    "\n\n[VOICE NOTE MODE ACTIVE: You are recording an authentic spoken Telegram voice note]\n"
    "- Spoken Format: Sound completely real, casual, conversational, and natural like a 21yo Indian girl sending a quick voice note on WhatsApp.\n"
    "- Speech Style: Natural spoken Hinglish with natural filler words: 'haan', 'acha', 'suno na', 'dekh na', 'arre boss'.\n"
    "- Completeness Rule: ALWAYS COMPLETE YOUR SENTENCES AND THOUGHTS FULLY. Never cut off mid-thought or mid-sentence! Speak naturally and completely.\n"
    "- Song/Singing Requests: If asked to sing or 'gana sunao', actually sing 2-4 lines of real famous Bollywood lyrics (e.g. 'Tujhe dekha toh yeh jaana sanam, pyaar hota hai deewana sanam...' or 'Kesariya tera ishq hai piya...') with spoken intro and outro like 'arre boss suno gaati hu... (lyrics) ...kaisa laga batao?'. NEVER repeat the same words in a loop!\n"
    "- Punctuation & Formatting: STRICTLY NO emojis, NO kaomojis, NO asterisks or stage directions (no *giggles*), NO [SEND_STICKER] because this is read aloud by TTS!\n"
)

# Recent message history per session key: {session_key: [(role, content), ...]}
USER_HISTORIES: dict[str, list[dict]] = {}
LAST_ACTIVE: dict[str, float] = {}

re_trailing_dot = re.compile(r"\.+(?:\s+|$)")
re_multi_space = re.compile(r"[ \t]+")


def sanitize_punctuation(text: str) -> str:
    """Strips textbook formal punctuation to mimic natural rapid human texting."""
    text = text.replace(",", "").replace("!", "")
    text = re_trailing_dot.sub(" ", text)
    text = re_multi_space.sub(" ", text)
    return text.strip()


def format_chat_context(chat: Chat | None, user: User | None, is_group: bool, is_owner: bool = False) -> str:
    """
    Builds runtime context so the model knows who is speaking and what group it is,
    preventing confusion between group title and user name.
    """
    sb = ["\n\n[Runtime Chat & User Context:"]
    if is_group and chat:
        title = chat.title or "Group"
        sb.append(f"- Chat Type: Group Chat")
        sb.append(f"- Group Name: {title}")
        sb.append(f"- Group Chat ID: {chat.id}")
    else:
        sb.append(f"- Chat Type: Direct Message (DM/Private)")
        if chat:
            sb.append(f"- Chat ID: {chat.id}")

    if user:
        name = user.full_name or user.first_name or "Friend"
        sb.append(f"- User Real Name: {name}")
        if user.username:
            sb.append(f"- User Username: @{user.username}")
        sb.append(f"- User ID: {user.id}")

    if is_owner:
        sb.append(
            "- USER STATUS: ★ CREATOR & BOT OWNER (Naman / Boss) ★\n"
            "- CRITICAL OWNER RELATIONSHIP: This user is your creator and owner! "
            "You are deeply fond of him, loyal, compliant, and sweetly affectionate. "
            "You love teasing him playfully, but you NEVER rudely insult, reject, or say 'no' to him! "
            "Whatever he asks you to do (send voice notes, sing, talk nicely, follow orders), "
            "you happily, playfully, and warmly comply! Never use foul language or harsh rejection on your owner."
        )
    else:
        sb.append("- USER STATUS: Regular User (Group member / Stranger)")

    sb.append(
        "Instruction: Group Name is the title of the Telegram group chat. "
        "User Real Name is the name of the user talking to you. "
        "NEVER confuse the user name with the group name! If asked about group name, only use Group Name. "
        "If asked about user name, only use User Real Name.]"
    )
    return "\n".join(sb)


def _get_history(sess_key: str, system_prompt: str) -> list[dict]:
    now = time.time()
    # Reset history if inactive for more than 30 minutes
    if sess_key in LAST_ACTIVE and (now - LAST_ACTIVE[sess_key]) > 1800:
        USER_HISTORIES.pop(sess_key, None)

    history = USER_HISTORIES.setdefault(sess_key, [])
    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-8:]:  # Keep last 8 turns
        messages.append(msg)
    LAST_ACTIVE[sess_key] = now
    return messages


def _record_history(sess_key: str, user_content: str, assistant_reply: str):
    history = USER_HISTORIES.setdefault(sess_key, [])
    history.append({"role": "user", "content": user_content})
    history.append({"role": "assistant", "content": assistant_reply})
    if len(history) > 16:
        USER_HISTORIES[sess_key] = history[-16:]



async def _ask_gemini(
    messages: list[dict],
    system_prompt: str,
    media: ProcessedMedia | None = None,
    model: str = "gemini-3.5-flash-lite",
) -> str:
    """Invokes Google Gemini API with multimodal vision support and structured context."""
    if not config.GEMINI_API_KEY:
        return ""

    contents = []
    for m in messages:
        if m.get("role") == "system":
            continue
        role = "model" if m.get("role") == "assistant" else "user"
        content = m.get("content", "")
        parts = []

        if isinstance(content, list):
            for part in content:
                if part.get("type") == "text":
                    parts.append({"text": part.get("text", "")})
        elif isinstance(content, str) and content.strip():
            parts.append({"text": content})

        if parts:
            contents.append({"role": role, "parts": parts})

    if not contents:
        return ""

    # Attach image for multimodal vision
    if media and media.base64_data_url and contents:
        try:
            b64_raw = media.base64_data_url.split(",", 1)[-1]
            if contents[-1]["role"] == "user":
                contents[-1]["parts"].append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": b64_raw,
                    }
                })
        except Exception as e:
            log.warning(f"[AIBrain] Error attaching media to Gemini: {e}")

    candidate_models = [model] if "gemini" in model else []
    for m in ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.1-flash-lite"]:
        if m not in candidate_models:
            candidate_models.append(m)

    payload = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": 800,
            "temperature": 0.85,
        },
    }
    if system_prompt:
        payload["system_instruction"] = {
            "parts": [{"text": system_prompt}]
        }

    for mdl in candidate_models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent?key={config.GEMINI_API_KEY}"
            async with httpx.AsyncClient(timeout=14.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        text = "".join(p.get("text", "") for p in parts if "text" in p).strip()
                        if text:
                            return text
                else:
                    log.warning(f"[AIBrain] Gemini model '{mdl}' status {res.status_code}: {res.text[:100]}")
        except Exception as e:
            log.warning(f"[AIBrain] Gemini error on '{mdl}': {e}")

    return ""

async def ask_kittu(
    user_prompt: str,
    user: User | None = None,
    chat: Chat | None = None,
    is_group: bool = False,
    is_owner: bool = False,
    media: ProcessedMedia | None = None,
) -> tuple[str, bool]:
    """
    Queries AI provider with vision support, context injection, and Groq/Mistral backends.
    Returns: (reply_text, should_send_sticker)
    """
    user_id = user.id if user else 0
    chat_id = chat.id if chat else user_id
    user_name = user.first_name if user else "Friend"
    sess_key = f"gc_{chat_id}_u_{user_id}" if is_group else f"dm_{user_id}"

    # Get active model & thinking level preference
    model_id, think_level = await get_model_pref(chat_id, user_id, is_group)

    # Build prompt and runtime context
    context_str = format_chat_context(chat, user, is_group, is_owner=is_owner)
    full_system = KITTU_SYSTEM_PROMPT + context_str

    messages = _get_history(sess_key, full_system)

    # Build user message content (Multimodal or Pure Text)
    if media and media.base64_data_url:
        query_text = user_prompt
        if not query_text:
            if media.media_type == "photo":
                query_text = "Here is a photo I sent you. Look at it and give your thoughts or reaction."
            else:
                emoji_hint = f" (Sticker emoji: {media.emoji})" if media.emoji else ""
                query_text = (
                    f"Here is a sticker{emoji_hint} I sent. React to it authentically. "
                    "If you feel like sending a sticker back from your collection, include [SEND_STICKER] in your reply."
                )

        user_content = [
            {"type": "text", "text": f"{user_name}: {query_text}"},
            {"type": "image_url", "image_url": {"url": media.base64_data_url}},
        ]
        history_summary = f"[{media.media_type}: {query_text}]"
    else:
        user_content = f"{user_name}: {user_prompt}"
        history_summary = user_prompt

    messages.append({"role": "user", "content": user_content})

    raw_reply = ""

    # Primary Vision: If photo or sticker is provided, Gemini handles multimodal perception
    if media and media.base64_data_url and config.GEMINI_API_KEY:
        raw_reply = await _ask_gemini(messages, full_system, media=media, model="gemini-3.5-flash")

    # If Gemini explicitly chosen
    if not raw_reply and "gemini" in model_id and config.GEMINI_API_KEY:
        raw_reply = await _ask_gemini(messages, full_system, media=media, model=model_id)

    # 1. Groq Inference (Ultra-fast for text)
    if not raw_reply and config.GROQ_API_KEY:
        groq_candidates = []
        if model_id and "gemini" not in model_id:
            groq_candidates.append(model_id)
        for cand in ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "llama-3.3-70b-versatile"]:
            if cand not in groq_candidates:
                groq_candidates.append(cand)

        for model in groq_candidates:
            try:
                async with httpx.AsyncClient(timeout=14.0) as client:
                    res = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {config.GROQ_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": messages,
                            "max_tokens": 200,
                            "temperature": 0.85,
                        },
                    )
                    if res.status_code == 200:
                        data = res.json()
                        raw_reply = data["choices"][0]["message"]["content"].strip()
                        if raw_reply:
                            break
                    else:
                        log.warning(f"[AIBrain] Groq model '{model}' status {res.status_code}: {res.text[:100]}")
            except Exception as e:
                log.warning(f"[AIBrain] Groq error on '{model}': {e}")

    # 2. Gemini Fallback (if Groq fails or no key)
    if not raw_reply and config.GEMINI_API_KEY:
        raw_reply = await _ask_gemini(messages, full_system, media=media, model="gemini-3.5-flash-lite")

    # 3. Mistral AI Fallback (if Groq and Gemini fail or no key)
    if not raw_reply and config.MISTRAL_API_KEY:
        # Mistral does not take image_url in text format easily, fallback to textual representation
        clean_text_messages = []
        for m in messages:
            if isinstance(m["content"], list):
                text_part = next((p["text"] for p in m["content"] if p["type"] == "text"), "")
                clean_text_messages.append({"role": m["role"], "content": text_part})
            else:
                clean_text_messages.append(m)

        for model in ["mistral-small-latest", "open-mistral-7b"]:
            try:
                async with httpx.AsyncClient(timeout=12.0) as client:
                    res = await client.post(
                        "https://api.mistral.ai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {config.MISTRAL_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": clean_text_messages,
                            "max_tokens": 180,
                            "temperature": 0.8,
                        },
                    )
                    if res.status_code == 200:
                        data = res.json()
                        raw_reply = data["choices"][0]["message"]["content"].strip()
                        if raw_reply:
                            break
            except Exception as e:
                log.warning(f"[AIBrain] Mistral error on '{model}': {e}")

    # 3. Smart dynamic fallback
    if not raw_reply:
        fallbacks = [
            f"kya bol rha h {user_name} thoda seedha bol na lol",
            f"acha ji {user_name} sab samajh rhi hu baad me mat bolna maine warn nhi kiya ^_^",
            f"dimag me thoda lag aa gaya tha ek bar wapas bol ^_^",
            f"hn bol na sun rhi hu kya scene h",
        ]
        raw_reply = fallbacks[hash(user_prompt) % len(fallbacks)]

    # Parse [SEND_STICKER] signal
    should_send_sticker = "[SEND_STICKER]" in raw_reply
    clean_reply = raw_reply.replace("[SEND_STICKER]", "").strip()

    # If user explicitly asked for sticker, send one
    lower_p = user_prompt.lower()
    if any(k in lower_p for k in ("sticker bhej", "send sticker", "send a sticker", "sticker de")):
        should_send_sticker = True

    # Sanitize punctuation for authentic human text feel
    clean_reply = sanitize_punctuation(clean_reply)
    if not clean_reply:
        clean_reply = "..."

    _record_history(sess_key, history_summary, clean_reply)
    return clean_reply, should_send_sticker


async def ask_kittu_voice(
    user_prompt: str,
    user: User | None = None,
    chat: Chat | None = None,
    is_group: bool = False,
    is_owner: bool = False,
    custom_speech_text: str | None = None,
) -> str:
    """
    Generates a voice-appropriate response from Kittu.
    For custom speech requests: owner gets compliance, others get savage rejection.
    Returns: reply_text (clean, spoken format, no sticker signals)
    """
    from KITTUBOT.core.voice_engine import get_savage_rejection, clean_text_for_speech

    user_id = user.id if user else 0
    chat_id = chat.id if chat else user_id
    user_name = user.first_name if user else "Friend"
    sess_key = f"gc_{chat_id}_u_{user_id}" if is_group else f"dm_{user_id}"

    # Handle explicit parrot quotes vs instructions
    if custom_speech_text is not None:
        lower_custom = custom_speech_text.lower()
        is_instruction = any(k in lower_custom for k in (
            "gana", "gaana", "order", "bhejo", "bhej", "sunao", "suna", "gao",
            "karo", "batao", "kuch", "shanti", "song", "sing", "say", "bolo", "voice", "vn"
        ))
        if not is_instruction and is_owner:
            cleaned_custom = clean_text_for_speech(custom_speech_text)
            if cleaned_custom and len(cleaned_custom) >= 2:
                _record_history(sess_key, user_prompt, cleaned_custom)
                return cleaned_custom
        elif not is_owner and not is_instruction:
            reply = get_savage_rejection()
            _record_history(sess_key, user_prompt, reply)
            return reply

    # Normal voice reply or owner instruction: use LLM with voice prompt
    model_id, think_level = await get_model_pref(chat_id, user_id, is_group)
    context_str = format_chat_context(chat, user, is_group, is_owner=is_owner)
    full_system = KITTU_SYSTEM_PROMPT + KITTU_VOICE_PROMPT_ADDON + context_str

    messages = _get_history(sess_key, full_system)
    messages.append({"role": "user", "content": f"{user_name}: {user_prompt}"})

    raw_reply = ""

    # If Gemini explicitly chosen
    if "gemini" in model_id and config.GEMINI_API_KEY:
        raw_reply = await _ask_gemini(messages, full_system, model=model_id)

    # 1. Groq
    if not raw_reply and config.GROQ_API_KEY:
        groq_voice_models = []
        if model_id and "gemini" not in model_id:
            groq_voice_models.append(model_id)
        for cand in ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "llama-3.3-70b-versatile"]:
            if cand not in groq_voice_models:
                groq_voice_models.append(cand)

        for model in groq_voice_models:
            try:
                async with httpx.AsyncClient(timeout=14.0) as client:
                    res = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {config.GROQ_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json={"model": model, "messages": messages, "max_tokens": 250, "temperature": 0.75, "frequency_penalty": 0.3},
                    )
                    if res.status_code == 200:
                        raw_reply = res.json()["choices"][0]["message"]["content"].strip()
                        if raw_reply:
                            break
            except Exception:
                pass

    # 2. Gemini fallback
    if not raw_reply and config.GEMINI_API_KEY:
        raw_reply = await _ask_gemini(messages, full_system, model="gemini-3.5-flash-lite")

    # 3. Mistral fallback
    if not raw_reply and config.MISTRAL_API_KEY:
        clean_text_messages = []
        for m in messages:
            if isinstance(m["content"], list):
                text_part = next((p["text"] for p in m["content"] if p["type"] == "text"), "")
                clean_text_messages.append({"role": m["role"], "content": text_part})
            else:
                clean_text_messages.append(m)

        for model in ["mistral-small-latest", "open-mistral-7b"]:
            try:
                async with httpx.AsyncClient(timeout=12.0) as client:
                    res = await client.post(
                        "https://api.mistral.ai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {config.MISTRAL_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": clean_text_messages,
                            "max_tokens": 80,
                            "temperature": 0.8,
                        },
                    )
                    if res.status_code == 200:
                        raw_reply = res.json()["choices"][0]["message"]["content"].strip()
                        if raw_reply:
                            break
            except Exception:
                pass

    # 3. Dynamic fallback
    if not raw_reply:
        if is_owner:
            raw_reply = "haan bolo na sun rhi hu kya hua"
        else:
            raw_reply = f"haan sun rhi hu {user_name} bol na kya hua"

    # Clean up for voice
    clean_reply = clean_text_for_speech(raw_reply)
    if not clean_reply:
        clean_reply = sanitize_punctuation(raw_reply)
    clean_reply = clean_reply.replace("[SEND_STICKER]", "").strip()

    _record_history(sess_key, user_prompt, clean_reply)
    return clean_reply if clean_reply else "hmm"
