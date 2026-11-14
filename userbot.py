"""
Telegram Personal Account Private Message AI Auto-Reply (Userbot).
Runs on your personal Telegram account to automatically reply to 1-on-1 private messages (DMs).
Built using Telethon (Telegram MTProto Client).
"""

import os
import sys
import time
import asyncio
import logging

from config import Config
from ai_engine import AIEngine
from filters import RateLimiter, MessageFilter, AwayManager

# Configure logging
logging.basicConfig(
    format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("Userbot")

# Initialize managers
rate_limiter = RateLimiter(
    cooldown_seconds=Config.REPLY_COOLDOWN_SECONDS,
    max_replies_per_hour=Config.MAX_REPLIES_PER_HOUR
)
away_manager = AwayManager(
    initially_away=Config.AWAY_MODE_ONLY,
    default_reason="Currently away from Telegram"
)
ai = AIEngine(
    provider=Config.AI_PROVIDER,
    gemini_api_key=Config.GEMINI_API_KEY,
    gemini_model=Config.GEMINI_MODEL,
    openai_api_key=Config.OPENAI_API_KEY,
    openai_model=Config.OPENAI_MODEL,
    system_instruction=Config.SYSTEM_PROMPT
)

async def main():
    try:
        from telethon import TelegramClient, events
        from telethon.tl.types import User
        from telethon.errors import FloodWaitError
    except ImportError:
        logger.error("=" * 60)
        logger.error("MISSING DEPENDENCY: Telethon is not installed!")
        logger.error("Please install dependencies: pip install -r requirements.txt")
        logger.error("=" * 60)
        sys.exit(1)

    if not Config.TELEGRAM_API_ID or not Config.TELEGRAM_API_HASH:
        logger.error("=" * 60)
        logger.error("MISSING CREDENTIALS!")
        logger.error("Please set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env")
        logger.error("Get them from: https://my.telegram.org -> API development tools")
        logger.error("=" * 60)
        sys.exit(1)

    logger.info("Initializing Telegram Client...")
    client = TelegramClient(
        Config.TELETHON_SESSION_NAME,
        Config.TELEGRAM_API_ID,
        Config.TELEGRAM_API_HASH
    )

    # Start client
    await client.start(phone=Config.TELEGRAM_PHONE if Config.TELEGRAM_PHONE else None)
    me = await client.get_me()

    logger.info("=" * 60)
    logger.info("Telegram AI Private Message Userbot Connected!")
    logger.info(f"Logged in as: {me.first_name} (@{me.username or 'No Username'}, ID: {me.id})")
    logger.info(f"AI Provider: {Config.AI_PROVIDER.upper()}")
    logger.info(f"Typing Delay: {Config.AUTO_REPLY_DELAY}s | Cooldown: {Config.REPLY_COOLDOWN_SECONDS}s")
    logger.info(f"Max Replies/Hour: {Config.MAX_REPLIES_PER_HOUR} | Away Only: {Config.AWAY_MODE_ONLY}")
    logger.info("Commands available in your Telegram: .status, .away, .back, .help")
    logger.info("Listening exclusively for incoming PRIVATE messages (DMs)...")
    logger.info("=" * 60)

    # -------------------------------------------------------------
    # 1. OUTGOING SELF-COMMANDS (.status, .away, .back, .help)
    # -------------------------------------------------------------
    @client.on(events.NewMessage(outgoing=True))
    async def on_self_command(event):
        text = (event.raw_text or "").strip()
        if not text.startswith("."):
            return

        cmd = text.split()[0].lower()
        args = text[len(cmd):].strip()

        if cmd == ".status":
            status_report = (
                f"🤖 **Telegram AI Auto-Reply Status**\n\n"
                f"• **Status:** `{'AWAY' if away_manager.is_away else 'ONLINE'}`\n"
                f"• **Reason:** `{away_manager.reason}`\n"
                f"• **AI Engine:** `{Config.AI_PROVIDER.upper()}`\n"
                f"• **Typing Delay:** `{Config.AUTO_REPLY_DELAY}s`\n"
                f"• **Cooldown:** `{Config.REPLY_COOLDOWN_SECONDS}s`\n"
                f"• **Hourly Limit:** `{Config.MAX_REPLIES_PER_HOUR}/hr`\n"
                f"• **Scope:** `Private 1-on-1 Messages Only`"
            )
            await event.edit(status_report)

        elif cmd == ".away":
            reason = args if args else "Away from Telegram"
            away_manager.set_away(reason)
            await event.edit(f"💤 **Away Mode ACTIVATED**\nReason: _{reason}_\nAuto-reply will now respond to private DMs.")

        elif cmd == ".back":
            away_manager.set_back()
            await event.edit("🟢 **Away Mode DEACTIVATED**\nStatus is now ONLINE.")

        elif cmd == ".help":
            help_text = (
                "🛠️ **AI Userbot Commands (Send in any chat or Saved Messages):**\n\n"
                "• `.status` - Check current bot status and limits\n"
                "• `.away [reason]` - Enable away auto-reply mode\n"
                "• `.back` - Disable away mode (set status to online)\n"
                "• `.help` - Show this commands manual"
            )
            await event.edit(help_text)

    # -------------------------------------------------------------
    # 2. INCOMING PRIVATE MESSAGES AUTO-REPLY
    # -------------------------------------------------------------
    @client.on(events.NewMessage(incoming=True))
    async def on_private_message(event):
        try:
            # 1. Validate sender and message type using MessageFilter
            sender = await event.get_sender()
            is_bot = getattr(sender, "bot", False) if sender else False
            sender_id = sender.id if sender else 0
            username = getattr(sender, "username", None) if sender else None
            first_name = getattr(sender, "first_name", "Friend") or "Friend"

            whitelist = Config.get_whitelist()
            blacklist = Config.get_blacklist()

            should_reply, reason = MessageFilter.should_reply(
                is_private=event.is_private,
                is_self=event.out,
                is_bot=is_bot,
                sender_id=sender_id,
                username=username,
                whitelist=whitelist,
                blacklist=blacklist,
                away_manager=away_manager,
                away_mode_only=Config.AWAY_MODE_ONLY
            )

            if not should_reply:
                # Silently skip non-qualifying messages
                return

            message_text = (event.raw_text or "").strip()
            if not message_text:
                return

            # 2. Rate Limit & Cooldown Check
            is_limited, limit_reason = rate_limiter.is_rate_limited(sender_id)
            if is_limited:
                logger.info(f"Rate limited user {first_name} (ID: {sender_id}): {limit_reason}")
                return

            logger.info(f"[Private DM] From {first_name} (@{username or sender_id}): \"{message_text}\"")

            # 3. Simulate human typing action
            async with client.action(event.chat_id, 'typing'):
                if Config.AUTO_REPLY_DELAY > 0:
                    await asyncio.sleep(Config.AUTO_REPLY_DELAY)

                # 4. Generate AI response
                reply_text = await ai.generate_reply(
                    user_id=sender_id,
                    message_text=message_text,
                    sender_name=first_name
                )

            if not reply_text:
                return

            # 5. Send reply
            await event.reply(reply_text)
            rate_limiter.record_reply(sender_id)
            logger.info(f"[Auto-Replied to {first_name}]: \"{reply_text[:80]}...\"")

        except FloodWaitError as e:
            logger.warning(f"Telegram FloodWaitError: sleeping for {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)

    # Keep userbot running
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Userbot stopped by user.")
