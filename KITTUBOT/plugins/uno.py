# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Multiplayer UNO Card Game Engine
Powered by the Official Telegram UNO Sticker Packs (@unocards)!
Features:
- Authentic Telegram Inline Mode gameplay matching @play_unobot
- Tap "Make your choice! ↗️" to open your live hand in the Telegram inline sticker tray
- Playable cards appear in full color; unplayable cards are greyed out (STICKERS_GREY)
- Played sticker becomes the new top card; old stickers auto-cleaned to prevent GC clutter
- Wild color picker, Action cards (+2, Skip, Reverse, Wild +4), 45s AFK timer, coin pots
- Secret Hand popup modal alert and optional Button Controls toggle
"""

import os
import json
import base64
import random
import asyncio
from pathlib import Path
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultCachedSticker,
    User,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
    ChosenInlineResultHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from KITTUBOT.database.users import ensure_user, update_balance
from KITTUBOT import log

__mod_name__ = "Uno"
__help__ = """
<blockquote>🃏 <b>ᴍᴜʟᴛɪᴘʟᴀʏᴇʀ ᴜɴᴏ ʜᴜʙ (@ᴜɴᴏᴄᴀʀᴅs):</b>
• <code>/uno [bet]</code> - sᴛᴀʀᴛ ᴀ ɢʀᴏᴜᴘ ᴜɴᴏ ʟᴏʙʙʏ (ᴍɪɴ 2, ᴍᴀx 6 ᴘʟᴀʏᴇʀs)
• <code>/close</code> - sᴛᴀʀᴛ ᴛʜᴇ ɢᴀᴍᴇ & sᴛᴏᴘ ᴘᴇᴏᴘʟᴇ ғʀᴏᴍ ᴊᴏɪɴɪɴɢ
• <code>/unodeck [theme]</code> - sᴡɪᴛᴄʜ sᴛɪᴄᴋᴇʀ ᴘᴀᴄᴋ (classic, colorblind, minimalist, nomercy)
• <code>/enduno</code> - ᴄᴀɴᴄᴇʟ ᴄᴜʀʀᴇɴᴛ ᴜɴᴏ ɢᴀᴍᴇ
• <b>Gameplay:</b> Tap <i>"Make your choice! ↗️"</i> to pick your card from the Telegram sticker tray! First to empty hand wins the pot!</blockquote>
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


def get_unique_payload(fid_str: str) -> bytes:
    """Extracts internal MTProto document identifier payload from a Telegram file_id."""
    try:
        pad = len(fid_str) % 4
        if pad:
            fid_str += "=" * (4 - pad)
        raw = base64.urlsafe_b64decode(fid_str)
        if len(raw) >= 19:
            return raw[-19:-2]
        return raw
    except Exception:
        return fid_str.encode("utf-8")


# Precompute sticker payload lookup tables for instant 0ms recognition
THEME_PAYLOADS: dict[str, dict[str, dict[bytes, str]]] = {}
for theme_name, tdata in THEMES.items():
    THEME_PAYLOADS[theme_name] = {"STICKERS": {}, "STICKERS_GREY": {}}
    for k, fid in tdata.get("STICKERS", {}).items():
        THEME_PAYLOADS[theme_name]["STICKERS"][get_unique_payload(fid)] = k
    for k, fid in tdata.get("STICKERS_GREY", {}).items():
        THEME_PAYLOADS[theme_name]["STICKERS_GREY"][get_unique_payload(fid)] = k


def resolve_sticker_key(theme: str, file_id: str) -> tuple[str | None, bool]:
    """
    Resolves any Telegram sticker file_id (static or incoming dynamic)
    to its card key (e.g. 'b_0', 'option_draw', etc.) and whether it's grey.
    Returns: (card_key, is_grey)
    """
    payload = get_unique_payload(file_id)
    t_payloads = THEME_PAYLOADS.get(theme) or THEME_PAYLOADS.get(DEFAULT_THEME, {})

    # 1. Match against active theme
    if payload in t_payloads.get("STICKERS", {}):
        return t_payloads["STICKERS"][payload], False
    if payload in t_payloads.get("STICKERS_GREY", {}):
        return t_payloads["STICKERS_GREY"][payload], True

    # 2. Check across other themes in case of cross-theme sticker
    for t_name, maps in THEME_PAYLOADS.items():
        if payload in maps.get("STICKERS", {}):
            return maps["STICKERS"][payload], False
        if payload in maps.get("STICKERS_GREY", {}):
            return maps["STICKERS_GREY"][payload], True

    # 3. Direct string match fallback
    deck_data = THEMES.get(theme) or THEMES.get(DEFAULT_THEME, {})
    for k, fid in deck_data.get("STICKERS", {}).items():
        if fid == file_id:
            return k, False
    for k, fid in deck_data.get("STICKERS_GREY", {}).items():
        if fid == file_id:
            return k, True

    return None, False


