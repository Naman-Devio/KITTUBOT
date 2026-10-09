# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Games Engine
Multiplayer Combat RPG, Robbery, Hot Potato Bomb & Group Warfare.
"""

import random
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from KITTUBOT.config import config
from KITTUBOT.core.permissions import resolve_target_user, TargetUser
from KITTUBOT.database.users import (
    ensure_user,
    get_user,
    update_balance,
    is_protected,
    set_protection,
    set_user_dead,
    check_auto_revive,
)
from KITTUBOT.database import users_col

__mod_name__ = "Games"
__help__ = """
<blockquote>⚔️ <b>ᴄᴏᴍʙᴀᴛ & ɢʀᴏᴜᴘ ɢᴀᴍᴇs:</b>
• <code>/kill [reply|@user|id]</code> - ᴀssᴀssɪɴᴀᴛᴇ ᴀ ᴍᴇᴍʙᴇʀ ғᴏʀ ʙᴏᴜɴᴛʏ
• <code>/rob [reply|@user|id]</code> - sᴛᴇᴀʟ ᴄᴏɪɴs ғʀᴏᴍ ᴀ ᴘʟᴀʏᴇʀ
• <code>/protect [1|2]</code> - ʙᴜʏ ɪɴᴠᴜʟɴᴇʀᴀʙɪʟɪᴛʏ sʜɪᴇʟᴅ
• <code>/revive [reply|@user|id]</code> - ʀᴇᴠɪᴠᴇ ʏᴏᴜʀsᴇʟғ ᴏʀ ᴀ ғᴀʟʟᴇɴ ғʀɪᴇɴᴅ
• <code>/game</code> - ᴠɪᴇᴡ ᴄᴏᴍʙᴀᴛ ɢᴀᴍᴇs ᴍᴇɴᴜ</blockquote>
"""


LAST_KILL_TIME: dict[int, float] = {}
LAST_ROB_TIME: dict[int, float] = {}


async def kill_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    attacker = update.effective_user
    if not message or not attacker:
        return

    target, _ = await resolve_target_user(update, context)
    if not target or getattr(target, "is_bot", False):
        await message.reply_html(
            "⚠️ <b>Specify a member to assassinate!</b>\n"
            "<i>Reply to their message or provide @username / user ID:</i>\n"
            "• <code>/kill @username</code>\n"
            "• <code>/kill 123456789</code>\n"
            "• <code>/kill</code> (by replying)"
        )
        return

    victim = target
    if victim.id == attacker.id:
        await message.reply_html("😅 Suicide is not allowed! Stay positive!")
        return

    now = time.time()
    if now - LAST_KILL_TIME.get(attacker.id, 0) < config.KILL_COOLDOWN_SECONDS:
        wait = max(1, int(config.KILL_COOLDOWN_SECONDS - (now - LAST_KILL_TIME.get(attacker.id, 0))))
        await message.reply_html(f"⏳ <b>Catch your breath!</b> Wait {wait}s before attacking again.")
        return
    LAST_KILL_TIME[attacker.id] = now

    attacker_data = await ensure_user(attacker)
    victim_data = await ensure_user(victim)

    if attacker_data.get("is_dead"):
        await check_auto_revive(attacker_data)
        if attacker_data.get("is_dead"):
            await message.reply_html("☠️ You are dead! Revive yourself first with <code>/revive</code>.")
            return

    if victim_data.get("is_dead"):
        await message.reply_html(f"☠️ {victim.mention_html()} is already dead! Let them rest.")
        return

    if await is_protected(victim.id):
        await message.reply_html(f"🛡️ {victim.mention_html()} has an active shield! Your attack bounced off!")
        return

    attacker_inv = attacker_data.get("inventory", [])
    victim_inv = victim_data.get("inventory", [])

    weapon_buff = sum(i["buff"] for i in config.SHOP_ITEMS if i["id"] in attacker_inv and i["type"] == "weapon")
    armor_buff = sum(i["buff"] for i in config.SHOP_ITEMS if i["id"] in victim_inv and i["type"] == "armor")

    base_chance = 0.60
    success_chance = min(0.85, max(0.25, base_chance + weapon_buff - armor_buff))
    roll = random.random()

    if roll <= success_chance:
        bounty = random.randint(100, 400)
        await set_user_dead(victim.id, True)
        await users_col.update_one({"user_id": attacker.id}, {"$inc": {"kills": 1, "balance": bounty}})
        await users_col.update_one({"user_id": victim.id}, {"$inc": {"deaths": 1}})

        weapons = ["a katana 🗡️", "a laser blaster ⚡", "a Kittu claw attack 🐾", "an AK-47 💥"]
        if "laser_blaster" in attacker_inv:
            weapons.append("a high-tech plasma laser ⚡🔫")
        if "sniper" in attacker_inv:
            weapons.append("a long-range 50-cal sniper rifle 🎯")
        chosen_weapon = random.choice(weapons)

        await message.reply_html(
            f"☠️ <b>ᴀssᴀssɪɴᴀᴛɪᴏɴ sᴜᴄᴄᴇssғᴜʟ!</b>\n\n"
            f"<blockquote>{attacker.mention_html()} eliminated {victim.mention_html()} using {chosen_weapon}!\n"
            f"💰 Bounty claimed: <b>+{bounty} Coins</b>.</blockquote>\n"
            f"🎋 <i>{victim.mention_html()} can revive with /revive.</i>"
        )
    else:
        penalty = 150
        await update_balance(attacker.id, -penalty)
        await message.reply_html(
            f"🛡️ <b>ᴀᴛᴛᴀᴄᴋ ғᴀɪʟᴇᴅ!</b>\n\n"
            f"<blockquote>{victim.mention_html()} dodged your strike! You tripped and lost <b>-{penalty} Coins</b>. 😂</blockquote>"
        )


async def rob_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    thief = update.effective_user
    if not message or not thief:
        return

    target, _ = await resolve_target_user(update, context)
    if not target or getattr(target, "is_bot", False):
        await message.reply_html(
            "⚠️ <b>Specify a member to rob!</b>\n"
            "<i>Reply to their message or provide @username / user ID:</i>\n"
            "• <code>/rob @username</code>\n"
            "• <code>/rob 123456789</code>\n"
            "• <code>/rob</code> (by replying)"
        )
        return

    victim = target
    if victim.id == thief.id:
        await message.reply_html("😂 You cannot rob yourself!")
        return

    now = time.time()
    if now - LAST_ROB_TIME.get(thief.id, 0) < 10:
        wait = max(1, int(10 - (now - LAST_ROB_TIME.get(thief.id, 0))))
        await message.reply_html(f"⏳ <b>Keep a low profile!</b> Wait {wait}s before another heist.")
        return
    LAST_ROB_TIME[thief.id] = now

    thief_data = await ensure_user(thief)
    victim_data = await ensure_user(victim)

    if thief_data.get("is_dead"):
        await message.reply_html("☠️ You are dead! Dead people cannot rob.")
        return

    if await is_protected(victim.id):
        await message.reply_html(f"🛡️ {victim.mention_html()} is protected by security shields!")
        return

    victim_bal = victim_data.get("balance", 0)
    if victim_bal < 200:
        await message.reply_html(f"🤷 {victim.mention_html()} is broke! Nothing to steal.")
        return

    victim_inv = victim_data.get("inventory", [])
    armor_buff = sum(i["buff"] for i in config.SHOP_ITEMS if i["id"] in victim_inv and i["type"] == "armor")
    base_rob_chance = 0.45
    rob_chance = max(0.20, base_rob_chance - armor_buff)

    if random.random() <= rob_chance:
        stolen = min(int(victim_bal * random.uniform(0.15, 0.35)), config.ROB_MAX_AMOUNT)
        await update_balance(victim.id, -stolen)
        await update_balance(thief.id, stolen)
        await message.reply_html(
            f"🥷 <b>ʜᴇɪsᴛ sᴜᴄᴄᴇssғᴜʟ!</b>\n\n"
            f"<blockquote>{thief.mention_html()} sneaked in and stole <b>{stolen:,} Coins</b> from {victim.mention_html()}! 💰</blockquote>"
        )
    else:
        fine = min(300, thief_data.get("balance", 0))
        await update_balance(thief.id, -fine)
        await update_balance(victim.id, fine)
        await message.reply_html(
            f"🚨 <b>ʙᴜsᴛᴇᴅ ʙʏ ᴘᴏʟɪᴄᴇ!</b>\n\n"
            f"<blockquote>{thief.mention_html()} got caught red-handed and paid <b>{fine:,} Coins</b> in damages to {victim.mention_html()}!</blockquote>"
        )


async def protect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return

    user_data = await ensure_user(user)

    days = 1
    if context.args and context.args[0] == "2":
        days = 2

    cost = config.PROTECT_1D_COST if days == 1 else config.PROTECT_2D_COST
    if user_data.get("balance", 0) < cost:
        await message.reply_html(f"❌ You need <b>{cost:,} Coins</b> for a {days}-day shield!")
        return

    await update_balance(user.id, -cost)
    await set_protection(user.id, days * 86400)

    await message.reply_html(
        f"🛡️ <b>sʜɪᴇʟᴅ ᴀᴄᴛɪᴠᴀᴛᴇᴅ!</b>\n\n"
        f"<blockquote>{user.mention_html()} is now immune to /kill and /rob for the next <b>{days} day(s)</b>! ✨</blockquote>"
    )


async def revive_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return

    target, _ = await resolve_target_user(update, context)
    if not target or getattr(target, "is_bot", False):
        target = user

    target_data = await ensure_user(target)

    if not target_data.get("is_dead"):
        msg = "You are already alive!" if target.id == user.id else f"{target.mention_html()} is already alive!"
        await message.reply_html(f"❤️ {msg}")
        return

    payer_data = await ensure_user(user)
    if payer_data.get("balance", 0) < config.REVIVE_COST:
        await message.reply_html(f"❌ Revive costs <b>{config.REVIVE_COST:,} Coins</b>!")
        return

    await update_balance(user.id, -config.REVIVE_COST)
    await set_user_dead(target.id, False)

    who = f"{user.mention_html()} revived themselves" if target.id == user.id else f"{user.mention_html()} generously revived {target.mention_html()}"
    await message.reply_html(
        f"✨ <b>ʀᴇᴠɪᴠᴇᴅ!</b>\n\n"
        f"<blockquote>{who} for <b>{config.REVIVE_COST} Coins</b>! 💖</blockquote>"
    )


from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from KITTUBOT.core.cleaner import track_menu, touch_menu


def get_games_hub_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚔️ ᴄᴏᴍʙᴀᴛ ʀᴘɢ", callback_data="gm_combat"),
            InlineKeyboardButton("🃏 ᴜɴᴏ & ʙᴏᴍʙ", callback_data="gm_cards"),
        ],
        [
            InlineKeyboardButton("🎰 ᴄᴀsɪɴᴏ ʜᴜʙ", callback_data="gm_casino"),
            InlineKeyboardButton("🔤 ᴡᴏʀᴅ ɢᴀᴍᴇs", callback_data="gm_words"),
        ],
        [
            InlineKeyboardButton("🛒 ᴀʀᴍᴏʀʏ sʜᴏᴘ", callback_data="gm_shop"),
            InlineKeyboardButton("❌ ᴄʟᴏsᴇ", callback_data="close_menu"),
        ]
    ])


async def games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    text = (
        "🎮 <b>ᴋɪᴛᴛᴜ ʙᴏᴛ — ɢᴀᴍᴇs & ᴇɴᴛᴇʀᴛᴀɪɴᴍᴇɴᴛ ʜᴜʙ</b> ✨\n\n"
        "<blockquote>ᴛᴀᴘ ᴀ ᴄᴀᴛᴇɢᴏʀʏ ʙᴇʟᴏᴡ ᴛᴏ ᴇxᴘʟᴏʀᴇ ʀᴜʟᴇs & ᴄᴏᴍᴍᴀɴᴅs:\n\n"
        "• ⚔️ <b>ᴄᴏᴍʙᴀᴛ ʀᴘɢ :</b> Assassinate, rob, shield & revive\n"
        "• 🃏 <b>ᴛᴀʙʟᴇ ɢᴀᴍᴇs :</b> Multiplayer UNO cards & Hot Potato Bomb\n"
        "• 🎰 <b>ᴄᴀsɪɴᴏ :</b> Blackjack, dice rolls, coinflip & slots\n"
        "• 🔤 <b>ᴡᴏʀᴅ ɢᴀᴍᴇs :</b> WordSeek, hangman, word chain & riddles\n"
        "• 🛒 <b>ᴀʀᴍᴏʀʏ :</b> High-tech weapons & cyber shields</blockquote>\n\n"
        "🎋 <i>Challenge your friends and build your empire!</i>"
    )
    keyboard = get_games_hub_keyboard()

    if update.callback_query:
        query = update.callback_query
        try:
            await query.answer()
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
            if chat:
                touch_menu(context, chat.id)
        except Exception:
            pass
    else:
        message = update.effective_message
        if message:
            sent = await message.reply_html(text, reply_markup=keyboard)
            if chat and chat.type != "private":
                await track_menu(context, chat.id, sent.message_id, auto_delete_seconds=180, is_group=True)


async def games_hub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    chat = update.effective_chat

    try:
        await query.answer()
    except Exception:
        pass

    back_btn = [
        [
            InlineKeyboardButton("🔙 ɢᴀᴍᴇs ᴍᴇɴᴜ", callback_data="gm_home"),
            InlineKeyboardButton("❌ ᴄʟᴏsᴇ", callback_data="close_menu"),
        ]
    ]

    if data == "gm_home":
        await games_menu(update, context)
        return

    elif data == "gm_combat":
        text = (
            "⚔️ <b>ᴄᴏᴍʙᴀᴛ ʀᴘɢ ᴀʀᴇɴᴀ</b>\n\n"
            "<blockquote>• <code>/kill</code> (reply) - Assassinate a player for bounty\n"
            "• <code>/rob</code> (reply) - Steal virtual coins from a player\n"
            "• <code>/protect [1|2]</code> - Buy 1h/2h invulnerability shield\n"
            "• <code>/revive</code> - Resurrect yourself or a fallen friend\n"
            "• <code>/shop</code> - Buy weapons & armor buffs</blockquote>\n\n"
            "🎋 <i>Weapons increase kill success, cyber armor blocks attacks!</i>"
        )
    elif data == "gm_cards":
        text = (
            "🃏 <b>ᴍᴜʟᴛɪᴘʟᴀʏᴇʀ ᴛᴀʙʟᴇ ɢᴀᴍᴇs</b>\n\n"
            "<blockquote>• <code>/uno [bet]</code> - Multiplayer UNO with official @unocards stickers!\n"
            "• <code>/unodeck &lt;theme&gt;</code> - Switch card visual pack (classic, minimal, etc.)\n"
            "• <code>/enduno</code> - Host can cancel and refund active UNO match\n"
            "• <code>/bomb [bet]</code> - Hot Potato Bomb match! Pass before fuse explodes!</blockquote>\n\n"
            "🎋 <i>Auto-ends games with full refunds if players go AFK.</i>"
        )
    elif data == "gm_casino":
        text = (
            "🎰 <b>ʜɪɢʜ-sᴛᴀᴋᴇs ᴄᴀsɪɴᴏ ʜᴜʙ</b>\n\n"
            "<blockquote>• <code>/blackjack [bet]</code> - 21 Card game vs Dealer (2.5x)\n"
            "• <code>/dice [bet]</code> - Roll Telegram physics dice (up to 2.5x)\n"
            "• <code>/dart [bet]</code> - Throw bullseye dart (up to 3.5x)\n"
            "• <code>/basket [bet]</code> - Shoot basketball hoop (2.0x)\n"
            "• <code>/slots [bet]</code> - 777 Animated slot machine (up to 10x)\n"
            "• <code>/coinflip [h|t] [bet]</code> - Golden coinflip (1.95x)</blockquote>"
        )
    elif data == "gm_words":
        text = (
            "🔤 <b>ᴡᴏʀᴅ & ʙʀᴀɪɴ ᴄʜᴀʟʟᴇɴɢᴇs</b>\n\n"
            "<blockquote>• <code>/words</code> - Word games hub menu\n"
            "• <code>/wordseek</code> or <code>/ws</code> - 5-Letter Wordle game\n"
            "• <code>/wsdaily</code> - Official daily wordle challenge\n"
            "• <code>/riddle</code> - Brain-teaser riddles with coin prizes\n"
            "• <code>/challenge</code> - Speed-typing banner contest</blockquote>"
        )
    elif data == "gm_shop":
        text = (
            "🛒 <b>ᴋɪᴛᴛᴜ ᴀʀᴍᴏʀʏ & ʙʟᴀᴄᴋ ᴍᴀʀᴋᴇᴛ</b>\n\n"
            "<blockquote>• <code>/shop</code> - Browse combat gear with 1-click buy buttons\n"
            "• <code>/buy &lt;item_id&gt;</code> - Purchase combat weapons or armor\n"
            "• <code>/inventory</code> - View your owned weapons & shields</blockquote>"
        )
    else:
        return

    try:
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(back_btn))
        if chat:
            touch_menu(context, chat.id)
    except Exception:
        pass


def register_handlers(app: Application):
    app.add_handler(CommandHandler("kill", kill_command))
    app.add_handler(CommandHandler("rob", rob_command))
    app.add_handler(CommandHandler("protect", protect_command))
    app.add_handler(CommandHandler("revive", revive_command))
    app.add_handler(CommandHandler(["game", "games"], games_menu))
    app.add_handler(CallbackQueryHandler(games_hub_callback, pattern=r"^gm_"))
