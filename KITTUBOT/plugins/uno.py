# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Multiplayer UNO Card Game Engine
Powered by the Official Telegram UNO Sticker Packs (@unocards)!
Features:
- Real card stickers sent to chat for top card and played cards
- Support for 4 deck themes: classic (@unocards), colorblind, minimalist, nomercy
- Action cards (+2, Skip, Reverse, Wild +4), interactive inline keyboards
- Private secret hand modal alerts, AFK turn timeouts & coin pots
"""

import os
import json
import random
import asyncio
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, User
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from KITTUBOT.database.users import ensure_user, update_balance
from KITTUBOT import log

__mod_name__ = "Uno"
__help__ = """
<blockquote>🃏 <b>ᴍᴜʟᴛɪᴘʟᴀʏᴇʀ ᴜɴᴏ ʜᴜʙ (@ᴜɴᴏᴄᴀʀᴅs):</b>
• <code>/uno [bet]</code> - sᴛᴀʀᴛ ᴀ ɢʀᴏᴜᴘ ᴜɴᴏ ʟᴏʙʙʏ (ᴍɪɴ 2, ᴍᴀx 6 ᴘʟᴀʏᴇʀs)
• <code>/unodeck [theme]</code> - sᴡɪᴛᴄʜ sᴛɪᴄᴋᴇʀ ᴘᴀᴄᴋ (classic, colorblind, minimalist, nomercy)
• <code>/enduno</code> - ᴄᴀɴᴄᴇʟ ᴄᴜʀʀᴇɴᴛ ᴜɴᴏ ɢᴀᴍᴇ
• <b>Rules:</b> Match color or number, play Action cards (+2, Skip, Reverse, Wild +4), 45s AFK timer, first to empty hand wins the pot!</blockquote>
"""

# Load all sticker decks from assets/cards/
CARDS_DIR = Path(__file__).resolve().parent.parent / "assets" / "cards"
THEMES: dict[str, dict] = {}

try:
    for filename in os.listdir(CARDS_DIR):
        if filename.endswith(".json"):
            theme_name = filename[:-5]
            with open(CARDS_DIR / filename, encoding="utf-8") as f:
                THEMES[theme_name] = json.load(f)
    log.info(f"Loaded {len(THEMES)} UNO card sticker themes: {list(THEMES.keys())}")
except Exception as e:
    log.error(f"Failed to load UNO card sticker decks: {e}")

DEFAULT_THEME = "classic"

COLORS = ["red", "blue", "green", "yellow"]
COLOR_EMOJIS = {
    "red": "🟥",
    "blue": "🟦",
    "green": "🟩",
    "yellow": "🟨",
    "wild": "🌈",
}

ACTIONS = ["skip", "reverse", "draw2"]


def get_card_sticker_id(theme: str, card: dict) -> str | None:
    """Resolves card to official Telegram sticker file_id from unocards pack."""
    c = card.get("color")
    v = card.get("val")

    if c == "wild":
        sticker_key = "draw_four" if v == "draw4" else "colorchooser"
    else:
        c_code = {"red": "r", "blue": "b", "green": "g", "yellow": "y"}.get(c, "r")
        v_code = "draw" if v == "draw2" else v
        sticker_key = f"{c_code}_{v_code}"

    deck_data = THEMES.get(theme) or THEMES.get(DEFAULT_THEME, {})
    return deck_data.get("STICKERS", {}).get(sticker_key)


def get_option_sticker_id(theme: str, option_name: str) -> str | None:
    """Fetches option stickers like option_draw, option_pass."""
    deck_data = THEMES.get(theme) or THEMES.get(DEFAULT_THEME, {})
    return deck_data.get("STICKERS", {}).get(f"option_{option_name}")


def generate_deck() -> list[dict]:
    """Generates a standard 108-card UNO deck."""
    deck = []
    for c in COLORS:
        # Zero card
        deck.append({"color": c, "val": "0"})
        # 1-9 twice
        for n in range(1, 10):
            deck.append({"color": c, "val": str(n)})
            deck.append({"color": c, "val": str(n)})
        # Action cards twice
        for act in ACTIONS:
            deck.append({"color": c, "val": act})
            deck.append({"color": c, "val": act})

    # Wild and Wild Draw 4 (4 of each)
    for _ in range(4):
        deck.append({"color": "wild", "val": "wild"})
        deck.append({"color": "wild", "val": "draw4"})

    random.shuffle(deck)
    return deck


def format_card(card: dict) -> str:
    """Formats a card into a human-readable string with emoji."""
    c = card["color"]
    v = card["val"]
    emoji = COLOR_EMOJIS.get(c, "🎴")

    val_display = {
        "skip": "🚫 Skip",
        "reverse": "🔄 Reverse",
        "draw2": "➕2 Draw",
        "wild": "🌈 Wild",
        "draw4": "🌈➕4 Wild",
    }.get(v, v)

    if c == "wild":
        return val_display
    return f"{emoji} {c.title()} {val_display}"


def format_card_button(card: dict) -> str:
    """Formats card for inline button with compact icons."""
    c = card["color"]
    v = card["val"]
    emoji = COLOR_EMOJIS.get(c, "🎴")

    val_display = {
        "skip": "🚫",
        "reverse": "🔄",
        "draw2": "+2",
        "wild": "🌈 Wild",
        "draw4": "🌈 +4",
    }.get(v, v)

    if c == "wild":
        return val_display
    return f"{emoji} {val_display}"


class UnoGameSession:
    def __init__(self, chat_id: int, host: User, bet: int = 0, theme: str = DEFAULT_THEME):
        self.chat_id = chat_id
        self.host = host
        self.bet = bet
        self.theme = theme if theme in THEMES else DEFAULT_THEME
        self.players: list[User] = [host]
        self.is_started = False
        self.deck = generate_deck()
        self.discard_pile: list[dict] = []
        self.hands: dict[int, list[dict]] = {}  # user_id -> [cards]
        self.current_idx = 0
        self.direction = 1  # 1 for clockwise, -1 for counter-clockwise
        self.active_color = "red"
        self.turn_timer_task = None
        self.lobby_timer_task = None
        self.board_message_id = None
        self.last_sticker_message_id = None
        self.consecutive_afk = 0
        self.last_status_note = ""


# Active games mapping: chat_id -> UnoGameSession
UNO_GAMES: dict[int, UnoGameSession] = {}


async def uno_lobby_timeout(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Auto-cancels an unstarted UNO lobby after 90s of inactivity to keep chat clean."""
    try:
        await asyncio.sleep(90)
        if chat_id in UNO_GAMES:
            game = UNO_GAMES[chat_id]
            if not game.is_started:
                del UNO_GAMES[chat_id]
                if game.board_message_id:
                    try:
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=game.board_message_id,
                            text="⌛ <b>ᴜɴᴏ ʟᴏʙʙʏ ᴇxᴘɪʀᴇᴅ</b>\n\n<blockquote>Lobby was auto-closed due to 90 seconds of inactivity.</blockquote>",
                            parse_mode="HTML",
                        )
                        await asyncio.sleep(6)
                        await context.bot.delete_message(chat_id=chat_id, message_id=game.board_message_id)
                    except Exception:
                        pass
    except asyncio.CancelledError:
        pass
    except Exception as e:
        log.debug(f"UNO lobby timeout exception: {e}")


