# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT — The Next-Gen Telegram AI Companion, Game Hub & Group Manager
Built on python-telegram-bot v22 (Pure Async, High Concurrency)
"""

import logging
import time
from datetime import datetime
import pytz

__version__ = "3.0.0"
__bot_name__ = "Kittu Bot"

START_TIME = time.time()
IST = pytz.timezone("Asia/Kolkata")
START_TIME_STR = datetime.now(IST).strftime("%d-%b-%Y %I:%M:%S %p")

# Clean, structured logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] [%(name)s]: %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
    ],
)

# Quiet down chatty external loggers
for noisy in ("httpx", "httpcore", "telegram", "apscheduler", "pymongo"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

log = logging.getLogger("KITTUBOT")
