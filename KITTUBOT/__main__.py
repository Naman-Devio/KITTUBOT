# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Primary Application Runner
Built on python-telegram-bot v22 (Pure Async Concurrency Engine).
Zero worker starvation, rock-solid uptime.
"""

import sys
import telegram.error
from telegram import BotCommand, Update
from telegram.ext import ApplicationBuilder, Application
from telegram.request import HTTPXRequest

from KITTUBOT.config import config
from KITTUBOT.database import init_db
from KITTUBOT.plugins import load_all_plugins
from KITTUBOT import log, __bot_name__, __version__


async def post_init(application: Application):
    """Sets Telegram bot command suggestions and initializes database."""
    await init_db()

    commands = [
        BotCommand("start", "Launch Kittu Bot & view menu"),
        BotCommand("help", "Browse all commands & features"),
        BotCommand("ping", "Check bot latency & uptime"),
        BotCommand("bal", "View your coins & wealth"),
        BotCommand("daily", "Claim daily bonus coins"),
        BotCommand("grab", "Claim spawned anime character"),
        BotCommand("harem", "View your waifu collection"),
        BotCommand("dice", "Roll casino animated dice"),
        BotCommand("slots", "Spin 777 slot machine"),
        BotCommand("blackjack", "Play 21 card game vs dealer"),
        BotCommand("uno", "Play multiplayer UNO cards"),
        BotCommand("bomb", "Hot potato multiplayer bomb"),
        BotCommand("kill", "Attack a member in group"),
        BotCommand("rob", "Attempt to steal coins"),
        BotCommand("words", "Word chain & unscramble games"),
        BotCommand("wordseek", "Play WordSeek / Wordle word game"),
        BotCommand("ranking", "View your chat rank & XP tier"),
        BotCommand("grouprank", "View group activity leaderboard"),
        BotCommand("challenge", "Speed-typing poster contest"),
        BotCommand("shop", "Open weapons & gear shop"),
        BotCommand("ban", "Ban a member from group"),
        BotCommand("warn", "Issue strike warning to user"),
        BotCommand("purge", "Bulk delete chat messages"),
        BotCommand("q", "Generate quote sticker on reply"),
        BotCommand("afk", "Set away from keyboard status"),
        BotCommand("anime", "Search anime synopsis & score"),
        BotCommand("tts", "Convert text to voice message"),
        BotCommand("dl", "Download video from social media"),
    ]
    try:
        await application.bot.set_my_commands(commands)
        bot_info = await application.bot.get_me()
        log.info(f"Bot connected: @{bot_info.username} (ID: {bot_info.id})")
        log.info(f"Commands menu registered with Telegram.")
    except Exception as e:
        log.warning(f"Failed to set bot commands: {e}")


async def error_handler(update, context):
    """Logs unhandled exceptions gracefully without crashing or dropping updates."""
    if isinstance(context.error, telegram.error.NetworkError):
        log.warning(f"Telegram network glitch (auto-retrying): {context.error}")
        return
    log.error(f"Update '{update}' caused error: {context.error}", exc_info=context.error)
    try:
        from KITTUBOT.plugins.logger import log_crash_error
        import asyncio
        asyncio.create_task(log_crash_error(context.bot, update, context.error))
    except Exception as e:
        log.warning(f"Failed to forward crash report to logger channel: {e}")


def main():
    if not config.BOT_TOKEN:
        log.critical("FATAL: BOT_TOKEN is missing! Set it in your .env file.")
        sys.exit(1)

    log.info(f"Initializing {__bot_name__} v{__version__}...")

    # Stable HTTP/1.1 connection pool with generous timeouts
    request = HTTPXRequest(
        connection_pool_size=50,
        connect_timeout=20.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=5.0,
        http_version="1.1",
    )

    app = (
        ApplicationBuilder()
        .token(config.BOT_TOKEN)
        .request(request)
        .post_init(post_init)
        .concurrent_updates(True)  # True async concurrent task spawning
        .build()
    )

    # Global error handler
    app.add_error_handler(error_handler)

    # Auto-load all modular plugins
    load_all_plugins(app)

    log.info(f"{__bot_name__} is now live and polling for updates!")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
