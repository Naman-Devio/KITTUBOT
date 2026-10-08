# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Complete Word & Brain Games Suite
Word Chain, Unscramble, Emoji Guessing, Hangman, Trivia Quiz & Truth/Dare.
"""

import random
import time
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from KITTUBOT.database.users import ensure_user, update_balance

__mod_name__ = "WordGames"
__help__ = """
<blockquote>🔤 <b>ᴡᴏʀᴅ & ʙʀᴀɪɴ ɢᴀᴍᴇs:</b>
• <code>/words</code> - ɪɴᴛᴇʀᴀᴄᴛɪᴠᴇ ɢᴀᴍᴇ ʟᴀᴜɴᴄʜᴇʀ
• <code>/wordseek</code> - ᴡᴏʀᴅʟᴇ / ᴡᴏʀᴅsᴇᴇᴋ (4, 5, 6-ʟᴇᴛᴛᴇʀ & ᴅᴀɪʟʏ)
• <code>/wordchain</code> - sᴛᴀʀᴛ ᴡᴏʀᴅ ᴄʜᴀɪɴ (ᴄʜᴀɪɴ ʟᴀsᴛ ʟᴇᴛᴛᴇʀ)
• <code>/unscramble</code> - sᴄʀᴀᴍʙʟᴇᴅ ᴡᴏʀᴅ ᴄʜᴀʟʟᴇɴɢᴇ
• <code>/emojiguess</code> - ɢᴜᴇss ᴍᴏᴠɪᴇ/ᴡᴏʀᴅ ғʀᴏᴍ ᴇᴍᴏᴊɪs
• <code>/hangman</code> - ᴄʟᴀssɪᴄ ʜᴀɴɢᴍᴀɴ ʟᴇᴛᴛᴇʀ ɢᴜᴇss
• <code>/quiz</code> - ᴛʀɪᴠɪᴀ ǫᴜɪᴢ ᴡɪᴛʜ ᴄᴏɪɴ ᴘʀɪᴢᴇs
• <code>/truth</code> & <code>/dare</code> - ᴘᴀʀᴛʏ ᴛʀᴜᴛʜ ᴏʀ ᴅᴀʀᴇ
• <code>/stopword</code> - ᴇɴᴅ ᴀᴄᴛɪᴠᴇ ᴡᴏʀᴅ ɢᴀᴍᴇ</blockquote>
"""

CURATED_WORDS = [
    "apple", "banana", "cat", "dog", "elephant", "falcon", "giraffe", "horse",
    "iguana", "jungle", "koala", "lion", "monkey", "nest", "octopus", "penguin",
    "queen", "rabbit", "snake", "tiger", "umbrella", "viper", "whale", "xylophone",
    "yak", "zebra", "balloon", "castle", "dragon", "emerald", "forest", "galaxy",
    "harbor", "island", "journey", "kingdom", "lantern", "mountain", "nebula",
    "ocean", "planet", "quasar", "rainbow", "shadow", "thunder", "universe",
    "volcano", "wizard", "phoenix", "diamond", "crystal", "blizzard", "samurai",
    "matrix", "cyber", "phantom", "legend", "vortex", "aurora", "comet", "beacon",
    "horizon", "starlight", "titan", "glacier", "avalanche", "solitude", "dynamo"
]

EMOJI_PUZZLES = [
    {"emoji": "🕷️ 👨", "answer": "spiderman", "hint": "Marvel superhero"},
    {"emoji": "🦁 👑", "answer": "lion king", "hint": "Disney classic animation"},
    {"emoji": "🍎 🥧", "answer": "apple pie", "hint": "Delicious baked dessert"},
    {"emoji": "🧊 🚢", "answer": "titanic", "hint": "Famous doomed ship movie"},
    {"emoji": "🧙‍♂️ 💍", "answer": "lord of the rings", "hint": "Epic fantasy saga"},
    {"emoji": "🦇 👨", "answer": "batman", "hint": "The Dark Knight"},
    {"emoji": "🍕 🐢", "answer": "ninja turtles", "hint": "Heroes in a half shell"},
    {"emoji": "🚀 🌕", "answer": "apollo", "hint": "Moon landing mission"},
    {"emoji": "❄️ 👸", "answer": "frozen", "hint": "Let it go!"},
    {"emoji": "🍫 🏭", "answer": "charlie and the chocolate factory", "hint": "Willy Wonka"},
    {"emoji": "⚡ 👓 🧙", "answer": "harry potter", "hint": "Boy who lived"},
    {"emoji": "🏴‍☠️ ⚓ 🦜", "answer": "pirates of the caribbean", "hint": "Captain Jack Sparrow"},
    {"emoji": "🦕 🌴 🦖", "answer": "jurassic park", "hint": "Dinosaur island"},
    {"emoji": "👻 🚫 🔫", "answer": "ghostbusters", "hint": "Who you gonna call?"},
    {"emoji": "🐼 🥋 🥢", "answer": "kung fu panda", "hint": "Dragon warrior Po"},
]

TRIVIA_QUESTIONS = [
    {
        "q": "What is the capital of India?",
        "options": ["Mumbai", "New Delhi", "Kolkata", "Bengaluru"],
        "correct": 1,
        "exp": "New Delhi is the official national capital of India."
    },
    {
        "q": "Which planet is known as the Red Planet?",
        "options": ["Venus", "Mars", "Jupiter", "Saturn"],
        "correct": 1,
        "exp": "Mars gets its reddish color from iron oxide on its surface."
    },
    {
        "q": "What is the largest ocean on Earth?",
        "options": ["Atlantic Ocean", "Indian Ocean", "Pacific Ocean", "Arctic Ocean"],
        "correct": 2,
        "exp": "The Pacific Ocean covers over 30% of Earth's total surface."
    },
    {
        "q": "Who invented the World Wide Web in 1989?",
        "options": ["Steve Jobs", "Bill Gates", "Tim Berners-Lee", "Alan Turing"],
        "correct": 2,
        "exp": "Sir Tim Berners-Lee invented the World Wide Web at CERN."
    },
    {
        "q": "How many players are on a standard soccer team on the field?",
        "options": ["9", "10", "11", "12"],
        "correct": 2,
        "exp": "Each soccer team fields 11 players including the goalkeeper."
    },
    {
        "q": "Which element has the chemical symbol 'Au'?",
        "options": ["Silver", "Gold", "Copper", "Aluminum"],
        "correct": 1,
        "exp": "Au comes from the Latin word 'Aurum', meaning Gold."
    },
]

# Dynamically enrich question bank with curated anime trivia from assets/trivia.json
from pathlib import Path
import json

_TRIVIA_ASSET = Path(__file__).resolve().parent.parent / "assets" / "trivia.json"
try:
    if _TRIVIA_ASSET.exists():
        with open(_TRIVIA_ASSET, encoding="utf-8") as f:
            _raw = json.load(f)
            for item in _raw.get("questions", []):
                opts = item.get("options", [])
                ans = item.get("answer", "")
                if ans in opts:
                    c_idx = opts.index(ans)
                    TRIVIA_QUESTIONS.append({
                        "q": item.get("question", ""),
                        "options": opts,
                        "correct": c_idx,
                        "exp": f"The correct answer is {ans}!",
                    })
except Exception:
    pass

TRUTH_PROMPTS = [
    "What is your most embarrassing moment that still keeps you up at night?",
    "Who is your current secret crush?",
    "What is the biggest lie you ever told your parents without getting caught?",
    "If you could trade lives with one person in this group for a day, who would it be?",
    "What is your biggest guilty pleasure that nobody knows about?",
    "Have you ever stalked someone's profile for more than an hour?",
    "What is the worst date or hangout you've ever had?",
    "What is something you pretend to like just to fit in?",
]

DARE_PROMPTS = [
    "Send a voice note singing your favorite Bollywood/English song in chat!",
    "Send the 5th photo from your gallery right now without context!",
    "Text your crush or bestie 'I have a huge confession' and post their reply screenshot!",
    "Send your funniest or most awkward selfie in the group!",
    "Type out a message with your nose and send it in chat!",
    "Give genuine compliments to the last 3 people who sent a message!",
    "Change your Telegram bio to 'I am Kittu Bot's #1 Fan' for 1 hour!",
]

# Active game states per chat: chat_id -> game_dict
ACTIVE_GAMES: dict[int, dict] = {}
GAME_TIMEOUT_TASKS: dict[int, asyncio.Task] = {}


async def auto_expire_word_game(context: ContextTypes.DEFAULT_TYPE, chat_id: int, game_type: str, answer: str):
    """Automatically cleans up and announces answer after 90 seconds."""
    await asyncio.sleep(90)
    if chat_id in ACTIVE_GAMES and ACTIVE_GAMES[chat_id].get("type") == game_type:
        del ACTIVE_GAMES[chat_id]
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"⏰ <b>ᴛɪᴍᴇ's ᴜᴘ!</b> 🎮\n\n"
                    f"<blockquote>Nobody solved the <b>{game_type.title()}</b> game in time!\n"
                    f"💡 <b>Correct Answer:</b> <code>{answer.upper()}</code></blockquote>\n\n"
                    "🎋 <i>Type /words to launch another challenge!</i>"
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass


def check_and_clear_stale_game(chat_id: int) -> bool:
    """Returns True if there is still an active non-stale game."""
    if chat_id in ACTIVE_GAMES:
        game = ACTIVE_GAMES[chat_id]
        if time.time() - game.get("started_at", 0) > 120:
            if chat_id in GAME_TIMEOUT_TASKS:
                GAME_TIMEOUT_TASKS[chat_id].cancel()
            del ACTIVE_GAMES[chat_id]
            return False
        return True
    return False


async def words_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Word games launcher menu."""
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔗 ᴡᴏʀᴅ ᴄʜᴀɪɴ", callback_data="wg_start_chain"),
            InlineKeyboardButton("🧩 ᴜɴsᴄʀᴀᴍʙʟᴇ", callback_data="wg_start_unscramble"),
        ],
        [
            InlineKeyboardButton("🎭 ᴇᴍᴏᴊɪ ɢᴜᴇss", callback_data="wg_start_emoji"),
            InlineKeyboardButton("🪓 ʜᴀɴɢᴍᴀɴ", callback_data="wg_start_hangman"),
        ],
        [
            InlineKeyboardButton("🔍 ᴡᴏʀᴅsᴇᴇᴋ", callback_data="wg_start_wordseek"),
            InlineKeyboardButton("💡 ᴛʀɪᴠɪᴀ ǫᴜɪᴢ", callback_data="wg_start_quiz"),
        ],
        [
            InlineKeyboardButton("❌ ᴄʟᴏsᴇ", callback_data="close_menu"),
        ]
    ])
    text = (
        "🔤 <b>ᴋɪᴛᴛᴜ ᴡᴏʀᴅ & ʙʀᴀɪɴ ɢᴀᴍᴇs</b> ✨\n\n"
        "<blockquote>ᴄʜᴏᴏsᴇ ᴀ ɢᴀᴍᴇ ᴍᴏᴅᴇ ʙᴇʟᴏᴡ ᴛᴏ ᴄʜᴀʟʟᴇɴɢᴇ ʏᴏᴜʀ ɢʀᴏᴜᴘ ᴍᴇᴍʙᴇʀs!\n"
        "ᴇᴀᴄʜ ᴄᴏʀʀᴇᴄᴛ ᴀɴsᴡᴇʀ ᴇᴀʀɴs ᴠɪʀᴛᴜᴀʟ ᴄᴏɪɴs! 🪙</blockquote>"
    )
    if update.callback_query:
        try:
            await update.callback_query.answer()
        except Exception:
            pass
        await update.callback_query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update.message.reply_html(text=text, reply_markup=keyboard)


