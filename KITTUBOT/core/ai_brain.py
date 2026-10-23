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


def format_chat_context(chat: Chat | None, user: User | None, is_group: bool) -> str:
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


async def ask_kittu(
    user_prompt: str,
    user: User | None = None,
    chat: Chat | None = None,
    is_group: bool = False,
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
    context_str = format_chat_context(chat, user, is_group)
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

    # 1. Groq Inference (Ultra-fast)
    if config.GROQ_API_KEY:
        # Determine candidate models for Groq
        groq_candidates = [model_id] if "groq" in model_id or "llama" in model_id or "qwen" in model_id else []
        groq_candidates.extend(["llama-3.3-70b-versatile", "qwen/qwen3.8-27b", "openai/gpt-oss-120b"])

        # Vision handling on Groq
        if media and media.base64_data_url:
            groq_candidates = ["llama-3.2-11b-vision-preview", "llama-3.2-90b-vision-preview"] + groq_candidates

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

    # 2. Mistral AI Fallback (if Groq fails or no key)
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
            f"dimag me thoda lag aa gaya tha ek bar wapas bol dY~-",
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
