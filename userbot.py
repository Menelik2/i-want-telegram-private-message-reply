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
from collections import defaultdict
from telethon import TelegramClient, events
from telethon.tl.types import User

from config import Config
from ai_engine import AIEngine

# Configure logging
logging.basicConfig(
    format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("Userbot")

# Track per-user reply activity for rate-limiting
# user_id -> [timestamps of replies in the last hour]
reply_history = defaultdict(list)
last_reply_time = {}

# Initialize AI Engine
ai = AIEngine(
    provider=Config.AI_PROVIDER,
    gemini_api_key=Config.GEMINI_API_KEY,
    gemini_model=Config.GEMINI_MODEL,
    openai_api_key=Config.OPENAI_API_KEY,
    openai_model=Config.OPENAI_MODEL,
    system_instruction=Config.SYSTEM_PROMPT
)

def is_rate_limited(user_id: int) -> bool:
    """Checks if a user has exceeded rate limits or is on cooldown."""
    now = time.time()
    
    # 1. Check minimum cooldown between replies
    if user_id in last_reply_time:
        if now - last_reply_time[user_id] < Config.REPLY_COOLDOWN_SECONDS:
            logger.info(f"Rate limiter: User {user_id} is in cooldown period ({Config.REPLY_COOLDOWN_SECONDS}s).")
            return True

    # 2. Check maximum replies per hour
    one_hour_ago = now - 3600
    # Clean up old timestamps
    reply_history[user_id] = [t for t in reply_history[user_id] if t > one_hour_ago]

    if len(reply_history[user_id]) >= Config.MAX_REPLIES_PER_HOUR:
        logger.warning(f"Rate limiter: User {user_id} reached max replies per hour ({Config.MAX_REPLIES_PER_HOUR}).")
        return True

    return False

def record_reply(user_id: int):
    """Records that a reply was just sent to the user."""
    now = time.time()
    last_reply_time[user_id] = now
    reply_history[user_id].append(now)

async def main():
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

    # Start the client (prompts for phone & code on first run if session file doesn't exist)
    await client.start(phone=Config.TELEGRAM_PHONE if Config.TELEGRAM_PHONE else None)
    
    me = await client.get_me()
    logger.info("=" * 60)
    logger.info(f"Telegram AI Private Message Userbot Connected!")
    logger.info(f"Logged in as: {me.first_name} (@{me.username or 'No Username'}, ID: {me.id})")
    logger.info(f"AI Provider: {Config.AI_PROVIDER.upper()}")
    logger.info(f"Auto-reply delay: {Config.AUTO_REPLY_DELAY}s | Cooldown: {Config.REPLY_COOLDOWN_SECONDS}s")
    logger.info(f"Max replies per user/hr: {Config.MAX_REPLIES_PER_HOUR}")
    logger.info("Listening exclusively for incoming PRIVATE messages (DMs)...")
    logger.info("=" * 60)

    whitelist = Config.get_whitelist()
    blacklist = Config.get_blacklist()

    @client.on(events.NewMessage(incoming=True))
    async def on_private_message(event):
        try:
            # 1. Strictly ignore anything that is NOT a 1-on-1 private message
            if not event.is_private:
                return

            # 2. Never reply to your own messages
            if event.out:
                return

            # 3. Get sender details
            sender = await event.get_sender()
            if not isinstance(sender, User):
                return

            # 4. Never reply to bots (prevents loop accidents)
            if sender.bot:
                logger.info(f"Ignoring message from bot: @{sender.username or sender.id}")
                return

            sender_id = sender.id
            username = (sender.username or "").lower()
            first_name = sender.first_name or "Friend"

            # 5. Blacklist filter
            if username in blacklist or str(sender_id) in blacklist:
                logger.info(f"Ignored blacklisted user: {username} (ID: {sender_id})")
                return

            # 6. Whitelist filter (if whitelist is configured, only reply to whitelisted users)
            if whitelist and (username not in whitelist and str(sender_id) not in whitelist):
                logger.info(f"User {username} (ID: {sender_id}) not in whitelist. Skipping.")
                return

            # 7. Check message text content
            message_text = event.raw_text
            if not message_text or not message_text.strip():
                # Ignore empty messages, stickers without text, or pure media
                return

            # 8. Check rate limiting & cooldown
            if is_rate_limited(sender_id):
                return

            logger.info(f"[Private DM] From {first_name} (@{username or sender_id}): \"{message_text}\"")

            # 9. Simulate human typing action
            async with client.action(event.chat_id, 'typing'):
                if Config.AUTO_REPLY_DELAY > 0:
                    await asyncio.sleep(Config.AUTO_REPLY_DELAY)

                # 10. Generate AI Reply
                reply_text = await ai.generate_reply(
                    user_id=sender_id,
                    message_text=message_text,
                    sender_name=first_name
                )

            if not reply_text:
                return

            # 11. Send reply to the private message
            await event.reply(reply_text)
            record_reply(sender_id)
            logger.info(f"[Auto-Replied to {first_name}]: \"{reply_text[:80]}...\"")

        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)

    # Run the userbot indefinitely until disconnected
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Userbot stopped by user.")