async def start_word_chain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if check_and_clear_stale_game(chat.id):
        msg = "⚠️ A game is already active in this chat! Finish it or type /stopword."
        if update.callback_query:
            try:
                await update.callback_query.answer(msg, show_alert=True)
            except Exception:
                pass
        else:
            await update.message.reply_html(msg)
        return

    first_word = random.choice(CURATED_WORDS)
    ACTIVE_GAMES[chat.id] = {
        "type": "chain",
        "last_word": first_word,
        "used": [first_word],
        "scores": {},
        "started_at": time.time(),
    }

    text = (
        "🔗 <b>ᴡᴏʀᴅ ᴄʜᴀɪɴ sᴛᴀʀᴛᴇᴅ!</b>\n\n"
        f"<blockquote>• sᴛᴀʀᴛɪɴɢ ᴡᴏʀᴅ: <b>{first_word.upper()}</b>\n"
        f"• ɴᴇxᴛ ᴡᴏʀᴅ ᴍᴜsᴛ sᴛᴀʀᴛ ᴡɪᴛʜ: <b>{first_word[-1].upper()}</b></blockquote>\n\n"
        "🎋 <i>Send your next English word in chat! Each valid word earns +150 Coins!</i>"
    )
    if update.callback_query:
        try:
            await update.callback_query.answer()
        except Exception:
            pass
        await update.callback_query.edit_message_text(text=text, parse_mode="HTML")
    else:
        await update.message.reply_html(text)