async def uno_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        await update.message.reply_html("⚠️ <b>UNO is a multiplayer game!</b> Play it inside a Telegram group.")
        return

    if chat.id in UNO_GAMES:
        await update.message.reply_html("⚠️ <b>An UNO game is already active in this chat!</b>")
        return

    bet = 0
    theme = DEFAULT_THEME

    if context.args:
        for arg in context.args:
            if arg.isdigit():
                bet = int(arg)
            elif arg.lower() in THEMES:
                theme = arg.lower()

    if bet > 0:
        u_data = await ensure_user(user)
        if u_data.get("balance", 0) < bet:
            await update.message.reply_html(f"❌ You don't have enough coins for a <b>{bet:,}</b> bet!")
            return

    game = UnoGameSession(chat.id, user, bet, theme)
    UNO_GAMES[chat.id] = game

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🙋 ᴊᴏɪɴ ʟᴏʙʙʏ (1/6)", callback_data="uno_join"),
            InlineKeyboardButton("🏃 ʟᴇᴀᴠᴇ", callback_data="uno_leave"),
        ],
        [
            InlineKeyboardButton("▶️ sᴛᴀʀᴛ ɢᴀᴍᴇ", callback_data="uno_start"),
            InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="uno_cancel"),
        ]
    ])

    bet_text = f"💰 <b>ᴇɴᴛʀʏ ʙᴇᴛ :</b> <code>{bet:,} Coins</code>" if bet > 0 else "🎮 <b>ғʀᴇᴇ ғᴏʀ ғᴜɴ</b>"

    msg = await update.message.reply_html(
        "🃏 <b>ᴋɪᴛᴛᴜ ᴜɴᴏ ᴍᴜʟᴛɪᴘʟᴀʏᴇʀ ʟᴏʙʙʏ</b> ✨\n\n"
        f"<blockquote>👑 <b>ʜᴏsᴛ :</b> {user.mention_html()}\n"
        f"👥 <b>ᴘʟᴀʏᴇʀs :</b> 1 / 6\n"
        f"🎨 <b>sᴛɪᴄᴋᴇʀ ᴘᴀᴄᴋ :</b> <code>{theme.title()} (@unocards)</code>\n"
        f"{bet_text}</blockquote>\n\n"
        "🎋 <i>Click 'Join Lobby' to enter! Host can start with 2+ players (Auto-expires in 90s).</i>",
        reply_markup=keyboard,
    )
    game.board_message_id = msg.message_id
    game.lobby_timer_task = asyncio.create_task(uno_lobby_timeout(context, chat.id))


