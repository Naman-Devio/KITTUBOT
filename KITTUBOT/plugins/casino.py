# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT High-Stakes Casino & Gambling Engine
Native Telegram animated physics games (Dice, Dart, Basket, Slots), Coinflip & Interactive Blackjack.
"""

import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, User
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from KITTUBOT.config import config
from KITTUBOT.database.users import ensure_user, get_user, update_balance

__mod_name__ = "Casino"
__help__ = """
<blockquote>🎰 <b>ᴄᴀsɪɴᴏ & ɢᴀᴍʙʟɪɴɢ:</b>
• <code>/dice [bet]</code> - ʀᴏʟʟ ᴀɴɪᴍᴀᴛᴇᴅ ᴅɪᴄᴇ (ᴜᴘ ᴛᴏ 2.5x)
• <code>/dart [bet]</code> - ᴛʜʀᴏᴡ ʙᴜʟʟsᴇʏᴇ ᴅᴀʀᴛ (ᴜᴘ ᴛᴏ 3.5x)
• <code>/basket [bet]</code> - sʜᴏᴏᴛ ᴀ ʙᴀsᴋᴇᴛʙᴀʟʟ ʜᴏᴏᴘ (2.0x)
• <code>/football [bet]</code> - ᴘᴇɴᴀʟᴛʏ sʜᴏᴏᴛᴏᴜᴛ (1.85x)
• <code>/bowling [bet]</code> - ʀᴏʟʟ ᴀ sᴛʀɪᴋᴇ (ᴜᴘ ᴛᴏ 3.5x)
• <code>/slots [bet]</code> - sᴘɪɴ 777 sʟᴏᴛ ᴍᴀᴄʜɪɴᴇ (ᴜᴘ ᴛᴏ 10x)
• <code>/coinflip [h|t] [bet]</code> - ғʟɪᴘ ᴀ ɢᴏʟᴅᴇɴ ᴄᴏɪɴ (1.95x)
• <code>/blackjack [bet]</code> - 21 ᴄᴀʀᴅ ɢᴀᴍᴇ ᴠs ᴅᴇᴀʟᴇʀ</blockquote>
"""

ACTIVE_BLACKJACK_GAMES: dict[str, dict] = {}  # key: f"{chat_id}_{user_id}" -> game_state


def create_bj_deck() -> list[dict]:
    suits = ["♠️", "♥️", "♦️", "♣️"]
    ranks = [
        ("2", 2), ("3", 3), ("4", 4), ("5", 5), ("6", 6),
        ("7", 7), ("8", 8), ("9", 9), ("10", 10),
        ("J", 10), ("Q", 10), ("K", 10), ("A", 11)
    ]
    deck = [{"rank": r, "val": v, "suit": s} for s in suits for r, v in ranks]
    random.shuffle(deck)
    return deck


def calculate_bj_score(hand: list[dict]) -> int:
    score = sum(c["val"] for c in hand)
    aces = sum(1 for c in hand if c["rank"] == "A")
    while score > 21 and aces > 0:
        score -= 10
        aces -= 1
    return score


def format_bj_hand(hand: list[dict], hide_second: bool = False) -> str:
    if hide_second and len(hand) >= 2:
        return f"[{hand[0]['suit']} {hand[0]['rank']}], [🎴 Hidden]"
    return ", ".join(f"[{c['suit']} {c['rank']}]" for c in hand)


# -------------------------------------------------------------
# 1. /dice [bet]
# -------------------------------------------------------------
async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_html("🎲 <b>Usage:</b> <code>/dice <bet></code> (e.g. <code>/dice 500</code>)")
        return

    bet = int(context.args[0])
    if bet < 50:
        await update.message.reply_html("⚠️ Minimum bet is <b>50 Coins</b>!")
        return

    u_data = await ensure_user(user)
    if u_data.get("balance", 0) < bet:
        await update.message.reply_html(f"❌ You don't have <b>{bet:,} Coins</b> in your wallet!")
        return

    await update_balance(user.id, -bet)

    # Roll animated Telegram dice
    dice_msg = await context.bot.send_dice(chat_id=chat.id, emoji="🎲")
    await asyncio.sleep(3.5)

    value = dice_msg.dice.value  # 1 to 6

    if value == 6:
        payout = int(bet * 2.5)
        profit = payout - bet
        await update_balance(user.id, payout)
        res_text = (
            f"🎉 <b>ɴᴀᴛᴜʀᴀʟ sɪx! ʙɪɢ ᴡɪɴ!</b> 🎲\n\n"
            f"<blockquote>Rolled: <b>{value}</b> 🌟\n"
            f"Multiplier: <b>2.5x</b>\n"
            f"Profit: <b>+{profit:,} Coins</b>! 🪙</blockquote>"
        )
    elif value in [4, 5]:
        payout = int(bet * 1.5)
        profit = payout - bet
        await update_balance(user.id, payout)
        res_text = (
            f"✅ <b>ʏᴏᴜ ᴡᴏɴ!</b> 🎲\n\n"
            f"<blockquote>Rolled: <b>{value}</b>\n"
            f"Multiplier: <b>1.5x</b>\n"
            f"Profit: <b>+{profit:,} Coins</b>! 🪙</blockquote>"
        )
    else:
        res_text = (
            f"💀 <b>ʜᴏᴜsᴇ ᴡᴏɴ!</b> 🎲\n\n"
            f"<blockquote>Rolled: <b>{value}</b>\n"
            f"You lost <b>-{bet:,} Coins</b>! Better luck next roll.</blockquote>"
        )

    await update.message.reply_html(res_text)


# -------------------------------------------------------------
# 2. /dart [bet]
# -------------------------------------------------------------
async def dart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_html("🎯 <b>Usage:</b> <code>/dart <bet></code> (e.g. <code>/dart 500</code>)")
        return

    bet = int(context.args[0])
    if bet < 50:
        await update.message.reply_html("⚠️ Minimum bet is <b>50 Coins</b>!")
        return

    u_data = await ensure_user(user)
    if u_data.get("balance", 0) < bet:
        await update.message.reply_html(f"❌ You don't have <b>{bet:,} Coins</b>!")
        return

    await update_balance(user.id, -bet)

    dart_msg = await context.bot.send_dice(chat_id=chat.id, emoji="🎯")
    await asyncio.sleep(3.5)

    value = dart_msg.dice.value

    if value == 6:
        # Bullseye!
        payout = int(bet * 3.5)
        profit = payout - bet
        await update_balance(user.id, payout)
        res_text = (
            f"🎯 <b>ʙᴜʟʟsᴇʏᴇ! ɪɴᴄʀᴇᴅɪʙʟᴇ sʜᴏᴛ!</b> 💥\n\n"
            f"<blockquote>Hit: <b>Center Bullseye (Value 6)</b> 🏆\n"
            f"Multiplier: <b>3.5x</b>\n"
            f"Profit: <b>+{profit:,} Coins</b>! 🪙</blockquote>"
        )
    elif value in [4, 5]:
        payout = int(bet * 1.4)
        profit = payout - bet
        await update_balance(user.id, payout)
        res_text = (
            f"✅ <b>ɢᴏᴏᴅ sʜᴏᴛ!</b> 🎯\n\n"
            f"<blockquote>Hit: <b>Inner Ring (Value {value})</b>\n"
            f"Multiplier: <b>1.4x</b>\n"
            f"Profit: <b>+{profit:,} Coins</b>! 🪙</blockquote>"
        )
    else:
        res_text = (
            f"💨 <b>ᴍɪssᴇᴅ ᴛʜᴇ ᴛᴀʀɢᴇᴛ!</b> 🎯\n\n"
            f"<blockquote>Hit: <b>Outer rim (Value {value})</b>\n"
            f"You lost <b>-{bet:,} Coins</b>.</blockquote>"
        )

    await update.message.reply_html(res_text)


# -------------------------------------------------------------
# 3. /basket [bet]
# -------------------------------------------------------------
async def basket_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_html("🏀 <b>Usage:</b> <code>/basket <bet></code> (e.g. <code>/basket 500</code>)")
        return

    bet = int(context.args[0])
    if bet < 50:
        await update.message.reply_html("⚠️ Minimum bet is <b>50 Coins</b>!")
        return

    u_data = await ensure_user(user)
    if u_data.get("balance", 0) < bet:
        await update.message.reply_html(f"❌ You don't have <b>{bet:,} Coins</b>!")
        return

    await update_balance(user.id, -bet)

    basket_msg = await context.bot.send_dice(chat_id=chat.id, emoji="🏀")
    await asyncio.sleep(3.5)

    value = basket_msg.dice.value  # 4 and 5 are successful shots

    if value in [4, 5]:
        payout = int(bet * 2.0)
        profit = payout - bet
        await update_balance(user.id, payout)
        res_text = (
            f"🏀 <b>sᴡɪsʜ! ᴄʟᴇᴀɴ ʙᴀsᴋᴇᴛ!</b> ⛹️‍♂️🔥\n\n"
            f"<blockquote>Shot: <b>Made the Hoop!</b>\n"
            f"Multiplier: <b>2.0x</b>\n"
            f"Profit: <b>+{profit:,} Coins</b>! 🪙</blockquote>"
        )
    else:
        res_text = (
            f"🧱 <b>ᴄʟᴀɴᴋ! ʙʀɪᴄᴋᴇᴅ ᴛʜᴇ sʜᴏᴛ!</b> 🏀\n\n"
            f"<blockquote>Shot: <b>Bounced off the rim!</b>\n"
            f"You lost <b>-{bet:,} Coins</b>.</blockquote>"
        )

    await update.message.reply_html(res_text)


# -------------------------------------------------------------
# 3b. /football [bet]
# -------------------------------------------------------------
async def football_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_html("⚽ <b>Usage:</b> <code>/football <bet></code> (e.g. <code>/football 200</code>)")
        return

    bet = int(context.args[0])
    if bet < 50:
        await update.message.reply_html("⚠️ Minimum bet is <b>50 Coins</b>!")
        return

    u_data = await ensure_user(user)
    if u_data.get("balance", 0) < bet:
        await update.message.reply_html(f"❌ You don't have <b>{bet:,} Coins</b>!")
        return

    await update_balance(user.id, -bet)

    ball_msg = await context.bot.send_dice(chat_id=chat.id, emoji="⚽")
    await asyncio.sleep(3.5)

    value = ball_msg.dice.value  # 3, 4, 5 are goals in net

    if value in [3, 4, 5]:
        payout = int(bet * 1.85)
        profit = payout - bet
        await update_balance(user.id, payout)
        res_text = (
            f"⚽ <b>ɢᴏᴏᴏᴏᴏᴀʟ! ɪɴ ᴛʜᴇ ɴᴇᴛ!</b> 🥅🔥\n\n"
            f"<blockquote>Strike: <b>Clean Goal!</b>\n"
            f"Multiplier: <b>1.85x</b>\n"
            f"Profit: <b>+{profit:,} Coins</b>! 🪙</blockquote>"
        )
    else:
        res_text = (
            f"🥅 <b>sᴀᴠᴇᴅ / ᴍɪssᴇᴅ!</b> ⚽🧱\n\n"
            f"<blockquote>Keeper blocked the shot or hit the crossbar!\n"
            f"You lost <b>-{bet:,} Coins</b>.</blockquote>"
        )

    await update.message.reply_html(res_text)


# -------------------------------------------------------------
# 3c. /bowling [bet]
# -------------------------------------------------------------
async def bowling_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_html("🎳 <b>Usage:</b> <code>/bowling <bet></code> (e.g. <code>/bowling 250</code>)")
        return

    bet = int(context.args[0])
    if bet < 50:
        await update.message.reply_html("⚠️ Minimum bet is <b>50 Coins</b>!")
        return

    u_data = await ensure_user(user)
    if u_data.get("balance", 0) < bet:
        await update.message.reply_html(f"❌ You don't have <b>{bet:,} Coins</b>!")
        return

    await update_balance(user.id, -bet)

    bowl_msg = await context.bot.send_dice(chat_id=chat.id, emoji="🎳")
    await asyncio.sleep(3.5)

    value = bowl_msg.dice.value  # 6 = strike, 4-5 = spare, 1-3 = gutter

    if value == 6:
        payout = int(bet * 3.5)
        profit = payout - bet
        await update_balance(user.id, payout)
        res_text = (
            f"🎳 <b>sᴛʀɪᴋᴇ! ᴀʟʟ 10 ᴘɪɴs ᴅᴏᴡɴ!</b> 👑💥\n\n"
            f"<blockquote>Roll: <b>PERFECT STRIKE!</b>\n"
            f"Multiplier: <b>3.5x</b>\n"
            f"Profit: <b>+{profit:,} Coins</b>! 🪙</blockquote>"
        )
    elif value in [4, 5]:
        payout = int(bet * 1.8)
        profit = payout - bet
        await update_balance(user.id, payout)
        res_text = (
            f"🎳 <b>sᴘᴀʀᴇ! ɢʀᴇᴀᴛ ʀᴏʟʟ!</b> ✨\n\n"
            f"<blockquote>Pins knocked: <b>{value} Pins</b>\n"
            f"Multiplier: <b>1.8x</b>\n"
            f"Profit: <b>+{profit:,} Coins</b>! 🪙</blockquote>"
        )
    else:
        res_text = (
            f"🎳 <b>ɢᴜᴛᴛᴇʀ ʙᴀʟʟ!</b> 💨\n\n"
            f"<blockquote>Ball slipped into the gutter lane!\n"
            f"You lost <b>-{bet:,} Coins</b>.</blockquote>"
        )

    await update.message.reply_html(res_text)


# -------------------------------------------------------------
# 4. /slots [bet]
# -------------------------------------------------------------
async def slots_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_html("🎰 <b>Usage:</b> <code>/slots <bet></code> (e.g. <code>/slots 500</code>)")
        return

    bet = int(context.args[0])
    if bet < 50:
        await update.message.reply_html("⚠️ Minimum bet is <b>50 Coins</b>!")
        return

    u_data = await ensure_user(user)
    if u_data.get("balance", 0) < bet:
        await update.message.reply_html(f"❌ You don't have <b>{bet:,} Coins</b>!")
        return

    await update_balance(user.id, -bet)

    slot_msg = await context.bot.send_dice(chat_id=chat.id, emoji="🎰")
    await asyncio.sleep(3.5)

    value = slot_msg.dice.value

    # In Telegram slots:
    # 64 = 777 Jackpot
    # 1 = BAR BAR BAR
    # 22 = Berries
    # 43 = Lemons
    if value == 64:
        payout = int(bet * 10.0)
        profit = payout - bet
        await update_balance(user.id, payout)
        res_text = (
            f"🎰 <b>𝟟𝟟𝟟 𝕄𝔼𝔾𝔸 𝕁𝔸ℂ𝕂ℙ𝕆𝕋!</b> 👑🎉🎉\n\n"
            f"<blockquote>Reels: <b>7️⃣ 7️⃣ 7️⃣</b>\n"
            f"Multiplier: <b>10.0x</b>\n"
            f"Jackpot Profit: <b>+{profit:,} Coins</b>! 🪙🪙🪙</blockquote>"
        )
    elif value == 1:
        payout = int(bet * 5.0)
        profit = payout - bet
        await update_balance(user.id, payout)
        res_text = (
            f"🎰 <b>ʙᴀʀ ʙᴀʀ ʙᴀʀ ᴡɪɴ!</b> 💰\n\n"
            f"<blockquote>Reels: <b>BAR BAR BAR</b>\n"
            f"Multiplier: <b>5.0x</b>\n"
            f"Profit: <b>+{profit:,} Coins</b>! 🪙</blockquote>"
        )
    elif value in [22, 43]:
        payout = int(bet * 3.0)
        profit = payout - bet
        await update_balance(user.id, payout)
        res_text = (
            f"🍓 <b>ᴛʀɪᴘʟᴇ ғʀᴜɪᴛ ᴍᴀᴛᴄʜ!</b> 🎰\n\n"
            f"<blockquote>Reels: <b>Triple Matched!</b>\n"
            f"Multiplier: <b>3.0x</b>\n"
            f"Profit: <b>+{profit:,} Coins</b>! 🪙</blockquote>"
        )
    elif value in [16, 32, 48]:
        payout = int(bet * 1.5)
        profit = payout - bet
        await update_balance(user.id, payout)
        res_text = (
            f"✨ <b>ᴅᴏᴜʙʟᴇ sʏᴍʙᴏʟ ᴍᴀᴛᴄʜ!</b> 🎰\n\n"
            f"<blockquote>Multiplier: <b>1.5x</b>\n"
            f"Profit: <b>+{profit:,} Coins</b>! 🪙</blockquote>"
        )
    else:
        res_text = (
            f"💀 <b>ɴᴏ ᴍᴀᴛᴄʜ! sᴘɪɴ ᴀɢᴀɪɴ!</b> 🎰\n\n"
            f"<blockquote>Reels did not align.\n"
            f"Lost: <b>-{bet:,} Coins</b>.</blockquote>"
        )

    await update.message.reply_html(res_text)


# -------------------------------------------------------------
# 5. /coinflip [heads|tails] [bet]
# -------------------------------------------------------------
async def coinflip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if len(context.args) < 2 or not context.args[1].isdigit():
        await update.message.reply_html(
            "🪙 <b>Usage:</b> <code>/coinflip <heads|tails> <bet></code>\n"
            "Example: <code>/coinflip heads 500</code> or <code>/cf h 1000</code>"
        )
        return

    choice = context.args[0].lower()
    if choice in ["h", "head", "heads"]:
        user_pick = "heads"
    elif choice in ["t", "tail", "tails"]:
        user_pick = "tails"
    else:
        await update.message.reply_html("⚠️ Choose <b>heads</b> or <b>tails</b>!")
        return

    bet = int(context.args[1])
    if bet < 50:
        await update.message.reply_html("⚠️ Minimum bet is <b>50 Coins</b>!")
        return

    u_data = await ensure_user(user)
    if u_data.get("balance", 0) < bet:
        await update.message.reply_html(f"❌ You don't have <b>{bet:,} Coins</b>!")
        return

    await update_balance(user.id, -bet)

    suspense = await update.message.reply_html("🪙 <i>Flipping the golden coin into the air...</i>")
    await asyncio.sleep(1.2)

    outcome = random.choice(["heads", "tails"])
    emoji = "👑 HEADS" if outcome == "heads" else "🦅 TAILS"

    if user_pick == outcome:
        payout = int(bet * 1.95)
        profit = payout - bet
        await update_balance(user.id, payout)
        await suspense.edit_text(
            f"🪙 <b>ᴄᴏɪɴғʟɪᴘ ᴡɪɴ!</b> ✨\n\n"
            f"<blockquote>Result: <b>{emoji}</b>\n"
            f"Your call: <b>{user_pick.upper()}</b> ✅\n"
            f"Multiplier: <b>1.95x</b>\n"
            f"Profit: <b>+{profit:,} Coins</b>! 🪙</blockquote>",
            parse_mode="HTML",
        )
    else:
        await suspense.edit_text(
            f"💀 <b>ᴄᴏɪɴғʟɪᴘ ʟᴏss!</b> 🪙\n\n"
            f"<blockquote>Result: <b>{emoji}</b>\n"
            f"Your call: <b>{user_pick.upper()}</b> ❌\n"
            f"You lost: <b>-{bet:,} Coins</b>.</blockquote>",
            parse_mode="HTML",
        )


# -------------------------------------------------------------
# 6. /blackjack [bet] (Interactive 21)
# -------------------------------------------------------------
async def blackjack_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    session_key = f"{chat.id}_{user.id}"

    if session_key in ACTIVE_BLACKJACK_GAMES:
        await update.message.reply_html("⚠️ <b>You already have an active Blackjack hand!</b> Finish it first.")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_html("🃏 <b>Usage:</b> <code>/blackjack <bet></code> (e.g. <code>/bj 500</code>)")
        return

    bet = int(context.args[0])
    if bet < 100:
        await update.message.reply_html("⚠️ Minimum Blackjack bet is <b>100 Coins</b>!")
        return

    u_data = await ensure_user(user)
    if u_data.get("balance", 0) < bet:
        await update.message.reply_html(f"❌ You don't have <b>{bet:,} Coins</b>!")
        return

    await update_balance(user.id, -bet)

    deck = create_bj_deck()
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]

    p_score = calculate_bj_score(player_hand)
    d_score = calculate_bj_score(dealer_hand)

    # Check natural Blackjack (21 on deal)
    if p_score == 21:
        if d_score == 21:
            # Push
            await update_balance(user.id, bet)
            await update.message.reply_html(
                "🤝 <b>ʙʟᴀᴄᴋᴊᴀᴄᴋ ᴘᴜsʜ!</b>\n\n"
                f"<blockquote>Your hand: {format_bj_hand(player_hand)} (21)\n"
                f"Dealer hand: {format_bj_hand(dealer_hand)} (21)\n"
                f"Tie game! Bet refunded.</blockquote>"
            )
            return
        else:
            payout = int(bet * 2.5)
            profit = payout - bet
            await update_balance(user.id, payout)
            await update.message.reply_html(
                "🔥 <b>ɴᴀᴛᴜʀᴀʟ ʙʟᴀᴄᴋᴊᴀᴄᴋ 21!</b> 🏆\n\n"
                f"<blockquote>Your hand: <b>{format_bj_hand(player_hand)}</b> (21!)\n"
                f"Dealer hand: {format_bj_hand(dealer_hand)} ({d_score})\n"
                f"Payout: <b>2.5x</b>\n"
                f"Profit: <b>+{profit:,} Coins</b>! 🪙</blockquote>"
            )
            return

    game_state = {
        "user_id": user.id,
        "chat_id": chat.id,
        "bet": bet,
        "deck": deck,
        "player_hand": player_hand,
        "dealer_hand": dealer_hand,
    }
    ACTIVE_BLACKJACK_GAMES[session_key] = game_state

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🃏 ʜɪᴛ", callback_data=f"bj_hit_{user.id}"),
            InlineKeyboardButton("🛑 sᴛᴀɴᴅ", callback_data=f"bj_stand_{user.id}"),
        ]
    ])

    text = (
        "🃏 <b>ᴋɪᴛᴛᴜ ʙʟᴀᴄᴋᴊᴀᴄᴋ ᴛᴀʙʟᴇ</b> 🎰\n\n"
        f"<blockquote>👤 <b>{user.first_name}'s Hand:</b> {format_bj_hand(player_hand)} (Score: <b>{p_score}</b>)\n"
        f"🎩 <b>Dealer's Hand:</b> {format_bj_hand(dealer_hand, hide_second=True)}\n"
        f"💰 <b>Current Bet:</b> <code>{bet:,} Coins</code></blockquote>\n\n"
        "🎋 <i>Choose to Hit for another card or Stand with your total:</i>"
    )

    await update.message.reply_html(text, reply_markup=keyboard)


async def bj_hit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    chat = update.effective_chat
    session_key = f"{chat.id}_{user.id}"

    if session_key not in ACTIVE_BLACKJACK_GAMES:
        try:
            await query.answer("No active blackjack game found!", show_alert=True)
        except Exception:
            pass
        return

    game = ACTIVE_BLACKJACK_GAMES[session_key]
    target_user_id = int(query.data.split("_")[2])
    if user.id != target_user_id:
        try:
            await query.answer("This is not your table!", show_alert=True)
        except Exception:
            pass
        return

    # Draw card
    card = game["deck"].pop()
    game["player_hand"].append(card)
    score = calculate_bj_score(game["player_hand"])

    if score > 21:
        # BUST!
        del ACTIVE_BLACKJACK_GAMES[session_key]
        try:
            await query.answer("💥 BUST! Over 21!", show_alert=True)
            await query.edit_message_text(
                "💥 <b>ʙᴜsᴛ! ʏᴏᴜ ᴡᴇɴᴛ ᴏᴠᴇʀ 21!</b> 💀\n\n"
                f"<blockquote>Your Hand: {format_bj_hand(game['player_hand'])} (Score: <b>{score}</b>)\n"
                f"Dealer Hand: {format_bj_hand(game['dealer_hand'])}\n"
                f"Lost: <b>-{game['bet']:,} Coins</b>.</blockquote>",
                parse_mode="HTML",
            )
        except Exception:
            pass
        return

    try:
        await query.answer(f"Hit [{card['suit']} {card['rank']}]! Score: {score}")
    except Exception:
        pass

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🃏 ʜɪᴛ", callback_data=f"bj_hit_{user.id}"),
            InlineKeyboardButton("🛑 sᴛᴀɴᴅ", callback_data=f"bj_stand_{user.id}"),
        ]
    ])

    text = (
        "🃏 <b>ᴋɪᴛᴛᴜ ʙʟᴀᴄᴋᴊᴀᴄᴋ ᴛᴀʙʟᴇ</b> 🎰\n\n"
        f"<blockquote>👤 <b>{user.first_name}'s Hand:</b> {format_bj_hand(game['player_hand'])} (Score: <b>{score}</b>)\n"
        f"🎩 <b>Dealer's Hand:</b> {format_bj_hand(game['dealer_hand'], hide_second=True)}\n"
        f"💰 <b>Current Bet:</b> <code>{game['bet']:,} Coins</code></blockquote>\n\n"
        "🎋 <i>Choose to Hit or Stand:</i>"
    )

    try:
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        pass


async def bj_stand_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    chat = update.effective_chat
    session_key = f"{chat.id}_{user.id}"

    if session_key not in ACTIVE_BLACKJACK_GAMES:
        try:
            await query.answer("No active blackjack game found!", show_alert=True)
        except Exception:
            pass
        return

    game = ACTIVE_BLACKJACK_GAMES[session_key]
    target_user_id = int(query.data.split("_")[2])
    if user.id != target_user_id:
        try:
            await query.answer("This is not your table!", show_alert=True)
        except Exception:
            pass
        return

    del ACTIVE_BLACKJACK_GAMES[session_key]
    player_score = calculate_bj_score(game["player_hand"])

    # Dealer draws until score >= 17
    dealer_score = calculate_bj_score(game["dealer_hand"])
    while dealer_score < 17:
        game["dealer_hand"].append(game["deck"].pop())
        dealer_score = calculate_bj_score(game["dealer_hand"])

    bet = game["bet"]

    if dealer_score > 21:
        # Dealer busts, player wins
        payout = bet * 2
        await update_balance(user.id, payout)
        res = (
            "🎉 <b>ᴅᴇᴀʟᴇʀ ʙᴜsᴛs! ʏᴏᴜ ᴡɪɴ!</b> 🏆\n\n"
            f"<blockquote>👤 <b>Your Hand:</b> {format_bj_hand(game['player_hand'])} (Score: <b>{player_score}</b>)\n"
            f"🎩 <b>Dealer's Hand:</b> {format_bj_hand(game['dealer_hand'])} (Score: <b>{dealer_score} - BUST</b>)\n"
            f"💰 <b>Profit Won:</b> <code>+{bet:,} Coins</code>! 🪙</blockquote>"
        )
    elif player_score > dealer_score:
        payout = bet * 2
        await update_balance(user.id, payout)
        res = (
            "🏆 <b>ʏᴏᴜ ʙᴇᴀᴛ ᴛʜᴇ ᴅᴇᴀʟᴇʀ!</b> 🎉\n\n"
            f"<blockquote>👤 <b>Your Hand:</b> {format_bj_hand(game['player_hand'])} (Score: <b>{player_score}</b>)\n"
            f"🎩 <b>Dealer's Hand:</b> {format_bj_hand(game['dealer_hand'])} (Score: <b>{dealer_score}</b>)\n"
            f"💰 <b>Profit Won:</b> <code>+{bet:,} Coins</code>! 🪙</blockquote>"
        )
    elif player_score == dealer_score:
        # Push
        await update_balance(user.id, bet)
        res = (
            "🤝 <b>ʙʟᴀᴄᴋᴊᴀᴄᴋ ᴘᴜsʜ! ᴛɪᴇ!</b>\n\n"
            f"<blockquote>👤 <b>Your Hand:</b> {format_bj_hand(game['player_hand'])} ({player_score})\n"
            f"🎩 <b>Dealer's Hand:</b> {format_bj_hand(game['dealer_hand'])} ({dealer_score})\n"
            f"Bet refunded: <b>{bet:,} Coins</b>.</blockquote>"
        )
    else:
        res = (
            "💀 <b>ᴅᴇᴀʟᴇʀ ᴡɪɴs!</b> 🎩\n\n"
            f"<blockquote>👤 <b>Your Hand:</b> {format_bj_hand(game['player_hand'])} (Score: <b>{player_score}</b>)\n"
            f"🎩 <b>Dealer's Hand:</b> {format_bj_hand(game['dealer_hand'])} (Score: <b>{dealer_score}</b>)\n"
            f"Lost: <b>-{bet:,} Coins</b>. Better luck next hand!</blockquote>"
        )

    try:
        await query.answer("Hand finished!")
        await query.edit_message_text(text=res, parse_mode="HTML")
    except Exception:
        pass


def register_handlers(app: Application):
    app.add_handler(CommandHandler(["dice", "roll"], dice_command))
    app.add_handler(CommandHandler("dart", dart_command))
    app.add_handler(CommandHandler(["basket", "hoop"], basket_command))
    app.add_handler(CommandHandler(["football", "goal", "shoot"], football_command))
    app.add_handler(CommandHandler(["bowling", "strike"], bowling_command))
    app.add_handler(CommandHandler(["slots", "slot"], slots_command))
    app.add_handler(CommandHandler(["coinflip", "cf"], coinflip_command))
    app.add_handler(CommandHandler(["blackjack", "bj"], blackjack_command))

    app.add_handler(CallbackQueryHandler(bj_hit_callback, pattern=r"^bj_hit_\d+$"))
    app.add_handler(CallbackQueryHandler(bj_stand_callback, pattern=r"^bj_stand_\d+$"))