COLORS = ["red", "blue", "green", "yellow"]
COLOR_EMOJIS = {
    "red": "🟥",
    "blue": "🟦",
    "green": "🟩",
    "yellow": "🟨",
    "wild": "🌈",
}

ACTIONS = ["skip", "reverse", "draw2"]


def get_card_key(card: dict) -> str:
    """Calculates key in STICKERS / STICKERS_GREY dictionary."""
    c = card.get("color")
    v = card.get("val")

    if c == "wild":
        return "draw_four" if v == "draw4" else "colorchooser"

    c_code = {"red": "r", "blue": "b", "green": "g", "yellow": "y"}.get(c, "r")
    v_code = "draw" if v == "draw2" else v
    return f"{c_code}_{v_code}"


def get_card_sticker_id(theme: str, card: dict) -> str | None:
    """Resolves card to official Telegram sticker file_id from unocards pack."""
    k = get_card_key(card)
    deck_data = THEMES.get(theme) or THEMES.get(DEFAULT_THEME, {})
    return deck_data.get("STICKERS", {}).get(k)


def get_card_grey_sticker_id(theme: str, card: dict) -> str | None:
    """Resolves card to dimmed/monochrome sticker file_id for unplayable cards."""
    k = get_card_key(card)
    deck_data = THEMES.get(theme) or THEMES.get(DEFAULT_THEME, {})
    grey_dict = deck_data.get("STICKERS_GREY", {})
    if k in grey_dict:
        return grey_dict[k]
    return deck_data.get("STICKERS", {}).get(k)


def get_option_sticker_id(theme: str, option_name: str) -> str | None:
    """Fetches option stickers like option_draw, option_pass, option_info."""
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
    c = card.get("color")
    v = card.get("val")
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
    c = card.get("color")
    v = card.get("val")
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


def is_card_playable(card: dict, top_card: dict, active_color: str) -> bool:
    """Checks if a card matches the active card/color according to UNO rules."""
    if card.get("color") == "wild":
        return True
    if card.get("color") == active_color:
        return True
    if card.get("val") == top_card.get("val"):
        return True
    return False


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
        self.turn_timer_task: asyncio.Task | None = None
        self.lobby_timer_task: asyncio.Task | None = None
        self.lobby_message_id: int | None = None
        self.board_message_id: int | None = None
        self.last_sticker_message_id: int | None = None
        self.consecutive_afk = 0
        self.last_status_note = ""
        self.has_drawn_this_turn = False
        self.pending_wild_player_id: int | None = None
        self.pending_wild_card: dict | None = None
        self.button_mode = False
        self.turn_number = 0


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
                msg_id = game.lobby_message_id or game.board_message_id
                if msg_id:
                    try:
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=msg_id,
                            text="⌛ <b>ᴜɴᴏ ʟᴏʙʙʏ ᴇxᴘɪʀᴇᴅ</b>\n\n<blockquote>Lobby was auto-closed due to 90 seconds of inactivity.</blockquote>",
                            parse_mode="HTML",
                        )
                        await asyncio.sleep(5)
                        await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
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
        "🎋 <i>Click 'Join Lobby' to enter! Host can tap 'Start Game' or type /close to deal cards (Auto-expires in 90s).</i>",
        reply_markup=keyboard,
    )
    game.lobby_message_id = msg.message_id
    game.lobby_timer_task = asyncio.create_task(uno_lobby_timeout(context, chat.id))