async def unodeck_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not context.args:
        available = ", ".join(f"<code>{t}</code>" for t in sorted(THEMES.keys()))
        await update.message.reply_html(
            f"🃏 <b>Available UNO Sticker Packs:</b>\n{available}\n\n"
            "<i>Usage: <code>/unodeck classic</code> (Official @unocards)</i>"
        )
        return

    choice = context.args[0].lower().strip()
    if choice not in THEMES:
        await update.message.reply_html(f"❌ Unknown deck theme! Choose from: <code>{', '.join(THEMES.keys())}</code>")
        return

    if chat.id in UNO_GAMES:
        game = UNO_GAMES[chat.id]
        if not game.is_started:
            game.theme = choice
            await update.message.reply_html(f"🎨 Switched lobby sticker pack to <b>{choice.title()}</b>!")
            return

    await update.message.reply_html(f"🎨 Default UNO sticker pack set to <b>{choice.title()}</b> for next game!")


async def uno_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in UNO_GAMES:
        try:
            await query.answer("This UNO lobby has expired or ended.", show_alert=True)
        except Exception:
            pass
        return

    game = UNO_GAMES[chat_id]
    if game.is_started:
        try:
            await query.answer("Game is already underway!", show_alert=True)
        except Exception:
            pass
        return

    if any(p.id == user.id for p in game.players):
        try:
            await query.answer("You are already in the lobby!", show_alert=True)
        except Exception:
            pass
        return

    if len(game.players) >= 6:
        try:
            await query.answer("Lobby is full! (Max 6 players)", show_alert=True)
        except Exception:
            pass
        return

    if game.bet > 0:
        u_data = await ensure_user(user)
        if u_data.get("balance", 0) < game.bet:
            try:
                await query.answer(f"You don't have {game.bet:,} coins to join this table!", show_alert=True)
            except Exception:
                pass
            return

    game.players.append(user)
    try:
        await query.answer(f"Joined lobby! ({len(game.players)}/6)")
    except Exception:
        pass

    await update_uno_lobby_message(query, game)


async def uno_leave_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in UNO_GAMES:
        try:
            await query.answer("No active UNO lobby here!", show_alert=True)
        except Exception:
            pass
        return

    game = UNO_GAMES[chat_id]
    if game.is_started:
        try:
            await query.answer("Cannot leave a game that has already started!", show_alert=True)
        except Exception:
            pass
        return

    if not any(p.id == user.id for p in game.players):
        try:
            await query.answer("You are not in the lobby!", show_alert=True)
        except Exception:
            pass
        return

    # If host leaves, cancel game
    if user.id == game.host.id:
        if game.lobby_timer_task:
            game.lobby_timer_task.cancel()
        del UNO_GAMES[chat_id]
        try:
            await query.answer("Host left! Lobby cancelled.", show_alert=True)
            await query.edit_message_text("🛑 <b>UNO lobby cancelled because the host left.</b>", parse_mode="HTML")
        except Exception:
            pass
        return

    # Remove non-host player
    game.players = [p for p in game.players if p.id != user.id]
    try:
        await query.answer("Left the UNO lobby.")
    except Exception:
        pass
    await update_uno_lobby_message(query, game)


