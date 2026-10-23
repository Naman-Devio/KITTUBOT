# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🧠 KITTUBOT Paginated Interactive Model Switcher & Thinking Depth Control
Allows inline keyboard navigation with zero message spam.
"""

from dataclasses import dataclass
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from KITTUBOT.database.models_pref import get_model_pref, set_model_pref

__mod_name__ = "Models"
__help__ = """
<blockquote>🧠 <b>AI Model & Reasoning Switcher:</b>
• <code>/models</code> - Open interactive inline menu to switch AI models & reasoning depth
• <code>/model [name]</code> - Directly switch model (e.g. <code>/model llama-3.3-70b-versatile</code>)</blockquote>
"""


@dataclass
class ModelItem:
    id: str
    name: str
    desc: str


MODEL_CATALOG: list[ModelItem] = [
    ModelItem("llama-3.3-70b-versatile", "Llama 3.3 70B (Groq)", "Ultra-Fast Groq Inference"),
    ModelItem("deepseek-r1-distill-llama-70b", "DeepSeek R1 (Groq)", "Deep Reasoning & Logic"),
    ModelItem("qwen/qwen3.8-27b", "Qwen 3.8 27B", "Smart Natural Dialogue"),
    ModelItem("openai/gpt-oss-120b", "GPT-OSS 120B", "Frontier High Capacity"),
    ModelItem("gemini-2.0-flash", "Gemini 2.0 Flash", "Multimodal Flash Vision"),
    ModelItem("mistral-small-latest", "Mistral Small", "Fast & Coherent"),
    ModelItem("gpt-4o-mini", "OpenAI GPT-4o Mini", "Frontier Conversational"),
    ModelItem("open-mistral-7b", "Mistral 7B", "Lightweight Fallback"),
]

PAGE_SIZE = 4


async def render_models_page(chat_id: int, user_id: int, is_group: bool, page: int) -> tuple[str, InlineKeyboardMarkup]:
    """Generates text and inline markup for a specific page of models."""
    total_models = len(MODEL_CATALOG)
    total_pages = (total_models + PAGE_SIZE - 1) // PAGE_SIZE

    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1

    cur_model, cur_think = await get_model_pref(chat_id, user_id, is_group)

    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, total_models)
    page_models = MODEL_CATALOG[start:end]

    text = (
        "<b>🧠 Select AI Model for this Chat</b>\n\n"
        f"• <b>Active Model:</b> <code>{cur_model}</code>\n"
        f"• <b>Thinking Depth:</b> <code>{cur_think.upper()}</code>\n"
        f"• <b>Page:</b> <code>{page + 1}/{total_pages}</code>\n\n"
        "<i>Tap a button below to switch model instantly:</i>"
    )

    keyboard = []

    # Model selection buttons
    for m in page_models:
        is_active = (cur_model == m.id)
        btn_label = f"✔ {m.name}" if is_active else m.name
        cb_data = f"mdl_set:{m.id}:{page}"
        keyboard.append([InlineKeyboardButton(btn_label, callback_data=cb_data)])

    # Reasoning / Think depth button
    think_btn = InlineKeyboardButton(
        f"🧠 Thinking: {cur_think.upper()}",
        callback_data=f"mdl_think:{page}",
    )
    keyboard.append([think_btn])

    # Navigation buttons: Prev / Close / Next
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀ Prev", callback_data=f"mdl_page:{page - 1}"))
    else:
        nav_row.append(InlineKeyboardButton("•", callback_data="mdl_noop"))

    nav_row.append(InlineKeyboardButton("❌ Close", callback_data="mdl_close"))

    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Next ▶", callback_data=f"mdl_page:{page + 1}"))
    else:
        nav_row.append(InlineKeyboardButton("•", callback_data="mdl_noop"))

    keyboard.append(nav_row)

    return text, InlineKeyboardMarkup(keyboard)


async def models_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Opens interactive /models inline keyboard."""
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if not message or not user:
        return

    is_group = (chat.type != "private")
    text, markup = await render_models_page(chat.id, user.id, is_group, page=0)
    await message.reply_html(text, reply_markup=markup)


async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Directly switches model via text argument (e.g. /model llama-3.3-70b-versatile)."""
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if not message or not user:
        return

    if not context.args:
        return await models_command(update, context)

    target_model = context.args[0].strip().lower()
    is_group = (chat.type != "private")

    await set_model_pref(chat.id, user.id, is_group, model=target_model)
    await message.reply_html(f"✨ Switched model to <code>{target_model}</code> for this session!")


async def models_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles pagination, model selection, and thinking depth toggles."""
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data
    user = update.effective_user
    chat = update.effective_chat
    is_group = (chat.type != "private")

    if data == "mdl_noop":
        await query.answer()
        return

    if data == "mdl_close":
        await query.answer("Closed!")
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    if data.startswith("mdl_page:"):
        page = int(data.split(":")[1])
        text, markup = await render_models_page(chat.id, user.id, is_group, page)
        try:
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            pass
        await query.answer()
        return

    if data.startswith("mdl_set:"):
        _, model_id, page_str = data.split(":")
        page = int(page_str)
        await set_model_pref(chat.id, user.id, is_group, model=model_id)
        await query.answer(f"✨ Switched model to: {model_id}")

        text, markup = await render_models_page(chat.id, user.id, is_group, page)
        try:
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            pass
        return

    if data.startswith("mdl_think:"):
        page = int(data.split(":")[1])
        _, cur_think = await get_model_pref(chat.id, user.id, is_group)

        # Cycle: low -> medium -> high -> off -> low
        cycle_map = {
            "low": "medium",
            "medium": "high",
            "high": "off",
            "off": "low",
        }
        next_think = cycle_map.get(cur_think, "low")
        await set_model_pref(chat.id, user.id, is_group, think=next_think)
        await query.answer(f"🧠 Thinking depth: {next_think.upper()}")

        text, markup = await render_models_page(chat.id, user.id, is_group, page)
        try:
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            pass
        return


def register_handlers(app: Application):
    app.add_handler(CommandHandler("models", models_command))
    app.add_handler(CommandHandler("model", model_command))
    app.add_handler(CallbackQueryHandler(models_callback_handler, pattern=r"^mdl_"))