async def close_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Implements /close command matching @play_unobot:
    Stops people from joining the game and immediately deals cards to start!
    """
    chat = update.effective_chat
    user = update.effective_user

    if chat.id not in UNO_GAMES:
        await update.message.reply_html("⚠️ No active UNO lobby in this chat. Start one with <code>/uno</code>!")
        return

    game = UNO_GAMES[chat.id]
    if game.is_started:
        await update.message.reply_html("⚠️ The UNO game is already underway! Use <code>/enduno</code> to cancel.")
        return

    from KITTUBOT.config import config
    if user.id != game.host.id and user.id not in config.SUDO_IDS:
        await update.message.reply_html("⚠️ Only the table host can use <code>/close</code> to start the game!")
        return

    if len(game.players) < 2:
        await update.message.reply_html("⚠️ Need at least 2 players in the lobby to start UNO!")
        return

    await start_uno_game(context, game)


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
            "🎋 <i>Click 'Join Lobby' to enter! Host can tap 'Start Game' or type /close to deal cards.</i>",
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
        await query.answer("Dealing cards...")
    except Exception:
        pass

    await start_uno_game(context, game)


async def start_uno_game(context: ContextTypes.DEFAULT_TYPE, game: UnoGameSession):
    """Initializes the cards, deletes the lobby message, sends first top sticker, and opens the board."""
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

    # Draw first top card (ensure non-action, non-wild number card 0-9)
    top_card = game.deck.pop()
    while top_card["color"] == "wild" or top_card["val"] in ACTIONS:
        game.deck.append(top_card)
        random.shuffle(game.deck)
        top_card = game.deck.pop()

    game.discard_pile.append(top_card)
    game.active_color = top_card["color"]

    # Delete lobby message to keep chat tidy
    msg_id = game.lobby_message_id
    if msg_id:
        try:
            await context.bot.edit_message_reply_markup(chat_id=game.chat_id, message_id=msg_id, reply_markup=None)
        except Exception:
            pass
        try:
            await context.bot.delete_message(chat_id=game.chat_id, message_id=msg_id)
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

    await render_game_board(None, context, game, is_first_turn=True, send_new=True)


async def render_game_board(
    update: Update | None,
    context: ContextTypes.DEFAULT_TYPE,
    game: UnoGameSession,
    is_first_turn: bool = False,
    send_new: bool = False,
):
    """
    Renders the UNO game status directly beneath the top sticker.
    Matches the official @play_unobot layout with:
    - Current player mention & username
    - Prominent 'Make your choice! ↗️' inline button
    - Optional secret hand view & end game controls
    """
    # Reshuffle if deck is low
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

    cur_username = f" (@{cur_player.username})" if cur_player.username else ""

    if is_first_turn:
        # Matches official Screenshot 1:
        text = (
            f"<b>First player:</b> {cur_player.mention_html()}{cur_username}\n"
            "Use /close to stop people from joining the game.\n\n"
            f"<b>Active Card :</b> {format_card(top)} ({top_emoji} {top_color.upper()})\n"
            f"<b>Direction :</b> {dir_str}\n\n"
            f"<b>Players :</b>\n{stats_str}{pot_str}{note_str}"
        )
    else:
        text = (
            f"<b>Current player:</b> {cur_player.mention_html()}{cur_username}\n\n"
            f"<b>Active Card :</b> {format_card(top)} ({top_emoji} {top_color.upper()})\n"
            f"<b>Direction :</b> {dir_str}\n\n"
            f"<b>Players :</b>\n{stats_str}{pot_str}{note_str}\n\n"
            f"🎋 <i>It's {cur_player.first_name}'s turn (45s)! Tap 'Make your choice!' below:</i>"
        )

    # Build Keyboard
    if not game.button_mode:
        # Default: Pure Authentic @play_unobot Inline Mode
        keyboard_rows = [
            [
                InlineKeyboardButton("Make your choice! ↗️", switch_inline_query_current_chat="")
            ],
            [
                InlineKeyboardButton("🎴 View Hand", callback_data="uno_secret_hand"),
                InlineKeyboardButton("🎛️ Button Mode", callback_data="uno_toggle_buttons"),
            ],
            [
                InlineKeyboardButton("❌ End Game", callback_data="uno_cancel"),
            ]
        ]
    else:
        # Optional Button Controls fallback
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
        keyboard_rows = [card_buttons[i : i + 3] for i in range(0, len(card_buttons), 3)]
        keyboard_rows.append([
            InlineKeyboardButton("🃏 Draw Card", callback_data="uno_draw"),
            InlineKeyboardButton("🎴 View Hand", callback_data="uno_secret_hand"),
        ])
        keyboard_rows.append([
            InlineKeyboardButton("🔄 Switch to Inline Mode ↗️", callback_data="uno_toggle_buttons"),
            InlineKeyboardButton("❌ End Game", callback_data="uno_cancel"),
        ])

    keyboard = InlineKeyboardMarkup(keyboard_rows)

    try:
        if send_new:
            # Delete old board message if present to place new board cleanly beneath latest sticker
            if game.board_message_id:
                try:
                    await context.bot.edit_message_reply_markup(
                        chat_id=game.chat_id, message_id=game.board_message_id, reply_markup=None
                    )
                except Exception:
                    pass
                try:
                    await context.bot.delete_message(chat_id=game.chat_id, message_id=game.board_message_id)
                except Exception:
                    pass
            msg = await context.bot.send_message(
                chat_id=game.chat_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            game.board_message_id = msg.message_id
        else:
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
        log.warning(f"Error rendering UNO game board: {e}")

    # Start 45s AFK timer
    if game.turn_timer_task:
        game.turn_timer_task.cancel()
    game.turn_timer_task = asyncio.create_task(uno_turn_timeout(context, game, cur_player.id))


async def uno_inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles inline queries triggered by 'Make your choice! ↗️'.
    Displays the player's hand in Telegram's sticker popup tray:
    - Item 0: option_draw (or option_pass if card already drawn)
    - Items 1..N: Playable cards in full color; unplayable cards greyed out
    - Item Last: option_info (?)
    """
    inline_query = update.inline_query
    if not inline_query:
        return

    user = inline_query.from_user

    # Find the active game for this user
    active_game = None
    # Priority: game where it is CURRENTLY this user's turn
    for g in UNO_GAMES.values():
        if g.is_started and g.players[g.current_idx].id == user.id:
            active_game = g
            break

    # Fallback: any active game user is participating in
    if not active_game:
        for g in UNO_GAMES.values():
            if g.is_started and any(p.id == user.id for p in g.players):
                active_game = g
                break

    deck_data = THEMES.get(active_game.theme if active_game else DEFAULT_THEME) or THEMES.get(DEFAULT_THEME, {})
    stickers_norm = deck_data.get("STICKERS", {})
    stickers_grey = deck_data.get("STICKERS_GREY", {})

    if not active_game:
        info_stk = stickers_norm.get("option_info")
        results = []
        if info_stk:
            results.append(
                InlineQueryResultCachedSticker(
                    id="uno_no_game",
                    sticker_file_id=info_stk,
                )
            )
        await inline_query.answer(results, cache_time=0, is_personal=True)
        return

    is_turn = (active_game.players[active_game.current_idx].id == user.id)
    hand = active_game.hands.get(user.id, [])
    top_card = active_game.discard_pile[-1] if active_game.discard_pile else {"color": "red", "val": "0"}
    active_color = active_game.active_color

    results = []

    # 1. Action Option (Draw or Pass)
    if is_turn:
        if active_game.has_drawn_this_turn:
            pass_stk = stickers_norm.get("option_pass")
            if pass_stk:
                results.append(
                    InlineQueryResultCachedSticker(
                        id=f"uno_pass_{active_game.chat_id}_{random.randint(100, 999)}",
                        sticker_file_id=pass_stk,
                    )
                )
        else:
            draw_stk = stickers_norm.get("option_draw")
            if draw_stk:
                results.append(
                    InlineQueryResultCachedSticker(
                        id=f"uno_draw_{active_game.chat_id}_{random.randint(100, 999)}",
                        sticker_file_id=draw_stk,
                    )
                )

    # 2. Player Hand Cards (Colored if playable, Grey if unplayable)
    for idx, card in enumerate(hand):
        k = get_card_key(card)
        playable = is_turn and is_card_playable(card, top_card, active_color)
        if playable:
            stk_id = stickers_norm.get(k)
        else:
            stk_id = stickers_grey.get(k) or stickers_norm.get(k)

        if stk_id:
            results.append(
                InlineQueryResultCachedSticker(
                    id=f"uno_c_{active_game.chat_id}_{idx}_{k}_{random.randint(100, 999)}",
                    sticker_file_id=stk_id,
                )
            )

    # 3. Info / Help Option (?)
    info_stk = stickers_norm.get("option_info")
    if info_stk:
        results.append(
            InlineQueryResultCachedSticker(
                id=f"uno_info_{active_game.chat_id}_{random.randint(100, 999)}",
                sticker_file_id=info_stk,
            )
        )

    # Telegram limits inline queries to max 50 items
    await inline_query.answer(results[:50], cache_time=0, is_personal=True)