async def start_unscramble(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if check_and_clear_stale_game(chat.id):
        msg = "⚠️ A game is already active in this chat!"
        if update.callback_query:
            try:
                await update.callback_query.answer(msg, show_alert=True)
            except Exception:
                pass
        else:
            await update.message.reply_html(msg)
        return

    word = random.choice(CURATED_WORDS)
    scrambled_list = list(word)
    while "".join(scrambled_list) == word and len(word) > 1:
        random.shuffle(scrambled_list)
    scrambled = "".join(scrambled_list).upper()

    ACTIVE_GAMES[chat.id] = {
        "type": "unscramble",
        "answer": word.lower(),
        "reward": 500,
        "started_at": time.time(),
    }

    # Start 90s auto-expiry
    if chat.id in GAME_TIMEOUT_TASKS:
        GAME_TIMEOUT_TASKS[chat.id].cancel()
    GAME_TIMEOUT_TASKS[chat.id] = asyncio.create_task(
        auto_expire_word_game(context, chat.id, "unscramble", word)
    )

    text = (
        "🧩 <b>ᴡᴏʀᴅ ᴜɴsᴄʀᴀᴍʙʟᴇ ᴄʜᴀʟʟᴇɴɢᴇ!</b>\n\n"
        f"<blockquote>🔀 sᴄʀᴀᴍʙʟᴇᴅ: <code>{scrambled}</code>\n"
        f"💰 ʙᴏᴜɴᴛʏ: <b>500 Coins</b>\n"
        f"⏳ ᴛɪᴍᴇ: <b>90 Seconds</b>\n"
        f"💡 ʟᴇɴɢᴛʜ: <b>{len(word)} letters</b></blockquote>\n\n"
        "🎋 <i>First member to send the correct word wins the prize!</i>"
    )
    if update.callback_query:
        try:
            await update.callback_query.answer()
        except Exception:
            pass
        await update.callback_query.edit_message_text(text=text, parse_mode="HTML")
    else:
        await update.message.reply_html(text)


async def start_emoji_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if check_and_clear_stale_game(chat.id):
        msg = "⚠️ A game is already active in this chat!"
        if update.callback_query:
            try:
                await update.callback_query.answer(msg, show_alert=True)
            except Exception:
                pass
        else:
            await update.message.reply_html(msg)
        return

    puzzle = random.choice(EMOJI_PUZZLES)
    ACTIVE_GAMES[chat.id] = {
        "type": "emoji",
        "answer": puzzle["answer"].lower(),
        "reward": 750,
        "started_at": time.time(),
    }

    # Start 90s auto-expiry
    if chat.id in GAME_TIMEOUT_TASKS:
        GAME_TIMEOUT_TASKS[chat.id].cancel()
    GAME_TIMEOUT_TASKS[chat.id] = asyncio.create_task(
        auto_expire_word_game(context, chat.id, "emoji", puzzle["answer"])
    )

    text = (
        "🎭 <b>ᴇᴍᴏᴊɪ ɢᴜᴇssɪɴɢ ɢᴀᴍᴇ!</b>\n\n"
        f"<blockquote>❓ ᴘᴜᴢᴢʟᴇ: {puzzle['emoji']}\n"
        f"💡 ʜɪɴᴛ: <i>{puzzle['hint']}</i>\n"
        f"💰 ʙᴏᴜɴᴛʏ: <b>750 Coins</b>\n"
        f"⏳ ᴛɪᴍᴇ: <b>90 Seconds</b></blockquote>\n\n"
        "🎋 <i>Guess what movie, phrase, or character this represents!</i>"
    )
    if update.callback_query:
        try:
            await update.callback_query.answer()
        except Exception:
            pass
        await update.callback_query.edit_message_text(text=text, parse_mode="HTML")
    else:
        await update.message.reply_html(text)


async def start_hangman(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if check_and_clear_stale_game(chat.id):
        msg = "⚠️ A game is already active in this chat!"
        if update.callback_query:
            try:
                await update.callback_query.answer(msg, show_alert=True)
            except Exception:
                pass
        else:
            await update.message.reply_html(msg)
        return

    word = random.choice(CURATED_WORDS).lower()
    masked = ["_" for _ in word]

    ACTIVE_GAMES[chat.id] = {
        "type": "hangman",
        "word": word,
        "masked": masked,
        "lives": 6,
        "guessed_letters": [],
        "reward": 800,
        "started_at": time.time(),
    }

    # Start 90s auto-expiry
    if chat.id in GAME_TIMEOUT_TASKS:
        GAME_TIMEOUT_TASKS[chat.id].cancel()
    GAME_TIMEOUT_TASKS[chat.id] = asyncio.create_task(
        auto_expire_word_game(context, chat.id, "hangman", word)
    )

    lives_bar = "❤️ " * 6
    display_mask = " ".join(masked)

    text = (
        "🪓 <b>ᴋɪᴛᴛᴜ ʜᴀɴɢᴍᴀɴ ᴄʜᴀʟʟᴇɴɢᴇ!</b> 🎮\n\n"
        f"<blockquote><b>ᴡᴏʀᴅ :</b> <code>{display_mask}</code>\n"
        f"<b>ʟɪᴠᴇs :</b> {lives_bar} (6/6)\n"
        f"💰 <b>ʙᴏᴜɴᴛʏ :</b> 800 Coins\n"
        f"⏳ <b>ᴛɪᴍᴇ :</b> 90 Seconds</blockquote>\n\n"
        "🎋 <i>Send a letter in chat or guess the full word directly!</i>"
    )
    if update.callback_query:
        try:
            await update.callback_query.answer()
        except Exception:
            pass
        await update.callback_query.edit_message_text(text=text, parse_mode="HTML")
    else:
        await update.message.reply_html(text)


async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    quiz = random.choice(TRIVIA_QUESTIONS)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"A) {quiz['options'][0]}", callback_data=f"quiz_ans_0_{quiz['correct']}"),
            InlineKeyboardButton(f"B) {quiz['options'][1]}", callback_data=f"quiz_ans_1_{quiz['correct']}"),
        ],
        [
            InlineKeyboardButton(f"C) {quiz['options'][2]}", callback_data=f"quiz_ans_2_{quiz['correct']}"),
            InlineKeyboardButton(f"D) {quiz['options'][3]}", callback_data=f"quiz_ans_3_{quiz['correct']}"),
        ]
    ])

    text = (
        "💡 <b>ᴋɪᴛᴛᴜ ᴛʀɪᴠɪᴀ ǫᴜɪᴢ!</b> 🧠\n\n"
        f"<blockquote>❓ <b>{quiz['q']}</b>\n\n"
        f"• A) {quiz['options'][0]}\n"
        f"• B) {quiz['options'][1]}\n"
        f"• C) {quiz['options'][2]}\n"
        f"• D) {quiz['options'][3]}</blockquote>\n\n"
        "💰 <b>Reward:</b> <code>500 Coins</code>\n"
        "🎋 <i>Tap your answer option below!</i>"
    )

    if update.callback_query:
        try:
            await update.callback_query.answer()
        except Exception:
            pass
        await update.callback_query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update.message.reply_html(text=text, reply_markup=keyboard)


