"""
bot/app.py
──────────
Entry point. Starts the Telegram bot using polling (no public URL needed).
Handles 409 Conflict by force-closing any existing polling connection first.
"""

import os
import sys
import time
import logging
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────
Path("./logs").mkdir(exist_ok=True)

LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("./logs/bot.log"),
    ],
)
log = logging.getLogger("quiz-bot")

from bot.bot import build_app


def force_close_existing_connections(token: str):
    """
    Use plain HTTP requests (no asyncio) to evict any lingering polling connection
    on Telegram's side before we start our own. Resolves 409 Conflict on restart.
    """
    base = f"https://api.telegram.org/bot{token}"
    log.info("🔌 Clearing any existing polling connections...")
    try:
        requests.post(f"{base}/deleteWebhook", json={"drop_pending_updates": True}, timeout=10)
        # A short getUpdates call steals the slot from any lingering instance
        requests.post(f"{base}/getUpdates", json={"offset": -1, "timeout": 1}, timeout=5)
        log.info("✅ Connection slot cleared.")
    except Exception as e:
        log.warning("⚠️  Could not clear existing connections: %s", e)
    time.sleep(2)  # give Telegram a moment to release the slot


def main():
    log.info("✈️  Aircraft Engineer Quiz Bot starting...")

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        log.error("❌ TELEGRAM_BOT_TOKEN not set in .env")
        sys.exit(1)

    allowed = os.getenv("TELEGRAM_ALLOWED_CHAT_ID", "")
    if allowed and allowed != "REPLACE_WITH_YOUR_PRIVATE_GROUP_CHAT_ID":
        log.info("🔒 Sandboxed to chat ID: %s", allowed)
    else:
        log.warning("⚠️  No TELEGRAM_ALLOWED_CHAT_ID set — bot will respond to anyone")

    # Force-close any lingering connection (pure HTTP, no asyncio conflict)
    force_close_existing_connections(token)

    app = build_app()
    log.info("🚀 Bot running via polling. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True, bootstrap_retries=5)


if __name__ == "__main__":
    main()