async def uno_via_bot_sticker_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Catches stickers sent into the chat via inline mode.
    This executes the card play directly:
    - If option_draw: draws a card
    - If option_pass: passes turn
    - If unplayable card: warns player & deletes sticker
    - If playable card: becomes the new top sticker, deletes previous sticker, advances game!
    """
    msg = update.effective_message
    if not msg or not msg.sticker or not msg.via_bot:
        return

    # Ensure this sticker was sent through our bot
    if msg.via_bot.id != context.bot.id:
        return

    chat_id = msg.chat.id
    if chat_id not in UNO_GAMES:
        return

    game = UNO_GAMES[chat_id]
    if not game.is_started:
        return

    user = msg.from_user
    cur_player = game.players[game.current_idx]

    # Verify if it is this player's turn
    if user.id != cur_player.id:
        try:
            await msg.delete()
        except Exception:
            pass
        return

    card_key, is_grey_card = resolve_sticker_key(game.theme, msg.sticker.file_id)
    if not card_key:
        try:
            await msg.delete()
        except Exception:
            pass
        return

    # Check if option_draw was tapped
    if card_key == "option_draw":
        try:
            await msg.delete()
        except Exception:
            pass
        await execute_draw_card(context, game, cur_player)
        return

    # Check if option_pass was tapped
    if card_key == "option_pass":
        try:
            await msg.delete()
        except Exception:
            pass
        await execute_pass_turn(context, game, cur_player)
        return

    # Check if option_info was tapped
    if card_key == "option_info":
        try:
            await msg.delete()
        except Exception:
            pass
        game.last_status_note = "ℹ️ <i>Match the top card color/value or play a Wild card!</i>"
        await render_game_board(None, context, game, send_new=False)
        return

    # Check hand cards
    hand = game.hands.get(cur_player.id, [])
    top_card = game.discard_pile[-1]
    matched_idx = None

    for idx, c in enumerate(hand):
        if get_card_key(c) == card_key:
            matched_idx = idx
            break

    if matched_idx is None:
        try:
            await msg.delete()
        except Exception:
            pass
        return

    if is_grey_card:
        try:
            await msg.delete()
        except Exception:
            pass
        game.last_status_note = f"🔒 <i>That card doesn't match {format_card(top_card)}! Choose a playable card or draw.</i>"
        await render_game_board(None, context, game, send_new=False)
        return

    card = hand[matched_idx]
    if not is_card_playable(card, top_card, game.active_color):
        try:
            await msg.delete()
        except Exception:
            pass
        game.last_status_note = f"🔒 <i>That card cannot be played on {format_card(top_card)}!</i>"
        await render_game_board(None, context, game, send_new=False)
        return

    # Execute playable card!
    await execute_play_card_sticker(context, game, cur_player, matched_idx, msg)


async def execute_play_card_sticker(
    context: ContextTypes.DEFAULT_TYPE,
    game: UnoGameSession,
    cur_player: User,
    card_idx: int,
    stk_msg: any,
):
    """Executes a valid card play via sticker."""
    hand = game.hands.get(cur_player.id, [])
    if card_idx >= len(hand):
        return

    card = hand.pop(card_idx)
    game.discard_pile.append(card)
    game.has_drawn_this_turn = False

    # Cancel turn timer
    if game.turn_timer_task:
        game.turn_timer_task.cancel()
    game.consecutive_afk = 0
    game.last_status_note = ""

    # Delete old top card sticker to keep the chat tidy
    new_mid = getattr(stk_msg, "message_id", None)
    if game.last_sticker_message_id and new_mid and game.last_sticker_message_id != new_mid:
        try:
            await context.bot.delete_message(chat_id=game.chat_id, message_id=game.last_sticker_message_id)
        except Exception:
            pass

    # The played sticker is now the new top card sticker!
    if new_mid:
        game.last_sticker_message_id = new_mid

    # Check WIN CONDITION
    if len(hand) == 0:
        total_pot = game.bet * len(game.players)
        if total_pot > 0:
            await update_balance(cur_player.id, total_pot)
            pot_text = f"🏆 <b>Prize Won:</b> <code>+{total_pot:,} Coins!</code> 🪙"
        else:
            pot_text = "🎉 <b>Champion of the table!</b>"

        del UNO_GAMES[game.chat_id]
        if game.board_message_id:
            try:
                await context.bot.delete_message(chat_id=game.chat_id, message_id=game.board_message_id)
            except Exception:
                pass

        win_text = (
            f"🎉 <b>ᴜɴᴏ! ᴡᴇ ʜᴀᴠᴇ ᴀ ᴡɪɴɴᴇʀ!</b> 🏆\n\n"
            f"<blockquote>👑 {cur_player.mention_html()} played their final card <b>{format_card(card)}</b> and won the game!\n"
            f"{pot_text}</blockquote>\n\n"
            "🎋 <i>Type /uno to start another round!</i>"
        )
        await context.bot.send_message(chat_id=game.chat_id, text=win_text, parse_mode="HTML")
        return

    # Shout UNO if 1 card left
    if len(hand) == 1:
        game.last_status_note = f"📢 <b>ᴜɴᴏ!</b> {cur_player.first_name} has only <b>1 CARD</b> remaining! 🔥"

    # Wild Card Color Selection
    if card["color"] == "wild":
        game.pending_wild_player_id = cur_player.id
        game.pending_wild_card = card

        if game.board_message_id:
            try:
                await context.bot.delete_message(chat_id=game.chat_id, message_id=game.board_message_id)
            except Exception:
                pass

        color_buttons = [
            [
                InlineKeyboardButton("🔴 Red", callback_data="uno_wild_red"),
                InlineKeyboardButton("🔵 Blue", callback_data="uno_wild_blue"),
            ],
            [
                InlineKeyboardButton("🟢 Green", callback_data="uno_wild_green"),
                InlineKeyboardButton("🟡 Yellow", callback_data="uno_wild_yellow"),
            ]
        ]
        wild_msg = await context.bot.send_message(
            chat_id=game.chat_id,
            text=(
                f"🌈 <b>{cur_player.mention_html()} played {format_card(card)}!</b>\n\n"
                "<blockquote>Choose the next active color for the table:</blockquote>"
            ),
            reply_markup=InlineKeyboardMarkup(color_buttons),
            parse_mode="HTML",
        )
        game.board_message_id = wild_msg.message_id
        game.turn_timer_task = asyncio.create_task(uno_wild_timeout(context, game, cur_player.id))
        return

    # Regular card: active color matches card color
    game.active_color = card["color"]

    # Action card handling
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
        game.last_status_note += f"\n➕2: <i>{target_player.first_name} drew 2 cards & skipped!</i>"

    # Advance turn index
    game.current_idx = (game.current_idx + (game.direction * advance_turns)) % num_players
    await render_game_board(None, context, game, send_new=True)


async def execute_draw_card(context: ContextTypes.DEFAULT_TYPE, game: UnoGameSession, cur_player: User):
    """Draws a card from the deck for the current player."""
    if not game.deck:
        top_keep = game.discard_pile[-1]
        reshuffled = game.discard_pile[:-1]
        random.shuffle(reshuffled)
        game.deck.extend(reshuffled)
        game.discard_pile = [top_keep]
        if not game.deck:
            game.deck = generate_deck()

    drawn = game.deck.pop()
    game.hands[cur_player.id].append(drawn)
    game.consecutive_afk = 0

    playable = is_card_playable(drawn, game.discard_pile[-1], game.active_color)
    if playable:
        game.has_drawn_this_turn = True
        game.last_status_note = f"🃏 <i>{cur_player.first_name} drew {format_card(drawn)}! You can play it or pass.</i>"
        await render_game_board(None, context, game, send_new=False)
    else:
        game.has_drawn_this_turn = False
        game.current_idx = (game.current_idx + game.direction) % len(game.players)
        game.last_status_note = f"🃏 <i>{cur_player.first_name} drew a card and passed turn.</i>"
        await render_game_board(None, context, game, send_new=True)


async def execute_pass_turn(context: ContextTypes.DEFAULT_TYPE, game: UnoGameSession, cur_player: User):
    """Passes turn after drawing."""
    game.has_drawn_this_turn = False
    game.consecutive_afk = 0
    game.current_idx = (game.current_idx + game.direction) % len(game.players)
    game.last_status_note = f"⏭ <i>{cur_player.first_name} passed their turn.</i>"
    await render_game_board(None, context, game, send_new=True)


async def uno_wild_timeout(context: ContextTypes.DEFAULT_TYPE, game: UnoGameSession, player_id: int):
    """Auto-picks a random color if Wild color choice times out."""
    try:
        await asyncio.sleep(30)
    except asyncio.CancelledError:
        return

    if game.chat_id not in UNO_GAMES:
        return

    if game.pending_wild_player_id == player_id:
        chosen_color = random.choice(COLORS)
        await finish_wild_selection(context, game, chosen_color)


async def uno_wild_color_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = update.effective_chat.id
    chosen_color = query.data.split("_")[2]

    if chat_id not in UNO_GAMES:
        return
    game = UNO_GAMES[chat_id]

    if query.from_user.id != game.pending_wild_player_id:
        try:
            await query.answer("Only the player who placed the Wild card can pick the color!", show_alert=True)
        except Exception:
            pass
        return

    if game.turn_timer_task:
        game.turn_timer_task.cancel()

    try:
        await query.answer(f"Color set to {chosen_color.upper()}!")
    except Exception:
        pass

    await finish_wild_selection(context, game, chosen_color)


async def finish_wild_selection(context: ContextTypes.DEFAULT_TYPE, game: UnoGameSession, chosen_color: str):
    """Applies chosen wild color, executes Wild +4 penalty if applicable, and advances turn."""
    cur_player = game.players[game.current_idx]
    game.active_color = chosen_color
    wild_card = game.pending_wild_card or {"val": "wild"}

    game.pending_wild_player_id = None
    game.pending_wild_card = None

    num_players = len(game.players)
    advance_turns = 1

    if wild_card.get("val") == "draw4":
        next_target_idx = (game.current_idx + game.direction) % num_players
        target_player = game.players[next_target_idx]
        for _ in range(4):
            if not game.deck:
                game.deck = generate_deck()
            game.hands[target_player.id].append(game.deck.pop())
        advance_turns = 2
        game.last_status_note = f"🌈 <i>{cur_player.first_name} chose {chosen_color.upper()}! {target_player.first_name} drew 4 cards & was skipped.</i>"
    else:
        game.last_status_note = f"🌈 <i>{cur_player.first_name} set active color to {chosen_color.upper()}!</i>"

    game.current_idx = (game.current_idx + (game.direction * advance_turns)) % num_players
    await render_game_board(None, context, game, send_new=True)


async def uno_turn_timeout(context: ContextTypes.DEFAULT_TYPE, game: UnoGameSession, player_id: int):
    """Auto-draws and skips turn if player is AFK for 45s. Auto-ends game if all players abandon match."""
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

        if game.bet > 0:
            for p in game.players:
                await update_balance(p.id, game.bet)

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

    # Auto-draw & pass turn
    if not game.deck:
        game.deck = generate_deck()
    drawn = game.deck.pop()
    game.hands[cur_player.id].append(drawn)
    game.current_idx = (game.current_idx + game.direction) % len(game.players)

    game.last_status_note = f"⏳ <i>{cur_player.first_name} timed out & auto-drew a card!</i>"
    await render_game_board(None, context, game, send_new=True)


async def uno_secret_hand_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pops up the user's private hand in a secure modal alert so no one else sees it."""
    query = update.callback_query
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in UNO_GAMES:
        try:
            await query.answer("No active UNO game here.", show_alert=True)
        except Exception:
            pass
        return

    game = UNO_GAMES[chat_id]
    if user.id not in game.hands:
        try:
            await query.answer("You are not playing in this game!", show_alert=True)
        except Exception:
            pass
        return

    hand = game.hands[user.id]
    top = game.discard_pile[-1]
    is_turn = (game.players[game.current_idx].id == user.id)

    card_items = []
    for c in hand:
        playable = is_turn and is_card_playable(c, top, game.active_color)
        badge = "✨" if playable else ""
        card_items.append(f"{format_card_button(c)}{badge}")

    turn_str = "👉 YOUR TURN!" if is_turn else f"Turn: {game.players[game.current_idx].first_name}"
    alert_text = f"🎴 Your Hand ({len(hand)}):\n{', '.join(card_items)}\n\n{turn_str}"

    try:
        await query.answer(alert_text[:190], show_alert=True)
    except Exception:
        pass