async def quiz_answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_")
    chosen = int(parts[2])
    correct = int(parts[3])
    user = update.effective_user

    if chosen == correct:
        await ensure_user(user)
        await update_balance(user.id, 500)
        try:
            await query.answer("🎉 Correct Answer! +500 Coins 🪙", show_alert=True)
            await query.edit_message_text(
                f"🎉 <b>ᴛʀɪᴠɪᴀ ᴡɪɴɴᴇʀ!</b> 🏆\n\n"
                f"<blockquote>{user.mention_html()} picked the correct option!\n"
                f"💰 <b>Prize Awarded:</b> <code>+500 Coins</code> 🪙</blockquote>",
                parse_mode="HTML",
            )
        except Exception:
            pass
    else:
        try:
            await query.answer("❌ Wrong answer! Try again next time.", show_alert=True)
        except Exception:
            pass


async def truth_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = random.choice(TRUTH_PROMPTS)
    user = update.effective_user
    await update.message.reply_html(
        f"🌶️ <b>ᴛʀᴜᴛʜ ғᴏʀ {user.mention_html()}!</b>\n\n"
        f"<blockquote>❓ <i>{prompt}</i></blockquote>\n\n"
        "🎋 <i>Answer truthfully in the group chat!</i>"
    )


async def dare_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = random.choice(DARE_PROMPTS)
    user = update.effective_user
    await update.message.reply_html(
        f"🔥 <b>ᴅᴀʀᴇ ғᴏʀ {user.mention_html()}!</b>\n\n"
        f"<blockquote>⚡ <i>{prompt}</i></blockquote>\n\n"
        "🎋 <i>Do the dare and send proof in chat!</i>"
    )


