# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Multiplayer Hot Potato Bomb Game
High-stakes group elimination game with random fuse, pass mechanics, medals & cash pots.
"""

import random
import asyncio
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, User
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from KITTUBOT.database.users import (
    ensure_user,
    get_user,
    update_balance,
    set_user_dead,
    record_bomb_win,
    get_top_bomb_winners,
    get_user_bomb_rank,
)

__mod_name__ = "Bomb"
__help__ = """
<blockquote>💣 <b>ʜᴏᴛ ᴘᴏᴛᴀᴛᴏ ʙᴏᴍʙ ɢᴀᴍᴇ:</b>
• <code>/bomb [amount]</code> - sᴛᴀʀᴛ ᴀ ʙᴏᴍʙ ʟᴏʙʙʏ (ᴍɪɴ 100 ᴄᴏɪɴs)
• <code>/join</code> - ᴇɴᴛᴇʀ ᴛʜᴇ ʙᴏᴍʙ ɢᴀᴍᴇ
• <code>/pass</code> - ᴘᴀss ᴛɪᴄᴋɪɴɢ ʙᴏᴍʙ ᴛᴏ ᴀɴᴏᴛʜᴇʀ ᴘʟᴀʏᴇʀ
• <code>/bombleaders</code> - ᴠɪᴇᴡ ᴛᴏᴘ 10 ʙᴏᴍʙ ᴄʜᴀᴍᴘɪᴏɴs
• <code>/bombmyrank</code> - ᴄʜᴇᴄᴋ ʏᴏᴜʀ ʙᴏᴍʙ sᴜʀᴠɪᴠᴀʟ sᴛᴀᴛs
• <code>/bombcancel</code> - ᴄᴀɴᴄᴇʟ ɢᴀᴍᴇ & ʀᴇғᴜɴᴅ ᴘᴏᴛ</blockquote>
"""


class BombGame:
    def __init__(self, chat_id: int, host: User, bet: int):
        self.chat_id = chat_id
        self.host = host
        self.bet = bet
        self.players: list[User] = [host]
        self.active_players: list[User] = []
        self.current_holder: User = None
        self.is_started = False
        self.pot = bet
        self.timer_task = None
        self.board_msg_id = None
        self.round_num = 1
        self.created_at = time.time()
        self.last_pass_time = 0.0


# Active bomb games: chat_id -> BombGame
BOMB_GAMES: dict[int, BombGame] = {}


async def bomb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        await update.message.reply_html("⚠️ <b>Bomb is a multiplayer game!</b> Play it inside a group.")
        return

    if chat.id in BOMB_GAMES:
        existing = BOMB_GAMES[chat.id]
        # Auto-expire unstarted lobby older than 180s
        if not existing.is_started and (time.time() - existing.created_at) > 180:
            del BOMB_GAMES[chat.id]
        else:
            await update.message.reply_html("⚠️ <b>A bomb game is already active in this chat!</b>")
            return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_html("❗ <b>Usage:</b> <code>/bomb <amount></code> (e.g. <code>/bomb 500</code>)")
        return

    bet = int(context.args[0])
    if bet < 100:
        await update.message.reply_html("⚠️ Minimum bet is <b>100 Coins</b>!")
        return

    u_data = await ensure_user(user)
    if u_data.get("balance", 0) < bet:
        await update.message.reply_html(f"❌ You need <b>{bet:,} Coins</b> to start this game!")
        return

    game = BombGame(chat.id, user, bet)
    BOMB_GAMES[chat.id] = game

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💣 ᴊᴏɪɴ ʙᴏᴍʙ", callback_data="bomb_join"),
            InlineKeyboardButton("▶️ sᴛᴀʀᴛ ɢᴀᴍᴇ", callback_data="bomb_start"),
        ],
        [
            InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="bomb_cancel"),
        ]
    ])

    msg = await update.message.reply_html(
        "💣 <b>ᴋɪᴛᴛᴜ ʜᴏᴛ-ᴘᴏᴛᴀᴛᴏ ʙᴏᴍʙ ʟᴏʙʙʏ</b> ✨\n\n"
        f"<blockquote>👑 <b>ʜᴏsᴛ :</b> {user.mention_html()}\n"
        f"💰 <b>ᴇɴᴛʀʏ ʙᴇᴛ :</b> <code>{bet:,} Coins</code>\n"
        f"👥 <b>ᴘʟᴀʏᴇʀs :</b> 1\n"
        f"🏆 <b>ᴘʀɪᴢᴇ ᴘᴏᴛ :</b> <code>{bet:,} Coins</code></blockquote>\n\n"
        "🎋 <i>Click 'Join Bomb' or type /join! Host can start with 2+ players.</i>",
        reply_markup=keyboard,
    )
    game.board_msg_id = msg.message_id


async def join_bomb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in BOMB_GAMES:
        if update.callback_query:
            try:
                await update.callback_query.answer("No active bomb lobby here!", show_alert=True)
            except Exception:
                pass
        return

    game = BOMB_GAMES[chat_id]
    if game.is_started:
        if update.callback_query:
            try:
                await update.callback_query.answer("Game already started!", show_alert=True)
            except Exception:
                pass
        return

    if any(p.id == user.id for p in game.players):
        if update.callback_query:
            try:
                await update.callback_query.answer("You are already in the game!", show_alert=True)
            except Exception:
                pass
        return

    u_data = await ensure_user(user)
    if u_data.get("balance", 0) < game.bet:
        if update.callback_query:
            try:
                await update.callback_query.answer(f"You need {game.bet:,} coins to join!", show_alert=True)
            except Exception:
                pass
        else:
            await update.message.reply_html(f"❌ You need <b>{game.bet:,} Coins</b> to enter!")
        return

    game.players.append(user)
    game.pot += game.bet

    if update.callback_query:
        try:
            await update.callback_query.answer("Joined the bomb game! 💣")
        except Exception:
            pass

    p_list = ", ".join(p.first_name for p in game.players)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"💣 ᴊᴏɪɴ ʙᴏᴍʙ ({len(game.players)})", callback_data="bomb_join"),
            InlineKeyboardButton("▶️ sᴛᴀʀᴛ ɢᴀᴍᴇ", callback_data="bomb_start"),
        ],
        [
            InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="bomb_cancel"),
        ]
    ])

    text = (
        "💣 <b>ᴋɪᴛᴛᴜ ʜᴏᴛ-ᴘᴏᴛᴀᴛᴏ ʙᴏᴍʙ ʟᴏʙʙʏ</b> ✨\n\n"
        f"<blockquote>👑 <b>ʜᴏsᴛ :</b> {game.host.mention_html()}\n"
        f"💰 <b>ᴇɴᴛʀʏ ʙᴇᴛ :</b> <code>{game.bet:,} Coins</code>\n"
        f"👥 <b>ᴘʟᴀʏᴇʀs ({len(game.players)}):</b> <i>{p_list}</i>\n"
        f"🏆 <b>ᴘʀɪᴢᴇ ᴘᴏᴛ :</b> <code>{game.pot:,} Coins</code></blockquote>\n\n"
        "🎋 <i>Host can press 'Start Game' to ignite the fuse!</i>"
    )

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
        except Exception:
            pass
    else:
        await update.message.reply_html(f"💣 {user.mention_html()} joined the bomb match! Pot is now <b>{game.pot:,} Coins</b>!")


async def start_bomb_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in BOMB_GAMES:
        return
    game = BOMB_GAMES[chat_id]

    if user.id != game.host.id:
        try:
            await query.answer("Only the host can start the game!", show_alert=True)
        except Exception:
            pass
        return

    if len(game.players) < 2:
        try:
            await query.answer("Need at least 2 players to start!", show_alert=True)
        except Exception:
            pass
        return

    try:
        await query.answer("Igniting the bomb! 🔥")
    except Exception:
        pass

    # Deduct bets
    for p in game.players:
        await update_balance(p.id, -game.bet)

    game.is_started = True
    game.active_players = list(game.players)
    game.current_holder = random.choice(game.active_players)

    await start_bomb_round(context, game)


async def start_bomb_round(context: ContextTypes.DEFAULT_TYPE, game: BombGame):
    """Starts a ticking round with a random countdown."""
    fuse_seconds = random.randint(12, 28)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏃 ᴘᴀss ʙᴏᴍʙ!", callback_data="bomb_pass")]
    ])

    p_list = ", ".join(p.first_name for p in game.active_players)

    await context.bot.send_message(
        chat_id=game.chat_id,
        text=(
            f"💣 <b>ʀᴏᴜɴᴅ {game.round_num} — ᴛʜᴇ ғᴜsᴇ ɪs ʟɪᴛ!</b> 🔥\n\n"
            f"<blockquote>⚡ <b>ʙᴏᴍʙ ʜᴏʟᴅᴇʀ :</b> {game.current_holder.mention_html()}\n"
            f"👥 <b>sᴜʀᴠɪᴠᴏʀs :</b> <i>{p_list}</i>\n"
            f"🏆 <b>ᴛᴏᴛᴀʟ ᴘᴏᴛ :</b> <code>{game.pot:,} Coins</code></blockquote>\n\n"
            f"🎋 <i>Quick! {game.current_holder.first_name}, pass the bomb with /pass or hit the button!</i>"
        ),
        parse_mode="HTML",
        reply_markup=keyboard,
    )

    if game.timer_task:
        game.timer_task.cancel()
    game.timer_task = asyncio.create_task(bomb_timer(context, game, fuse_seconds))


async def bomb_timer(context: ContextTypes.DEFAULT_TYPE, game: BombGame, duration: int):
    """Timer counting down until explosion."""
    await asyncio.sleep(duration)

    if game.chat_id not in BOMB_GAMES:
        return

    victim = game.current_holder
    # BOOM!
    await set_user_dead(victim.id, True)
    game.active_players = [p for p in game.active_players if p.id != victim.id]

    await context.bot.send_message(
        chat_id=game.chat_id,
        text=(
            "💥 <b>ᴋᴀ-ʙᴏᴏᴏᴏᴏᴏᴍ!</b> 💣💥💥\n\n"
            f"<blockquote>☠️ <b>{victim.mention_html()}</b> was holding the bomb when it detonated!\n"
            f"<i>They have been eliminated from the game!</i></blockquote>"
        ),
        parse_mode="HTML",
    )

    # Check WINNER
    if len(game.active_players) == 1:
        winner = game.active_players[0]
        await record_bomb_win(winner.id, game.pot)
        del BOMB_GAMES[game.chat_id]

        await context.bot.send_message(
            chat_id=game.chat_id,
            text=(
                "🏆 <b>ʙᴏᴍʙ sᴜʀᴠɪᴠᴏʀ ᴄʜᴀᴍᴘɪᴏɴ!</b> 🎉\n\n"
                f"<blockquote>👑 {winner.mention_html()} outlasted everyone and won the match!\n"
                f"💰 <b>ᴘʀɪᴢᴇ ᴘᴏᴛ :</b> <code>+{game.pot:,} Coins!</code> 🪙\n"
                f"🏅 <b>ʙᴏᴍʙ ᴡɪɴs :</b> Added to leaderboard!</blockquote>\n\n"
                "🎋 <i>Type /bomb to start another high-stakes round!</i>"
            ),
            parse_mode="HTML",
        )
    else:
        # Next round
        game.round_num += 1
        game.current_holder = random.choice(game.active_players)
        await asyncio.sleep(2)
        await start_bomb_round(context, game)


async def pass_bomb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in BOMB_GAMES:
        if update.callback_query:
            try:
                await update.callback_query.answer("No active bomb game!", show_alert=True)
            except Exception:
                pass
        return

    game = BOMB_GAMES[chat_id]
    if not game.is_started:
        return

    if user.id != game.current_holder.id:
        if update.callback_query:
            try:
                await update.callback_query.answer("🙄 You don't have the bomb!", show_alert=True)
            except Exception:
                pass
        else:
            await update.message.reply_html("🙄 <b>You don't have the bomb!</b> Only the holder can pass!")
        return

    # Anti-spam cooldown of 0.8s
    now = time.time()
    if now - getattr(game, "last_pass_time", 0) < 0.8:
        if update.callback_query:
            try:
                await update.callback_query.answer("🔥 Too hot! Wait a second!", show_alert=False)
            except Exception:
                pass
        return
    game.last_pass_time = now

    # Pass to a random other alive player
    candidates = [p for p in game.active_players if p.id != user.id]
    if not candidates:
        return

    new_holder = random.choice(candidates)
    game.current_holder = new_holder

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏃 ᴘᴀss ʙᴏᴍʙ!", callback_data="bomb_pass")]
    ])

    if update.callback_query:
        try:
            await update.callback_query.answer(f"Passed to {new_holder.first_name}!")
        except Exception:
            pass

    await context.bot.send_message(
        chat_id=game.chat_id,
        text=(
            f"💨 <b>ʙᴏᴍʙ ᴘᴀssᴇᴅ!</b>\n\n"
            f"<blockquote>{user.mention_html()} threw the bomb to 👉 {new_holder.mention_html()}!\n"
            f"⏳ <i>The fuse is still burning! Pass it quick!</i></blockquote>"
        ),
        parse_mode="HTML",
        reply_markup=keyboard,
    )


async def bomb_cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in BOMB_GAMES:
        if update.callback_query:
            try:
                await update.callback_query.answer("No active game to cancel.", show_alert=True)
            except Exception:
                pass
        return

    game = BOMB_GAMES[chat_id]
    from KITTUBOT.config import config
    if user.id != game.host.id and user.id not in config.SUDO_IDS:
        if update.callback_query:
            try:
                await update.callback_query.answer("Only the host or sudo can cancel!", show_alert=True)
            except Exception:
                pass
        return

    if game.timer_task:
        game.timer_task.cancel()

    # Refund if game was started
    if game.is_started:
        for p in game.active_players:
            await update_balance(p.id, game.bet)

    del BOMB_GAMES[chat_id]

    if update.callback_query:
        try:
            await update.callback_query.answer("Game cancelled!")
            await update.callback_query.edit_message_text("🛑 <b>Bomb game was cancelled and bets refunded!</b>", parse_mode="HTML")
        except Exception:
            pass
    else:
        await update.message.reply_html("🛑 <b>Bomb game was cancelled and bets refunded!</b>")


async def bomb_leaders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top_winners = await get_top_bomb_winners(limit=10)
    if not top_winners:
        await update.message.reply_html("No bomb survivors recorded yet.")
        return

    text = "💣 <b>ᴋɪᴛᴛᴜ ʙᴏᴍʙ ʜᴀʟʟ ᴏғ ғᴀᴍᴇ</b> 🏆\n\n<blockquote>"
    for idx, u in enumerate(top_winners, start=1):
        name = u.get("first_name", "Unknown")
        wins = u.get("bomb_wins", 0)
        medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
        text += f"{medal} <b>{name}</b> — <code>{wins} Wins</code>\n"
    text += "</blockquote>"

    await update.message.reply_html(text)


async def bomb_myrank_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    rank, wins = await get_user_bomb_rank(user.id)

    await update.message.reply_html(
        f"💣 <b>{user.mention_html()}'s ʙᴏᴍʙ sᴛᴀᴛs:</b>\n\n"
        f"<blockquote>🏆 <b>ʙᴏᴍʙ ᴡɪɴs :</b> <code>{wins}</code>\n"
        f"🎖️ <b>ɢʟᴏʙᴀʟ ʀᴀɴᴋ :</b> <code>#{rank}</code></blockquote>"
    )


def register_handlers(app: Application):
    app.add_handler(CommandHandler("bomb", bomb_command))
    app.add_handler(CommandHandler("join", join_bomb))
    app.add_handler(CommandHandler("pass", pass_bomb_command))
    app.add_handler(CommandHandler(["bombcancel", "cancelbomb"], bomb_cancel_command))
    app.add_handler(CommandHandler(["bombleaders", "bombtop"], bomb_leaders_command))
    app.add_handler(CommandHandler(["bombmyrank", "bombrank"], bomb_myrank_command))

    # Callback handlers
    app.add_handler(CallbackQueryHandler(join_bomb, pattern=r"^bomb_join$"))
    app.add_handler(CallbackQueryHandler(start_bomb_callback, pattern=r"^bomb_start$"))
    app.add_handler(CallbackQueryHandler(pass_bomb_command, pattern=r"^bomb_pass$"))
    app.add_handler(CallbackQueryHandler(bomb_cancel_command, pattern=r"^bomb_cancel$"))
