# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Economy System
Coins, Bank Deposits/Withdrawals, Daily Rewards, Transfers, Leaderboards & Wealth stats.
"""

import time
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from KITTUBOT.config import config
from KITTUBOT.database.users import (
    ensure_user,
    get_user,
    update_balance,
    get_top_rich,
    deposit_to_bank,
    withdraw_from_bank,
)

__mod_name__ = "Economy"
__help__ = """
<blockquote>💰 <b>ᴇᴄᴏɴᴏᴍʏ ᴄᴏᴍᴍᴀɴᴅs:</b>
• <code>/bal</code> - ᴄʜᴇᴄᴋ ᴄᴏɪɴ ʙᴀʟᴀɴᴄᴇ & ᴡᴇᴀʟᴛʜ
• <code>/daily</code> - ᴄʟᴀɪᴍ ᴅᴀɪʟʏ ᴄᴏɪɴs (ᴇᴠᴇʀʏ 12ʜ)
• <code>/dep [amt|all]</code> - sᴀᴠᴇ ᴄᴏɪɴs ɪɴ ʙᴀɴᴋ (sᴀғᴇ ғʀᴏᴍ /rob)
• <code>/with [amt|all]</code> - ᴡɪᴛʜᴅʀᴀᴡ ᴄᴏɪɴs ғʀᴏᴍ ʙᴀɴᴋ
• <code>/give [amt]</code> - (ʀᴇᴘʟʏ) ᴛʀᴀɴsғᴇʀ ᴄᴏɪɴs
• <code>/toprich</code> - ᴠɪᴇᴡ ᴛᴏᴘ 10 ʀɪᴄʜᴇsᴛ ᴛʏᴄᴏᴏɴs
• <code>/economy</code> - ᴇᴄᴏɴᴏᴍʏ ᴏᴠᴇʀᴠɪᴇᴡ & sᴛᴀᴛs</blockquote>
"""


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = await ensure_user(user)

    await update.message.reply_html(
        f"💳 <b>{user.mention_html()}'s ᴡᴀʟʟᴇᴛ</b>\n\n"
        f"<blockquote>🪙 <b>ᴄᴏɪɴs:</b> <code>{data.get('balance', 0):,}</code>\n"
        f"🏦 <b>ʙᴀɴᴋ:</b> <code>{data.get('bank', 0):,}</code>\n"
        f"⚔️ <b>ᴋɪʟʟs:</b> <code>{data.get('kills', 0)}</code> | ☠️ <b>ᴅᴇᴀᴛʜs:</b> <code>{data.get('deaths', 0)}</code></blockquote>"
    )


async def daily_bonus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = await ensure_user(user)

    last_daily = data.get("last_daily", 0)
    cooldown = config.BONUS_COOLDOWN_HOURS * 3600
    elapsed = time.time() - last_daily

    if elapsed < cooldown:
        rem_seconds = int(cooldown - elapsed)
        rem_hours = rem_seconds // 3600
        rem_mins = (rem_seconds % 3600) // 60
        await update.message.reply_html(
            f"⏳ <b>Already Claimed!</b>\n"
            f"<blockquote>You can claim your daily coins again in <b>{rem_hours}h {rem_mins}m</b>.</blockquote>"
        )
        return

    from KITTUBOT.database import users_col
    await users_col.update_one(
        {"user_id": user.id},
        {"$set": {"last_daily": time.time()}, "$inc": {"balance": config.DAILY_BONUS}},
    )

    await update.message.reply_html(
        f"🎁 <b>ᴅᴀɪʟʏ ʀᴇᴡᴀʀᴅ ᴄʟᴀɪᴍᴇᴅ!</b>\n\n"
        f"<blockquote>ʏᴏᴜ ʀᴇᴄᴇɪᴠᴇᴅ <b>+{config.DAILY_BONUS:,} ᴄᴏɪɴs</b>! 🪙\n"
        f"ᴄᴏᴍᴇ ʙᴀᴄᴋ ɪɴ {config.BONUS_COOLDOWN_HOURS} ʜᴏᴜʀs ғᴏʀ ᴍᴏʀᴇ!</blockquote>"
    )


async def deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = await ensure_user(user)
    bal = data.get("balance", 0)

    if not context.args:
        await update.message.reply_html("⚠️ <b>Specify amount or 'all'!</b> E.g. <code>/dep 500</code> or <code>/dep all</code>")
        return

    arg = context.args[0].lower()
    if arg == "all":
        amount = bal
    elif arg.isdigit():
        amount = int(arg)
    else:
        await update.message.reply_html("⚠️ Invalid amount entered!")
        return

    if amount <= 0:
        await update.message.reply_html("⚠️ Amount must be greater than zero!")
        return

    if bal < amount:
        await update.message.reply_html(f"❌ You only have <b>{bal:,} coins</b> in your wallet!")
        return

    success = await deposit_to_bank(user.id, amount)
    if success:
        await update.message.reply_html(
            f"🏦 <b>ᴅᴇᴘᴏsɪᴛ sᴜᴄᴄᴇssғᴜʟ!</b>\n\n"
            f"<blockquote>Deposited <b>{amount:,} Coins</b> into your Bank!\n"
            f"<i>Banked coins cannot be stolen by thieves via /rob!</i> 🛡️</blockquote>"
        )
    else:
        await update.message.reply_html("❌ Transaction failed! Check your balance.")


async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = await ensure_user(user)
    bank_bal = data.get("bank", 0)

    if not context.args:
        await update.message.reply_html("⚠️ <b>Specify amount or 'all'!</b> E.g. <code>/with 500</code> or <code>/with all</code>")
        return

    arg = context.args[0].lower()
    if arg == "all":
        amount = bank_bal
    elif arg.isdigit():
        amount = int(arg)
    else:
        await update.message.reply_html("⚠️ Invalid amount entered!")
        return

    if amount <= 0:
        await update.message.reply_html("⚠️ Amount must be greater than zero!")
        return

    if bank_bal < amount:
        await update.message.reply_html(f"❌ You only have <b>{bank_bal:,} coins</b> in your bank!")
        return

    success = await withdraw_from_bank(user.id, amount)
    if success:
        await update.message.reply_html(
            f"🏧 <b>ᴡɪᴛʜᴅʀᴀᴡ sᴜᴄᴄᴇssғᴜʟ!</b>\n\n"
            f"<blockquote>Withdrew <b>{amount:,} Coins</b> from Bank to your wallet! 🪙</blockquote>"
        )
    else:
        await update.message.reply_html("❌ Transaction failed! Check your bank balance.")


from KITTUBOT.core.permissions import resolve_target_user


async def give_coins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    target, rem_args = await resolve_target_user(update, context)

    if not target or (target.user and target.user.is_bot):
        await update.message.reply_html(
            "⚠️ <b>Specify the user to send coins to!</b>\n"
            "<i>Reply to their message or provide @username / user ID:</i>\n"
            "• <code>/give @username [amount]</code>\n"
            "• <code>/give 123456789 [amount]</code>\n"
            "• <code>/give [amount]</code> (by replying)"
        )
        return

    if target.id == user.id:
        await update.message.reply_html("😂 You cannot give coins to yourself!")
        return

    amount = None
    for arg in rem_args:
        if arg.isdigit():
            amount = int(arg)
            break

    if amount is None or amount <= 0:
        await update.message.reply_html("⚠️ Specify the amount! Example: <code>/give @username 500</code>")
        return

    sender_data = await ensure_user(user)
    if sender_data.get("balance", 0) < amount:
        await update.message.reply_html(f"❌ You only have <b>{sender_data.get('balance', 0):,} coins</b>!")
        return

    await update_balance(user.id, -amount)
    await update_balance(target.id, amount)

    await update.message.reply_html(
        f"💸 <b>ᴛʀᴀɴsғᴇʀ sᴜᴄᴄᴇssғᴜʟ!</b>\n\n"
        f"<blockquote>{user.mention_html()} transferred <b>{amount:,} Coins</b> to {target.mention_html()}! 🤝</blockquote>"
    )


async def toprich_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rich_users = await get_top_rich(limit=10)
    if not rich_users:
        await update.message.reply_html("No wealthy members recorded yet.")
        return

    text = "🏆 <b>ᴋɪᴛᴛᴜ ʙᴏᴛ — ᴛᴏᴘ 10 ʀɪᴄʜᴇsᴛ ᴛʏᴄᴏᴏɴs</b>\n\n<blockquote>"
    for idx, u in enumerate(rich_users, start=1):
        name = u.get("first_name", "Unknown")
        bal = u.get("balance", 0) + u.get("bank", 0)
        medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
        text += f"{medal} <b>{name}</b> — <code>{bal:,} coins</code>\n"
    text += "</blockquote>"

    await update.message.reply_html(text)


async def economy_overview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        "🏛️ <b>ᴋɪᴛᴛᴜ ᴄᴇɴᴛʀᴀʟ ᴇᴄᴏɴᴏᴍʏ</b>\n\n"
        f"<blockquote>• <b>Starting Bonus:</b> {config.REGISTER_BONUS:,} Coins\n"
        f"• <b>Daily Bonus:</b> {config.DAILY_BONUS:,} Coins\n"
        f"• <b>Riddle Bounty:</b> {config.RIDDLE_REWARD:,} Coins\n"
        f"• <b>Revive Cost:</b> {config.REVIVE_COST:,} Coins\n"
        f"• <b>Bank Vault:</b> Deposit coins via /dep to stay safe from /rob!</blockquote>\n\n"
        "🎋 <i>Use /daily, /shop, /bal, /dep, /with, and /toprich to build your fortune!</i>"
    )


def register_handlers(app: Application):
    app.add_handler(CommandHandler(["bal", "balance"], balance_command))
    app.add_handler(CommandHandler("daily", daily_bonus_command))
    app.add_handler(CommandHandler(["dep", "deposit"], deposit_command))
    app.add_handler(CommandHandler(["with", "withdraw"], withdraw_command))
    app.add_handler(CommandHandler(["give", "pay"], give_coins_command))
    app.add_handler(CommandHandler("toprich", toprich_command))
    app.add_handler(CommandHandler("economy", economy_overview))