async def uno_toggle_buttons_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggles between pure Inline Mode and Button Mode."""
    query = update.callback_query
    chat_id = update.effective_chat.id

    if chat_id not in UNO_GAMES:
        return
    game = UNO_GAMES[chat_id]

    game.button_mode = not game.button_mode
    mode_name = "Button Controls" if game.button_mode else "Official Inline Mode"
    try:
        await query.answer(f"Switched to {mode_name}!")
    except Exception:
        pass

    await render_game_board(None, context, game, send_new=False)


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
    """Handles playing a valid card via button mode."""
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
    top_card = game.discard_pile[-1]
    if not is_card_playable(card, top_card, game.active_color):
        try:
            await query.answer("🔒 Card is not playable!", show_alert=True)
        except Exception:
            pass
        return

    # Send official sticker to chat
    stk_id = get_card_sticker_id(game.theme, card)
    stk_msg = None
    if stk_id:
        try:
            stk_msg = await context.bot.send_sticker(chat_id=game.chat_id, sticker=stk_id)
        except Exception:
            pass

    try:
        await query.answer(f"Played {format_card(card)}!")
    except Exception:
        pass

    class DummyStickerMsg:
        def __init__(self, mid):
            self.message_id = mid

    msg_obj = stk_msg if stk_msg else DummyStickerMsg(game.last_sticker_message_id)
    await execute_play_card_sticker(context, game, cur_player, card_idx, msg_obj)


async def uno_draw_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles draw card button."""
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

    try:
        await query.answer("Drawing card...")
    except Exception:
        pass
    await execute_draw_card(context, game, cur_player)


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
    # Commands
    app.add_handler(CommandHandler(["uno", "unogame"], uno_command))
    app.add_handler(CommandHandler(["close", "startuno", "unostart"], close_command))
    app.add_handler(CommandHandler(["unodeck", "unotheme"], unodeck_command))
    app.add_handler(CommandHandler(["enduno", "canceluno"], end_uno_command))

    # Lobby Callbacks
    app.add_handler(CallbackQueryHandler(uno_join_callback, pattern=r"^uno_join$"))
    app.add_handler(CallbackQueryHandler(uno_leave_callback, pattern=r"^uno_leave$"))
    app.add_handler(CallbackQueryHandler(uno_start_callback, pattern=r"^uno_start$"))

    # In-Game Callbacks
    app.add_handler(CallbackQueryHandler(uno_secret_hand_callback, pattern=r"^uno_secret_hand$"))
    app.add_handler(CallbackQueryHandler(uno_toggle_buttons_callback, pattern=r"^uno_toggle_buttons$"))
    app.add_handler(CallbackQueryHandler(uno_wild_color_callback, pattern=r"^uno_wild_\w+$"))
    app.add_handler(CallbackQueryHandler(uno_play_card_callback, pattern=r"^uno_c_\d+$"))
    app.add_handler(CallbackQueryHandler(uno_locked_card_callback, pattern=r"^uno_locked_\d+$"))
    app.add_handler(CallbackQueryHandler(uno_draw_callback, pattern=r"^uno_draw$"))
    app.add_handler(CallbackQueryHandler(end_uno_command, pattern=r"^uno_cancel$"))

    # Telegram Inline Query & Played Sticker Listeners
    app.add_handler(InlineQueryHandler(uno_inline_query_handler))
    app.add_handler(ChosenInlineResultHandler(uno_chosen_inline_result_handler))
    app.add_handler(MessageHandler(filters.Sticker.ALL & filters.VIA_BOT, uno_via_bot_sticker_handler))


async def uno_chosen_inline_result_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Listens to chosen inline results (if enabled in BotFather)."""
    cir = update.chosen_inline_result
    if not cir:
        return
    log.debug(f"UNO Chosen Inline Result: user={cir.from_user.id}, result_id={cir.result_id}")

