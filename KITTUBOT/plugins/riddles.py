# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Riddles & Brain Teasers Plugin
Group riddle generator with automated answer validation & coin bounties.
"""

import random
import re
import time
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from KITTUBOT.config import config
from KITTUBOT.database.users import update_balance
from KITTUBOT.database import riddles_col

__mod_name__ = "Riddles"
__help__ = """
<blockquote>🧩 <b>ʀɪᴅᴅʟᴇs & ᴛʀɪᴠɪᴀ:</b>
• <code>/riddle</code> - sᴘᴀᴡɴ ᴀ ʙʀᴀɪɴ ᴛᴇᴀsᴇʀ ɪɴ ᴄʜᴀᴛ
• <code>/stopriddle</code> - ᴄᴀɴᴄᴇʟ ᴄᴜʀʀᴇɴᴛ ʀɪᴅᴅʟᴇ
• ғɪʀsᴛ ᴍᴇᴍʙᴇʀ ᴛᴏ ʀᴇᴘʟʏ ᴄᴏʀʀᴇᴄᴛʟʏ ᴡɪɴs ᴄᴏɪɴs!</blockquote>
"""

CURATED_RIDDLES = [
    {"q": "What has to be broken before you can use it?", "a": "egg"},
    {"q": "I’m tall when I’m young, and I’m short when I’m old. What am I?", "a": "candle"},
    {"q": "What month of the year has 28 days?", "a": "all"},
    {"q": "What is full of holes but still holds water?", "a": "sponge"},
    {"q": "What question can you never answer yes to?", "a": "asleep"},
    {"q": "What gets wet while drying?", "a": "towel"},
    {"q": "What can you break, even if you never pick it up or touch it?", "a": "promise"},
    {"q": "I have branches, but no fruit, trunk or leaves. What am I?", "a": "bank"},
    {"q": "What can travel all around the world without leaving its corner?", "a": "stamp"},
]

RIDDLE_TIMEOUT_TASKS: dict[int, asyncio.Task] = {}


async def riddle_timeout_job(context: ContextTypes.DEFAULT_TYPE, chat_id: int, answer: str):
    """Automatically expires an unsolved riddle after 120 seconds."""
    await asyncio.sleep(120)
    active = await riddles_col.find_one({"chat_id": chat_id, "active": True})
    if active:
        await riddles_col.update_one({"_id": active["_id"]}, {"$set": {"active": False}})
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    "⏰ <b>ᴛɪᴍᴇ's ᴜᴘ — ʀɪᴅᴅʟᴇ ᴇxᴘɪʀᴇᴅ!</b>\n\n"
                    f"<blockquote>Nobody solved the brain teaser in time!\n"
                    f"💡 <b>Correct Answer:</b> <code>{answer.title()}</code></blockquote>\n\n"
                    "🎋 <i>Type /riddle to challenge the group again!</i>"
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass


async def riddle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    active = await riddles_col.find_one({"chat_id": chat.id, "active": True})
    now = time.time()

    # Auto-expire stale riddle older than 3 minutes
    if active and (now - active.get("created_at", now)) > 180:
        await riddles_col.update_one({"_id": active["_id"]}, {"$set": {"active": False}})
        active = None

    if active:
        await update.message.reply_html(
            f"⚠️ <b>Active Riddle Running!</b>\n\n"
            f"<blockquote>❓ <i>{active['question']}</i>\n"
            f"💰 Bounty: <b>{config.RIDDLE_REWARD} Coins</b></blockquote>\n"
            "🎋 <i>Reply to solve it, or type /stopriddle to cancel.</i>"
        )
        return

    riddle = random.choice(CURATED_RIDDLES)
    await riddles_col.insert_one({
        "chat_id": chat.id,
        "question": riddle["q"],
        "answer": riddle["a"].lower(),
        "created_at": now,
        "active": True,
    })

    await update.message.reply_html(
        f"🧩 <b>ᴋɪᴛᴛᴜ ʙʀᴀɪɴ ᴛᴇᴀsᴇʀ!</b>\n\n"
        f"<blockquote><b>Question:</b> <i>{riddle['q']}</i>\n\n"
        f"💰 <b>Reward:</b> <code>{config.RIDDLE_REWARD:,} Coins</code>\n"
        f"⏳ <b>Time:</b> <code>2 Minutes</code></blockquote>\n"
        f"🎋 <i>Reply to this message with your answer to claim!</i>"
    )

    # Cancel previous timeout task if any
    if chat.id in RIDDLE_TIMEOUT_TASKS:
        RIDDLE_TIMEOUT_TASKS[chat.id].cancel()
    RIDDLE_TIMEOUT_TASKS[chat.id] = asyncio.create_task(
        riddle_timeout_job(context, chat.id, riddle["a"])
    )


async def check_riddle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message.text or not message.reply_to_message:
        return

    chat = update.effective_chat
    user = update.effective_user

    active = await riddles_col.find_one({"chat_id": chat.id, "active": True})
    if not active:
        return

    user_guess = message.text.strip().lower()
    ans = active["answer"].lower()

    # Check whole word boundary match or equality to avoid substring false positives
    matched = (user_guess == ans) or bool(re.search(rf"\b{re.escape(ans)}\b", user_guess))
    if matched:
        await riddles_col.update_one({"_id": active["_id"]}, {"$set": {"active": False}})
        if chat.id in RIDDLE_TIMEOUT_TASKS:
            RIDDLE_TIMEOUT_TASKS[chat.id].cancel()

        await update_balance(user.id, config.RIDDLE_REWARD)

        await message.reply_html(
            f"🎉 <b>ᴄᴏʀʀᴇᴄᴛ ᴀɴsᴡᴇʀ!</b>\n\n"
            f"<blockquote>Well done {user.mention_html()}! The answer was <b>{ans.title()}</b>!\n"
            f"🏆 You earned <b>+{config.RIDDLE_REWARD:,} Coins</b>! 🪙</blockquote>"
        )


async def stop_riddle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    active = await riddles_col.find_one({"chat_id": chat.id, "active": True})
    if active:
        await riddles_col.update_one({"_id": active["_id"]}, {"$set": {"active": False}})
        if chat.id in RIDDLE_TIMEOUT_TASKS:
            RIDDLE_TIMEOUT_TASKS[chat.id].cancel()
        await update.message.reply_html(
            f"🛑 <b>Riddle cancelled!</b> The answer was: <code>{active['answer'].title()}</code>"
        )
    else:
        await update.message.reply_html("No active riddle running in this chat.")


def register_handlers(app: Application):
    app.add_handler(CommandHandler(["riddle", "quizriddle"], riddle_command))
    app.add_handler(CommandHandler(["stopriddle", "endriddle"], stop_riddle_command))
    app.add_handler(
        MessageHandler(filters.TEXT & filters.REPLY & ~filters.COMMAND, check_riddle_answer),
        group=10,
    )