async def handle_game_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes in-chat answers for all active word game modes."""
    message = update.effective_message
    if not message or not message.text or message.text.startswith("/"):
        return

    chat = update.effective_chat
    user = update.effective_user

    if chat.id not in ACTIVE_GAMES:
        return

    game = ACTIVE_GAMES[chat.id]
    user_text = message.text.strip().lower()

    # 1. Unscramble Match
    if game["type"] == "unscramble":
        if user_text == game["answer"]:
            reward = game["reward"]
            del ACTIVE_GAMES[chat.id]
            if chat.id in GAME_TIMEOUT_TASKS:
                GAME_TIMEOUT_TASKS[chat.id].cancel()
            await ensure_user(user)
            await update_balance(user.id, reward)

            await message.reply_html(
                f"🎉 <b>ᴄᴏʀʀᴇᴄᴛ ᴜɴsᴄʀᴀᴍʙʟᴇ!</b>\n\n"
                f"<blockquote>{user.mention_html()} correctly solved: <b>{game['answer'].upper()}</b>!\n"
                f"🏆 Bounty claimed: <b>+{reward} Coins</b>! 🪙</blockquote>"
            )

    # 2. Emoji Guess Match
    elif game["type"] == "emoji":
        target_ans = game["answer"].strip().lower()
        if user_text == target_ans or user_text.replace(" ", "") == target_ans.replace(" ", ""):
            reward = game["reward"]
            del ACTIVE_GAMES[chat.id]
            if chat.id in GAME_TIMEOUT_TASKS:
                GAME_TIMEOUT_TASKS[chat.id].cancel()
            await ensure_user(user)
            await update_balance(user.id, reward)

            await message.reply_html(
                f"🎉 <b>ʙʀɪʟʟɪᴀɴᴛ ɢᴜᴇss!</b>\n\n"
                f"<blockquote>{user.mention_html()} correctly identified: <b>{game['answer'].title()}</b>!\n"
                f"🏆 Bounty claimed: <b>+{reward} Coins</b>! 🪙</blockquote>"
            )

    # 3. Word Chain Match
    elif game["type"] == "chain":
        last_word = game["last_word"]
        expected_char = last_word[-1].lower()

        if " " in user_text or not user_text.isalpha():
            return

        if not user_text.startswith(expected_char):
            return

        if user_text in game["used"]:
            await message.reply_html(
                f"⚠️ <i>'{user_text.title()}' has already been used in this chain! Try another word!</i>"
            )
            return

        game["last_word"] = user_text
        game["used"].append(user_text)
        game["scores"][user.id] = game["scores"].get(user.id, 0) + 1

        await ensure_user(user)
        await update_balance(user.id, 150)

        next_char = user_text[-1].upper()
        count = len(game["used"])

        await message.reply_html(
            f"✅ <b>{user.mention_html()}:</b> <code>{user_text.upper()}</code> (+150 🪙)\n"
            f"<blockquote>🔗 Chain Length: <b>{count}</b>\n"
            f"👉 Next word must start with: <b>{next_char}</b></blockquote>"
        )

    # 4. Hangman Match
    elif game["type"] == "hangman":
        target_word = game["word"].lower()

        # Direct whole word solve
        if user_text == target_word:
            reward = game["reward"]
            del ACTIVE_GAMES[chat.id]
            if chat.id in GAME_TIMEOUT_TASKS:
                GAME_TIMEOUT_TASKS[chat.id].cancel()
            await ensure_user(user)
            await update_balance(user.id, reward)

            await message.reply_html(
                f"🎉 <b>ʙʀɪʟʟɪᴀɴᴛ! ʜᴀɴɢᴍᴀɴ sᴏʟᴠᴇᴅ ɪɴ ᴏɴᴇ sʜᴏᴛ!</b> 🏆\n\n"
                f"<blockquote>{user.mention_html()} directly guessed the whole word: <b>{target_word.upper()}</b>!\n"
                f"💰 Bounty claimed: <b>+{reward:,} Coins</b>! 🪙</blockquote>"
            )
            return

        # Only single letter guesses
        if len(user_text) != 1 or not user_text.isalpha():
            return

        letter = user_text.lower()
        if letter in game["guessed_letters"]:
            return

        game["guessed_letters"].append(letter)

        if letter in target_word:
            # Reveal letter in masked string
            for idx, c in enumerate(target_word):
                if c == letter:
                    game["masked"][idx] = letter

            # Check full win
            if "_" not in game["masked"]:
                reward = game["reward"]
                del ACTIVE_GAMES[chat.id]
                if chat.id in GAME_TIMEOUT_TASKS:
                    GAME_TIMEOUT_TASKS[chat.id].cancel()
                await ensure_user(user)
                await update_balance(user.id, reward)

                await message.reply_html(
                    f"🎉 <b>ʜᴀɴɢᴍᴀɴ sᴏʟᴠᴇᴅ!</b> 🏆\n\n"
                    f"<blockquote>{user.mention_html()} completed the mystery word: <b>{target_word.upper()}</b>!\n"
                    f"💰 Bounty claimed: <b>+{reward:,} Coins</b>! 🪙</blockquote>"
                )
                return

            display_mask = " ".join(game["masked"]).upper()
            lives_bar = "❤️ " * game["lives"]
            await message.reply_html(
                f"✅ <b>Good letter '{letter.upper()}'!</b>\n\n"
                f"<blockquote><b>ᴡᴏʀᴅ :</b> <code>{display_mask}</code>\n"
                f"<b>ʟɪᴠᴇs :</b> {lives_bar} ({game['lives']}/6)</blockquote>"
            )
        else:
            game["lives"] -= 1
            display_mask = " ".join(game["masked"]).upper()
            lives_bar = "❤️ " * game["lives"]

            if game["lives"] <= 0:
                answer = target_word.upper()
                del ACTIVE_GAMES[chat.id]
                if chat.id in GAME_TIMEOUT_TASKS:
                    GAME_TIMEOUT_TASKS[chat.id].cancel()
                await message.reply_html(
                    f"💀 <b>ɢᴀᴍᴇ ᴏᴠᴇʀ — ʜᴀɴɢᴍᴀɴ ʟᴏsᴛ!</b>\n\n"
                    f"<blockquote>The man was hanged! The mystery word was: <b>{answer}</b>.</blockquote>"
                )
            else:
                await message.reply_html(
                    f"❌ <b>Wrong letter '{letter.upper()}'!</b> Lost 1 life!\n\n"
                    f"<blockquote><b>ᴡᴏʀᴅ :</b> <code>{display_mask}</code>\n"
                    f"<b>ʟɪᴠᴇs :</b> {lives_bar} ({game['lives']}/6)</blockquote>"
                )


async def stop_word_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id in ACTIVE_GAMES:
        del ACTIVE_GAMES[chat.id]
        if chat.id in GAME_TIMEOUT_TASKS:
            GAME_TIMEOUT_TASKS[chat.id].cancel()
        await update.message.reply_html("🛑 <b>Active word game ended!</b>")
    else:
        await update.message.reply_html("No word game is currently running in this chat.")


def register_handlers(app: Application):
    app.add_handler(CommandHandler(["words", "wordgames"], words_menu_command))
    app.add_handler(CommandHandler(["wordchain", "chain"], start_word_chain))
    app.add_handler(CommandHandler(["unscramble", "jumble"], start_unscramble))
    app.add_handler(CommandHandler(["emojiguess", "emoji"], start_emoji_guess))
    app.add_handler(CommandHandler("hangman", start_hangman))
    app.add_handler(CommandHandler("quiz", start_quiz))
    app.add_handler(CommandHandler("truth", truth_command))
    app.add_handler(CommandHandler("dare", dare_command))
    app.add_handler(CommandHandler(["stopword", "endword"], stop_word_game_command))

    # Callback queries for the interactive launcher
    app.add_handler(CallbackQueryHandler(start_word_chain, pattern=r"^wg_start_chain$"))
    app.add_handler(CallbackQueryHandler(start_unscramble, pattern=r"^wg_start_unscramble$"))
    app.add_handler(CallbackQueryHandler(start_emoji_guess, pattern=r"^wg_start_emoji$"))
    app.add_handler(CallbackQueryHandler(start_hangman, pattern=r"^wg_start_hangman$"))
    app.add_handler(CallbackQueryHandler(start_quiz, pattern=r"^wg_start_quiz$"))
    from KITTUBOT.plugins.wordseek import start_wordseek_command
    app.add_handler(CallbackQueryHandler(start_wordseek_command, pattern=r"^wg_start_wordseek$"))
    app.add_handler(CallbackQueryHandler(quiz_answer_callback, pattern=r"^quiz_ans_\d+_\d+$"))

    # Word game message listener
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_game_messages),
        group=15,
    )
