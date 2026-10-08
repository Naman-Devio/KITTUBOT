# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
🐾 KITTUBOT Plugin Loader & Registry
Drop-in modular architecture: Drop any plugin.py here and it auto-registers.
"""

import os
import importlib
from telegram.ext import Application
from KITTUBOT import log

HELP_MODULES: dict[str, str] = {}


def load_all_plugins(application: Application):
    """Automatically loads all plugins in this package."""
    current_dir = os.path.dirname(__file__)
    loaded_count = 0

    for file in sorted(os.listdir(current_dir)):
        if file.endswith(".py") and not file.startswith("__"):
            module_name = file[:-3]
            try:
                mod = importlib.import_module(f"KITTUBOT.plugins.{module_name}")
                if hasattr(mod, "register_handlers"):
                    mod.register_handlers(application)
                    loaded_count += 1

                mod_name = getattr(mod, "__mod_name__", None)
                mod_help = getattr(mod, "__help__", None)
                if mod_name and mod_help:
                    HELP_MODULES[mod_name] = mod_help

                log.info(f"Loaded plugin: {module_name}")
            except Exception as e:
                log.exception(f"Failed to load plugin {module_name}: {e}")

    log.info(f"Successfully loaded {loaded_count} KITTUBOT plugins.")
