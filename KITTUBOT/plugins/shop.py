# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Shop & Armory Plugin
Purchase weapons, cyber armor, and protective items with in-game currency.
Equipped with visual stats bars, rarity badges & one-click inline purchase buttons.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from KITTUBOT.config import config
from KITTUBOT.database.users import ensure_user, update_balance
from KITTUBOT.database import users_col

__mod_name__ = "Shop"
__help__ = """
<blockquote>🛒 <b>ᴋɪᴛᴛᴜ ᴀʀᴍᴏʀʏ & ʙʟᴀᴄᴋ ᴍᴀʀᴋᴇᴛ:</b>
• <code>/shop</code> - ʙʀᴏᴡsᴇ ᴡᴇᴀᴘᴏɴs & ᴄʏʙᴇʀ ᴀʀᴍᴏʀ ᴡɪᴛʜ ɪɴʟɪɴᴇ ʙᴜʏ
• <code>/buy [id]</code> - ᴘᴜʀᴄʜᴀsᴇ ᴀɴ ɪᴛᴇᴍ ғʀᴏᴍ ᴀʀᴍᴏʀʏ
• <code>/inventory</code> - ᴠɪᴇᴡ ʏᴏᴜʀ ᴏᴡɴᴇᴅ ɢᴇᴀʀ & ᴄᴏᴍʙᴀᴛ sᴛᴀᴛs</blockquote>
"""


def render_stat_bar(buff: float) -> str:
    """Renders a visual 10-segment stat bar."""
    filled = min(10, max(1, int(buff * 25)))
    return "█" * filled + "░" * (10 - filled)


async def shop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🛒 <b>ᴋɪᴛᴛᴜ ᴀʀᴍᴏʀʏ & ʙʟᴀᴄᴋ ᴍᴀʀᴋᴇᴛ</b> ✨\n\n"

    buttons = []
    text += "<blockquote>⚔️ <b>ᴄᴏᴍʙᴀᴛ ᴡᴇᴀᴘᴏɴs (ᴀᴛᴛᴀᴄᴋ ʙᴜғғs):</b>\n"
    for item in config.SHOP_ITEMS:
        if item["type"] == "weapon":
            bar = render_stat_bar(item["buff"])
            text += f"• <b>{item['name']}</b> (<code>{item['id']}</code>)\n  └ <code>{bar}</code> +{int(item['buff']*100)}% DMG • <b>{item['price']:,} coins</b>\n"
            buttons.append(InlineKeyboardButton(f"🗡️ Buy {item['name'].split()[0]} ({item['price']:,})", callback_data=f"buy_{item['id']}"))

    text += "\n🛡️ <b>ᴄʏʙᴇʀ ᴀʀᴍᴏʀ (ᴅᴇғᴇɴsᴇ sʜɪᴇʟᴅs):</b>\n"
    for item in config.SHOP_ITEMS:
        if item["type"] == "armor":
            bar = render_stat_bar(item["buff"])
            text += f"• <b>{item['name']}</b> (<code>{item['id']}</code>)\n  └ <code>{bar}</code> +{int(item['buff']*100)}% DEF • <b>{item['price']:,} coins</b>\n"
            buttons.append(InlineKeyboardButton(f"🛡️ Buy {item['name'].split()[0]} ({item['price']:,})", callback_data=f"buy_{item['id']}"))
    text += "</blockquote>\n"

    text += "🎋 <i>Tap an item button below to purchase instantly, or use <code>/buy &lt;id&gt;</code>!</i>"

    # Pair buttons 2 per row
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    keyboard = InlineKeyboardMarkup(rows)

    await update.message.reply_html(text, reply_markup=keyboard)