async def update_uno_lobby_message(query, game: UnoGameSession):
    p_names = ", ".join(p.first_name for p in game.players)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"🙋 ᴊᴏɪɴ ʟᴏʙʙʏ ({len(game.players)}/6)", callback_data="uno_join"),
            InlineKeyboardButton("🏃 ʟᴇᴀᴠᴇ", callback_data="uno_leave"),
        ],
        [
            InlineKeyboardButton("▶️ sᴛᴀʀᴛ ɢᴀᴍᴇ", callback_data="uno_start"),
            InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="uno_cancel"),
        ]
    ])
    bet_text = f"💰 <b>ᴇɴᴛʀʏ ʙᴇᴛ :</b> <code>{game.bet:,} Coins</code>" if game.bet > 0 else "🎮 <b>ғʀᴇᴇ ғᴏʀ ғᴜɴ</b>"

    try:
        await query.edit_message_text(
            "🃏 <b>ᴋɪᴛᴛᴜ ᴜɴᴏ ᴍᴜʟᴛɪᴘʟᴀʏᴇʀ ʟᴏʙʙʏ</b> ✨\n\n"
            f"<blockquote>👑 <b>ʜᴏsᴛ :</b> {game.host.mention_html()}\n"
            f"👥 <b>ᴘʟᴀʏᴇʀs ({len(game.players)}/6):</b> <i>{p_names}</i>\n"
            f"🎨 <b>sᴛɪᴄᴋᴇʀ ᴘᴀᴄᴋ :</b> <code>{game.theme.title()} (@unocards)</code>\n"
            f"{bet_text}</blockquote>\n\n"
            "🎋 <i>Click 'Join Lobby' to enter! Host can start with 2+ players.</i>",
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except Exception:
        pass


async def uno_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in UNO_GAMES:
        return

    game = UNO_GAMES[chat_id]
    if user.id != game.host.id:
        try:
            await query.answer("Only the table host can start the game!", show_alert=True)
        except Exception:
            pass
        return

    if len(game.players) < 2:
        try:
            await query.answer("Need at least 2 players to start UNO!", show_alert=True)
        except Exception:
            pass
        return

    try:
        await query.answer("Dealing UNO card stickers...")
    except Exception:
        pass

    game.is_started = True
    if game.lobby_timer_task:
        game.lobby_timer_task.cancel()

    # Deduct bets if any
    if game.bet > 0:
        for p in game.players:
            await update_balance(p.id, -game.bet)

    # Deal 7 cards each
    for p in game.players:
        game.hands[p.id] = [game.deck.pop() for _ in range(7)]

    # Draw first non-wild card for top
    top_card = game.deck.pop()
    while top_card["color"] == "wild":
        game.deck.append(top_card)
        random.shuffle(game.deck)
        top_card = game.deck.pop()

    game.discard_pile.append(top_card)
    game.active_color = top_card["color"]

    # Delete lobby text message to clean up
    try:
        await query.delete_message()
    except Exception:
        pass

    # Send the first top card as an official Telegram sticker!
    top_sticker_id = get_card_sticker_id(game.theme, top_card)
    if top_sticker_id:
        try:
            stk_msg = await context.bot.send_sticker(chat_id=game.chat_id, sticker=top_sticker_id)
            game.last_sticker_message_id = stk_msg.message_id
        except Exception as e:
            log.warning(f"Failed to send initial UNO sticker: {e}")

    await render_game_board(None, context, game)


def is_card_playable(card: dict, top_card: dict, active_color: str) -> bool:
    """Checks if a card matches the active card/color."""
    if card["color"] == "wild":
        return True
    if card["color"] == active_color:
        return True
    if card["val"] == top_card["val"]:
        return True
    return False


async def render_game_board(update: Update, context: ContextTypes.DEFAULT_TYPE, game: UnoGameSession):
    """Renders the main UNO board in the chat with playable card buttons for active player."""
    # Ensure deck has cards
    if len(game.deck) < 5:
        top_keep = game.discard_pile[-1]
        reshuffled = game.discard_pile[:-1]
        random.shuffle(reshuffled)
        game.deck.extend(reshuffled)
        game.discard_pile = [top_keep]

    top = game.discard_pile[-1]
    top_color = game.active_color
    top_emoji = COLOR_EMOJIS.get(top_color, "🎴")
    cur_player = game.players[game.current_idx]
    hand = game.hands.get(cur_player.id, [])

    player_stats = []
    for p in game.players:
        count = len(game.hands.get(p.id, []))
        marker = "👉" if p.id == cur_player.id else "•"
        uno_badge = " 🔥 <b>[UNO!]</b>" if count == 1 else ""
        player_stats.append(f"{marker} {p.first_name}: <b>{count} cards</b>{uno_badge}")

    stats_str = "\n".join(player_stats)
    pot_str = f"\n💰 <b>ᴛᴏᴛᴀʟ ᴘᴏᴛ :</b> <code>{game.bet * len(game.players):,} Coins</code>" if game.bet > 0 else ""
    dir_str = "Clockwise ➡️" if game.direction == 1 else "Counter-Clockwise ⬅️"

    note_str = f"\n\n<blockquote>{game.last_status_note}</blockquote>" if game.last_status_note else ""

    text = (
        "🃏 <b>ᴋɪᴛᴛᴜ ᴜɴᴏ ᴛᴀʙʟᴇ</b> 🎮\n\n"
        f"<blockquote><b>ᴛᴏᴘ ᴄᴀʀᴅ :</b> {format_card(top)}\n"
        f"<b>ᴀᴄᴛɪᴠᴇ ᴄᴏʟᴏʀ :</b> {top_emoji} {top_color.upper()}\n"
        f"<b>ᴏʀᴅᴇʀ :</b> {dir_str}\n"
        f"<b>ᴄᴜʀʀᴇɴᴛ ᴛᴜʀɴ :</b> {cur_player.mention_html()}{pot_str}</blockquote>\n\n"
        f"<b>ᴘʟᴀʏᴇʀs :</b>\n{stats_str}{note_str}\n\n"
        f"🎋 <i>It's {cur_player.first_name}'s turn (45s)! Tap your card below or draw:</i>"
    )

    # Dynamic keyboard: shows active player's cards as compact buttons directly
    card_buttons = []
    for idx, c in enumerate(hand):
        playable = is_card_playable(c, top, game.active_color)
        btn_label = format_card_button(c)
        if not playable:
            btn_label = f"🔒 {btn_label}"
        card_buttons.append(
            InlineKeyboardButton(
                btn_label,
                callback_data=f"uno_c_{idx}" if playable else f"uno_locked_{idx}"
            )
        )

    # 3 cards per row for cleaner compact layout
    rows = [card_buttons[i : i + 3] for i in range(0, len(card_buttons), 3)]
    rows.append([
        InlineKeyboardButton("🃏 ᴅʀᴀᴡ ᴄᴀʀᴅ", callback_data="uno_draw"),
        InlineKeyboardButton("👀 ᴠɪᴇᴡ ᴍʏ ʜᴀɴᴅ (sᴇᴄʀᴇᴛ)", callback_data="uno_secret_hand"),
    ])
    rows.append([
        InlineKeyboardButton("❌ ᴇɴᴅ ɢᴀᴍᴇ", callback_data="uno_cancel"),
    ])

    keyboard = InlineKeyboardMarkup(rows)

    try:
        if game.board_message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=game.chat_id,
                    message_id=game.board_message_id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
            except Exception:
                # If editing failed, send fresh message
                msg = await context.bot.send_message(
                    chat_id=game.chat_id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
                game.board_message_id = msg.message_id
        else:
            msg = await context.bot.send_message(
                chat_id=game.chat_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            game.board_message_id = msg.message_id
    except Exception as e:
        log.warning(f"Error updating UNO game board: {e}")

    # Start 45s AFK timer
    if game.turn_timer_task:
        game.turn_timer_task.cancel()
    game.turn_timer_task = asyncio.create_task(uno_turn_timeout(context, game, cur_player.id))


async def uno_turn_timeout(context: ContextTypes.DEFAULT_TYPE, game: UnoGameSession, player_id: int):
    """Auto-draws and skips turn if player is AFK for 45s. Auto-ends game if all players are inactive."""
    try:
        await asyncio.sleep(45)
    except asyncio.CancelledError:
        return

    if game.chat_id not in UNO_GAMES:
        return

    cur_player = game.players[game.current_idx]
    if cur_player.id != player_id:
        return

    game.consecutive_afk += 1

    # Smart Auto-End: If players abandon the match (e.g. 2 full rounds inactive)
    max_afk = max(3, len(game.players) * 2)
    if game.consecutive_afk >= max_afk:
        del UNO_GAMES[game.chat_id]

        # Refund bets
        if game.bet > 0:
            for p in game.players:
                await update_balance(p.id, game.bet)

        # Delete last card sticker
        if game.last_sticker_message_id:
            try:
                await context.bot.delete_message(chat_id=game.chat_id, message_id=game.last_sticker_message_id)
            except Exception:
                pass

        refund_note = f"\nAll bets (<code>{game.bet:,} Coins</code> each) have been refunded! 🪙" if game.bet > 0 else ""
        end_text = (
            "💤 <b>ᴜɴᴏ ɢᴀᴍᴇ ᴀᴜᴛᴏ-ᴇɴᴅᴇᴅ (ᴀғᴋ)</b>\n\n"
            f"<blockquote>Players were inactive for too long. Match ended.{refund_note}</blockquote>"
        )
        if game.board_message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=game.chat_id,
                    message_id=game.board_message_id,
                    text=end_text,
                    parse_mode="HTML",
                )
                return
            except Exception:
                pass
        await context.bot.send_message(chat_id=game.chat_id, text=end_text, parse_mode="HTML")
        return

    # Auto draw
    if not game.deck:
        game.deck = generate_deck()
    drawn = game.deck.pop()
    game.hands[cur_player.id].append(drawn)
    game.current_idx = (game.current_idx + game.direction) % len(game.players)

    # Note on board instead of spamming separate messages into chat
    game.last_status_note = f"⏳ <i>{cur_player.first_name} timed out & auto-drew a card!</i>"
    await render_game_board(None, context, game)


async def uno_secret_hand_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pops up the user's private hand in a secure modal alert so no one else sees it."""
    query = update.callback_query
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in UNO_GAMES:
        return
    game = UNO_GAMES[chat_id]

    if user.id not in game.hands:
        try:
            await query.answer("You are not playing in this game!", show_alert=True)
        except Exception:
            pass
        return

    hand = game.hands[user.id]
    cards_str = "\n".join(f"• {format_card(c)}" for c in hand)
    alert_text = f"🎴 Your Secret Hand ({len(hand)} cards):\n\n{cards_str}"

    try:
        await query.answer(alert_text[:190], show_alert=True)
    except Exception:
        pass


async def uno_locked_card_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in UNO_GAMES:
        return
    game = UNO_GAMES[chat_id]
    cur_player = game.players[game.current_idx]

    if user.id != cur_player.id:
        try:
            await query.answer(f"⏳ It's {cur_player.first_name}'s turn!", show_alert=True)
        except Exception:
            pass
    else:
        try:
            await query.answer("🔒 That card doesn't match the active color or value! Draw or play another.", show_alert=True)
        except Exception:
            pass


async def uno_play_card_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles playing a valid card."""
    query = update.callback_query
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in UNO_GAMES:
        return

    game = UNO_GAMES[chat_id]
    cur_player = game.players[game.current_idx]
    if user.id != cur_player.id:
        try:
            await query.answer(f"⏳ It's {cur_player.first_name}'s turn right now!", show_alert=True)
        except Exception:
            pass
        return

    card_idx = int(query.data.split("_")[2])
    hand = game.hands.get(user.id, [])
    if card_idx >= len(hand):
        return

    card = hand[card_idx]

    # If Wild card, prompt for color selection
    if card["color"] == "wild":
        color_buttons = [
            [
                InlineKeyboardButton("🔴 ʀᴇᴅ", callback_data=f"uno_color_red_{card_idx}"),
                InlineKeyboardButton("🔵 ʙʟᴜᴇ", callback_data=f"uno_color_blue_{card_idx}"),
            ],
            [
                InlineKeyboardButton("🟢 ɢʀᴇᴇɴ", callback_data=f"uno_color_green_{card_idx}"),
                InlineKeyboardButton("🟡 ʏᴇʟʟᴏᴡ", callback_data=f"uno_color_yellow_{card_idx}"),
            ]
        ]
        try:
            await query.answer()
            await query.edit_message_text(
                f"🌈 <b>ʏᴏᴜ ᴘʟᴀʏᴇᴅ {format_card(card)}!</b>\n\n"
                "<blockquote>Choose the next active color for the table:</blockquote>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(color_buttons),
            )
        except Exception:
            pass
        return

    await execute_play_card(update, context, game, card_idx, chosen_color=card["color"])


async def uno_color_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = update.effective_chat.id
    parts = query.data.split("_")
    chosen_color = parts[2]
    card_idx = int(parts[3])

    if chat_id not in UNO_GAMES:
        return
    game = UNO_GAMES[chat_id]
    user = update.effective_user
    cur_player = game.players[game.current_idx]
    if user.id != cur_player.id:
        try:
            await query.answer("It's not your turn to choose the color!", show_alert=True)
        except Exception:
            pass
        return

    await execute_play_card(update, context, game, card_idx, chosen_color=chosen_color)


async def execute_play_card(update: Update, context: ContextTypes.DEFAULT_TYPE, game: UnoGameSession, card_idx: int, chosen_color: str):
    user = update.effective_user
    hand = game.hands.get(user.id, [])
    if card_idx >= len(hand):
        return
    card = hand.pop(card_idx)
    game.discard_pile.append(card)
    game.active_color = chosen_color

    # Cancel turn timer
    if game.turn_timer_task:
        game.turn_timer_task.cancel()

    # Send the card's official Telegram sticker to the chat!
    card_sticker_id = get_card_sticker_id(game.theme, card)
    if card_sticker_id:
        # Delete old top card sticker to keep the chat tidy
        if game.last_sticker_message_id:
            try:
                await context.bot.delete_message(chat_id=game.chat_id, message_id=game.last_sticker_message_id)
            except Exception:
                pass

        try:
            stk_msg = await context.bot.send_sticker(chat_id=game.chat_id, sticker=card_sticker_id)
            game.last_sticker_message_id = stk_msg.message_id
        except Exception as e:
            log.warning(f"Failed to send UNO played card sticker: {e}")

    # Reset AFK counter on active move
    game.consecutive_afk = 0
    game.last_status_note = ""

    # Check WIN CONDITION
    if len(hand) == 0:
        total_pot = game.bet * len(game.players)
        if total_pot > 0:
            await update_balance(user.id, total_pot)
            pot_text = f"🏆 <b>Prize Won:</b> <code>+{total_pot:,} Coins!</code> 🪙"
        else:
            pot_text = "🎉 <b>Champion of the table!</b>"

        del UNO_GAMES[game.chat_id]
        if game.last_sticker_message_id:
            try:
                await context.bot.delete_message(chat_id=game.chat_id, message_id=game.last_sticker_message_id)
            except Exception:
                pass

        win_text = (
            f"🎉 <b>ᴜɴᴏ! ᴡᴇ ʜᴀᴠᴇ ᴀ ᴡɪɴɴᴇʀ!</b> 🏆\n\n"
            f"<blockquote>👑 {user.mention_html()} played their final card <b>{format_card(card)}</b> and won the game!\n"
            f"{pot_text}</blockquote>\n\n"
            "🎋 <i>Type /uno to start another round!</i>"
        )
        if game.board_message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=game.chat_id,
                    message_id=game.board_message_id,
                    text=win_text,
                    parse_mode="HTML",
                )
                return
            except Exception:
                pass
        await context.bot.send_message(chat_id=game.chat_id, text=win_text, parse_mode="HTML")
        return

    # Shout UNO if 1 card left
    if len(hand) == 1:
        await context.bot.send_message(
            chat_id=game.chat_id,
            text=f"📢 <b>ᴜɴᴏ!</b> {user.mention_html()} has only <b>1 CARD</b> remaining! 🔥",
            parse_mode="HTML",
        )

    # Special Action Card Handlers
    num_players = len(game.players)
    advance_turns = 1

    if card["val"] == "reverse":
        if num_players == 2:
            advance_turns = 2
        else:
            game.direction *= -1
    elif card["val"] == "skip":
        advance_turns = 2
    elif card["val"] == "draw2":
        next_target_idx = (game.current_idx + game.direction) % num_players
        target_player = game.players[next_target_idx]
        for _ in range(2):
            if not game.deck:
                game.deck = generate_deck()
            game.hands[target_player.id].append(game.deck.pop())
        advance_turns = 2
    elif card["val"] == "draw4":
        next_target_idx = (game.current_idx + game.direction) % num_players
        target_player = game.players[next_target_idx]
        for _ in range(4):
            if not game.deck:
                game.deck = generate_deck()
            game.hands[target_player.id].append(game.deck.pop())
        advance_turns = 2

    # Advance turn index
    game.current_idx = (game.current_idx + (game.direction * advance_turns)) % num_players

    await render_game_board(update, context, game)


async def uno_draw_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in UNO_GAMES:
        return
    game = UNO_GAMES[chat_id]
    cur_player = game.players[game.current_idx]
    if user.id != cur_player.id:
        try:
            await query.answer(f"⏳ It's {cur_player.first_name}'s turn!", show_alert=True)
        except Exception:
            pass
        return

    if not game.deck:
        game.deck = generate_deck()

    drawn = game.deck.pop()
    game.hands[user.id].append(drawn)

    # Reset AFK counter on active draw
    game.consecutive_afk = 0
    game.last_status_note = ""

    # Pass turn
    game.current_idx = (game.current_idx + game.direction) % len(game.players)

    try:
        await query.answer(f"Drew {format_card(drawn)}! Turn passed.")
    except Exception:
        pass

    await render_game_board(update, context, game)


async def end_uno_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in UNO_GAMES:
        if update.callback_query:
            try:
                await update.callback_query.answer("No active UNO game.", show_alert=True)
            except Exception:
                pass
        else:
            await update.message.reply_html("No active UNO game in this chat.")
        return

    game = UNO_GAMES[chat_id]
    from KITTUBOT.config import config
    if user.id != game.host.id and user.id not in config.SUDO_IDS:
        if update.callback_query:
            try:
                await update.callback_query.answer("Only the host can cancel the game!", show_alert=True)
            except Exception:
                pass
        else:
            await update.message.reply_html("⚠️ Only the host can cancel the UNO game!")
        return

    if game.turn_timer_task:
        game.turn_timer_task.cancel()
    if game.lobby_timer_task:
        game.lobby_timer_task.cancel()

    # Refund bets if started
    if game.is_started and game.bet > 0:
        for p in game.players:
            await update_balance(p.id, game.bet)

    # Clean up last sticker if exists
    if game.last_sticker_message_id:
        try:
            await context.bot.delete_message(chat_id=game.chat_id, message_id=game.last_sticker_message_id)
        except Exception:
            pass

    del UNO_GAMES[chat_id]

    if update.callback_query:
        try:
            await update.callback_query.answer("Game cancelled!")
            await update.callback_query.edit_message_text("🛑 <b>UNO game was cancelled and bets refunded!</b>", parse_mode="HTML")
        except Exception:
            pass
    else:
        await update.message.reply_html("🛑 <b>UNO game was cancelled and bets refunded!</b>")


def register_handlers(app: Application):
    app.add_handler(CommandHandler("uno", uno_command))
    app.add_handler(CommandHandler(["unodeck", "unotheme"], unodeck_command))
    app.add_handler(CommandHandler(["enduno", "canceluno"], end_uno_command))
    app.add_handler(CallbackQueryHandler(uno_join_callback, pattern=r"^uno_join$"))
    app.add_handler(CallbackQueryHandler(uno_leave_callback, pattern=r"^uno_leave$"))
    app.add_handler(CallbackQueryHandler(uno_start_callback, pattern=r"^uno_start$"))
    app.add_handler(CallbackQueryHandler(uno_play_card_callback, pattern=r"^uno_c_\d+$"))
    app.add_handler(CallbackQueryHandler(uno_locked_card_callback, pattern=r"^uno_locked_\d+$"))
    app.add_handler(CallbackQueryHandler(uno_secret_hand_callback, pattern=r"^uno_secret_hand$"))
    app.add_handler(CallbackQueryHandler(uno_color_select_callback, pattern=r"^uno_color_\w+_\d+$"))
    app.add_handler(CallbackQueryHandler(uno_draw_callback, pattern=r"^uno_draw$"))
    app.add_handler(CallbackQueryHandler(end_uno_command, pattern=r"^uno_cancel$"))
