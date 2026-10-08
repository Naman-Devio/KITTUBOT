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
from telegram.ext import Application, CommandHandler, ContextTypes
from KITTUBOT.config import config
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
• <code>/kill</code> - (ʀᴇᴘʟʏ) ᴀssᴀssɪɴᴀᴛᴇ ᴀ ᴍᴇᴍʙᴇʀ ғᴏʀ ʙᴏᴜɴᴛʏ
• <code>/rob</code> - (ʀᴇᴘʟʏ) sᴛᴇᴀʟ ᴄᴏɪɴs ғʀᴏᴍ ᴀ ᴘʟᴀʏᴇʀ
• <code>/protect [1|2]</code> - ʙᴜʏ ɪɴᴠᴜʟɴᴇʀᴀʙɪʟɪᴛʏ sʜɪᴇʟᴅ
• <code>/revive</code> - ʀᴇᴠɪᴠᴇ ʏᴏᴜʀsᴇʟғ ᴏʀ ᴀ ғᴀʟʟᴇɴ ғʀɪᴇɴᴅ
• <code>/game</code> - ᴠɪᴇᴡ ᴄᴏᴍʙᴀᴛ ɢᴀᴍᴇs ᴍᴇɴᴜ</blockquote>
"""


LAST_KILL_TIME: dict[int, float] = {}
LAST_ROB_TIME: dict[int, float] = {}


async def kill_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    attacker = update.effective_user
    reply = update.message.reply_to_message

    if not reply or not reply.from_user or reply.from_user.is_bot:
        await update.message.reply_html("⚠️ <b>Reply to a member</b> to attack them!")
        return

    now = time.time()
    if now - LAST_KILL_TIME.get(attacker.id, 0) < config.KILL_COOLDOWN_SECONDS:
        wait = max(1, int(config.KILL_COOLDOWN_SECONDS - (now - LAST_KILL_TIME.get(attacker.id, 0))))
        await update.message.reply_html(f"⏳ <b>Catch your breath!</b> Wait {wait}s before attacking again.")
        return
    LAST_KILL_TIME[attacker.id] = now

    victim = reply.from_user
    if victim.id == attacker.id:
        await update.message.reply_html("😅 Suicide is not allowed! Stay positive!")
        return

    attacker_data = await ensure_user(attacker)
    victim_data = await ensure_user(victim)

    if attacker_data.get("is_dead"):
        await check_auto_revive(attacker_data)
        if attacker_data.get("is_dead"):
            await update.message.reply_html("☠️ You are dead! Revive yourself first with <code>/revive</code>.")
            return

    if victim_data.get("is_dead"):
        await update.message.reply_html(f"☠️ {victim.mention_html()} is already dead! Let them rest.")
        return

    if await is_protected(victim.id):
        await update.message.reply_html(f"🛡️ {victim.mention_html()} has an active shield! Your attack bounced off!")
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

        await update.message.reply_html(
            f"☠️ <b>ᴀssᴀssɪɴᴀᴛɪᴏɴ sᴜᴄᴄᴇssғᴜʟ!</b>\n\n"
            f"<blockquote>{attacker.mention_html()} eliminated {victim.mention_html()} using {chosen_weapon}!\n"
            f"💰 Bounty claimed: <b>+{bounty} Coins</b>.</blockquote>\n"
            f"🎋 <i>{victim.mention_html()} can revive with /revive.</i>"
        )
    else:
        penalty = 150
        await update_balance(attacker.id, -penalty)
        await update.message.reply_html(
            f"🛡️ <b>ᴀᴛᴛᴀᴄᴋ ғᴀɪʟᴇᴅ!</b>\n\n"
            f"<blockquote>{victim.mention_html()} dodged your strike! You tripped and lost <b>-{penalty} Coins</b>. 😂</blockquote>"
        )


async def rob_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    thief = update.effective_user
    reply = update.message.reply_to_message

    if not reply or not reply.from_user or reply.from_user.is_bot:
        await update.message.reply_html("⚠️ <b>Reply to a member</b> to rob them!")
        return

    victim = reply.from_user
    if victim.id == thief.id:
        await update.message.reply_html("😂 You cannot rob yourself!")
        return

    now = time.time()
    if now - LAST_ROB_TIME.get(thief.id, 0) < 10:
        wait = max(1, int(10 - (now - LAST_ROB_TIME.get(thief.id, 0))))
        await update.message.reply_html(f"⏳ <b>Keep a low profile!</b> Wait {wait}s before another heist.")
        return
    LAST_ROB_TIME[thief.id] = now

    thief_data = await ensure_user(thief)
    victim_data = await ensure_user(victim)

    if thief_data.get("is_dead"):
        await update.message.reply_html("☠️ You are dead! Dead people cannot rob.")
        return

    if await is_protected(victim.id):
        await update.message.reply_html(f"🛡️ {victim.mention_html()} is protected by security shields!")
        return

    victim_bal = victim_data.get("balance", 0)
    if victim_bal < 200:
        await update.message.reply_html(f"🤷 {victim.mention_html()} is broke! Nothing to steal.")
        return

    victim_inv = victim_data.get("inventory", [])
    armor_buff = sum(i["buff"] for i in config.SHOP_ITEMS if i["id"] in victim_inv and i["type"] == "armor")
    base_rob_chance = 0.45
    rob_chance = max(0.20, base_rob_chance - armor_buff)

    if random.random() <= rob_chance:
        stolen = min(int(victim_bal * random.uniform(0.15, 0.35)), config.ROB_MAX_AMOUNT)
        await update_balance(victim.id, -stolen)
        await update_balance(thief.id, stolen)
        await update.message.reply_html(
            f"🥷 <b>ʜᴇɪsᴛ sᴜᴄᴄᴇssғᴜʟ!</b>\n\n"
            f"<blockquote>{thief.mention_html()} sneaked in and stole <b>{stolen:,} Coins</b> from {victim.mention_html()}! 💰</blockquote>"
        )
    else:
        fine = min(300, thief_data.get("balance", 0))
        await update_balance(thief.id, -fine)
        await update_balance(victim.id, fine)
        await update.message.reply_html(
            f"🚨 <b>ʙᴜsᴛᴇᴅ ʙʏ ᴘᴏʟɪᴄᴇ!</b>\n\n"
            f"<blockquote>{thief.mention_html()} got caught red-handed and paid <b>{fine:,} Coins</b> in damages to {victim.mention_html()}!</blockquote>"
        )


async def protect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = await ensure_user(user)

    days = 1
    if context.args and context.args[0] == "2":
        days = 2

    cost = config.PROTECT_1D_COST if days == 1 else config.PROTECT_2D_COST
    if user_data.get("balance", 0) < cost:
        await update.message.reply_html(f"❌ You need <b>{cost:,} Coins</b> for a {days}-day shield!")
        return

    await update_balance(user.id, -cost)
    await set_protection(user.id, days * 86400)

    await update.message.reply_html(
        f"🛡️ <b>sʜɪᴇʟᴅ ᴀᴄᴛɪᴠᴀᴛᴇᴅ!</b>\n\n"
        f"<blockquote>{user.mention_html()} is now immune to /kill and /rob for the next <b>{days} day(s)</b>! ✨</blockquote>"
    )


async def revive_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    reply = update.message.reply_to_message

    target = reply.from_user if (reply and reply.from_user and not reply.from_user.is_bot) else user
    target_data = await ensure_user(target)

    if not target_data.get("is_dead"):
        msg = "You are already alive!" if target.id == user.id else f"{target.mention_html()} is already alive!"
        await update.message.reply_html(f"❤️ {msg}")
        return

    payer_data = await ensure_user(user)
    if payer_data.get("balance", 0) < config.REVIVE_COST:
        await update.message.reply_html(f"❌ Revive costs <b>{config.REVIVE_COST:,} Coins</b>!")
        return

    await update_balance(user.id, -config.REVIVE_COST)
    await set_user_dead(target.id, False)

    who = f"{user.mention_html()} revived themselves" if target.id == user.id else f"{user.mention_html()} generously revived {target.mention_html()}"
    await update.message.reply_html(
        f"✨ <b>ʀᴇᴠɪᴠᴇᴅ!</b>\n\n"
        f"<blockquote>{who} for <b>{config.REVIVE_COST} Coins</b>! 💖</blockquote>"
    )


async def games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        "🎮 <b>ᴋɪᴛᴛᴜ ʙᴏᴛ — ɢᴀᴍᴇs & ᴇɴᴛᴇʀᴛᴀɪɴᴍᴇɴᴛ ʜᴜʙ</b>\n\n"
        "<blockquote>⚔️ <b>ᴄᴏᴍʙᴀᴛ ʀᴘɢ:</b>\n"
        "• <code>/kill</code> - Eliminate group members & collect bounties\n"
        "• <code>/rob</code> - Heist coins from members\n"
        "• <code>/protect</code> - Buy shields against assassination\n"
        "• <code>/revive</code> - Bring fallen players back to life\n"
        "• <code>/shop</code> - Buy weapons & cyber armor\n\n"
        "🃏 <b>ᴍᴜʟᴛɪᴘʟᴀʏᴇʀ ᴛᴀʙʟᴇ ɢᴀᴍᴇs:</b>\n"
        "• <code>/uno [bet]</code> - Multiplayer UNO cards with @unocards stickers\n"
        "• <code>/bomb [bet]</code> - Hot Potato Bomb knockout\n"
        "• <code>/words</code> - Word chain, unscramble, emoji guess, hangman & quiz\n"
        "• <code>/riddle</code> - Brain-teaser quizzes with coin prizes</blockquote>\n\n"
        "🎋 <i>Challenge your friends and build your empire!</i>"
    )


def register_handlers(app: Application):
    app.add_handler(CommandHandler("kill", kill_command))
    app.add_handler(CommandHandler("rob", rob_command))
    app.add_handler(CommandHandler("protect", protect_command))
    app.add_handler(CommandHandler("revive", revive_command))
    app.add_handler(CommandHandler("game", games_menu))