async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    item_id = query.data.split("_")[1]
    user = update.effective_user

    item = next((i for i in config.SHOP_ITEMS if i["id"] == item_id), None)
    if not item:
        try:
            await query.answer("Item no longer available!", show_alert=True)
        except Exception:
            pass
        return

    user_data = await ensure_user(user)
    if user_data.get("balance", 0) < item["price"]:
        try:
            await query.answer(f"❌ You need {item['price']:,} Coins! Balance too low.", show_alert=True)
        except Exception:
            pass
        return

    inventory = user_data.get("inventory", [])
    if item_id in inventory:
        try:
            await query.answer(f"⚠️ You already own {item['name']}!", show_alert=True)
        except Exception:
            pass
        return

    await update_balance(user.id, -item["price"])
    await users_col.update_one({"user_id": user.id}, {"$push": {"inventory": item_id}})

    try:
        await query.answer(f"🎉 Purchased {item['name']} for {item['price']:,} Coins!", show_alert=True)
        await query.message.reply_html(
            f"🎉 <b>ᴘᴜʀᴄʜᴀsᴇ sᴜᴄᴄᴇssғᴜʟ!</b> 🛍️\n\n"
            f"<blockquote>{user.mention_html()} acquired <b>{item['name']}</b> for <b>{item['price']:,} Coins</b>!\n"
            f"Equipped into active combat loadout! ⚔️</blockquote>"
        )
    except Exception:
        pass


async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_html("⚠️ <b>Specify the item ID!</b> Example: <code>/buy pistol</code>")
        return

    item_id = context.args[0].lower()
    item = next((i for i in config.SHOP_ITEMS if i["id"] == item_id), None)
    if not item:
        await update.message.reply_html("❌ <b>Item not found!</b> Type <code>/shop</code> to see available gear.")
        return

    user_data = await ensure_user(user)
    if user_data.get("balance", 0) < item["price"]:
        await update.message.reply_html(
            f"❌ <b>Insufficient funds!</b> You need <b>{item['price']:,} Coins</b>."
        )
        return

    # Check if already owned
    inventory = user_data.get("inventory", [])
    if item_id in inventory:
        await update.message.reply_html(f"⚠️ You already own <b>{item['name']}</b>!")
        return

    await update_balance(user.id, -item["price"])
    await users_col.update_one({"user_id": user.id}, {"$push": {"inventory": item_id}})

    await update.message.reply_html(
        f"🎉 <b>ᴘᴜʀᴄʜᴀsᴇ sᴜᴄᴄᴇssғᴜʟ!</b>\n\n"
        f"<blockquote>ʏᴏᴜ ᴀᴄǫᴜɪʀᴇᴅ <b>{item['name']}</b> ғᴏʀ <b>{item['price']:,} ᴄᴏɪɴs</b>! ⚔️</blockquote>"
    )


async def inventory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = await ensure_user(user)
    inv = user_data.get("inventory", [])

    if not inv:
        await update.message.reply_html("🎒 <b>Your inventory is empty!</b> Visit <code>/shop</code> to buy gear.")
        return

    text = f"🎒 <b>{user.mention_html()}'s ᴄᴏᴍʙᴀᴛ ɪɴᴠᴇɴᴛᴏʀʏ:</b>\n\n<blockquote>"
    total_atk = 0
    total_def = 0
    for item_id in inv:
        found = next((i for i in config.SHOP_ITEMS if i["id"] == item_id), None)
        if found:
            bar = render_stat_bar(found["buff"])
            icon = "⚔️" if found["type"] == "weapon" else "🛡️"
            if found["type"] == "weapon":
                total_atk += int(found["buff"] * 100)
            else:
                total_def += int(found["buff"] * 100)
            text += f"• {icon} <b>{found['name']}</b>\n  └ <code>{bar}</code> +{int(found['buff']*100)}%\n"
        else:
            text += f"• 📦 <b>{item_id}</b>\n"

    text += f"\n📊 <b>ᴛᴏᴛᴀʟ ᴄᴏᴍʙᴀᴛ ʙᴜғғs:</b>\n⚔️ ATK: <code>+{total_atk}%</code> | 🛡️ DEF: <code>+{total_def}%</code></blockquote>"

    await update.message.reply_html(text)


def register_handlers(app: Application):
    app.add_handler(CommandHandler("shop", shop_command))
    app.add_handler(CommandHandler("buy", buy_command))
    app.add_handler(CommandHandler(["inventory", "inv"], inventory_command))
    app.add_handler(CallbackQueryHandler(buy_callback, pattern=r"^buy_\w+$"))
