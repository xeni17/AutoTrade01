"""
main.py — Entry point for Smart Money Bot
"""

import sys
from loguru import logger
from dotenv import load_dotenv
import os

load_dotenv()

# Setup logging
log_level = os.getenv("LOG_LEVEL", "INFO")
log_file = os.getenv("LOG_FILE", "logs/bot.log")

logger.remove()
logger.add(sys.stdout, level=log_level, colorize=True,
           format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
logger.add(log_file, level="DEBUG", rotation="10 MB", retention="7 days")

from src.core.bot import SmartMoneyBot

if __name__ == "__main__":
    bot = SmartMoneyBot()
    bot.run()
