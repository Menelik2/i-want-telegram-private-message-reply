"""
Official Telegram Bot Private Message AI Auto-Reply.
Runs via Telegram Bot API Token (from @BotFather) to handle private 1-on-1 chats.
Built using python-telegram-bot (v20+ async).
"""

import sys
import asyncio
import logging

from config import Config
from ai_engine import AIEngine
from filters import RateLimiter, MessageFilter

logging.basicConfig(
    format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("TelegramBot")

# Initialize Rate Limiter & AI Engine
rate_limiter = RateLimiter(
    cooldown_seconds=Config.REPLY_COOLDOWN_SECONDS,
    max_replies_per_hour=Config.MAX_REPLIES_PER_HOUR
)
ai = AIEngine(
    provider=Config.AI_PROVIDER,
    gemini_api_key=Config.GEMINI_API_KEY,
    gemini_model=Config.GEMINI_MODEL,
    openai_api_key=Config.OPENAI_API_KEY,
    openai_model=Config.OPENAI_MODEL,
    system_instruction=Config.SYSTEM_PROMPT
)

async def start_command(update, context):
    """Handles the /start command."""
    user = update.effective_user
    welcome_text = (
        f"👋 Hello {user.first_name}!\n\n"
        f"I am an AI assistant here to reply to your private messages and questions.\n\n"
        f"💬 Send me any message or question, and I'll assist you immediately.\n"
        f"🔄 Use /clear to reset our conversation memory.\n"
        f"ℹ️ Use /status to see active AI engine configuration."
    )
    await update.message.reply_text(welcome_text)

async def clear_command(update, context):
    """Clears conversation context memory for this user."""
    user_id = update.effective_user.id
    ai.memory.clear(user_id)
    rate_limiter.reset_user(user_id)
    await update.message.reply_text("🧹 Conversation memory and rate limits cleared! Let's start fresh.")

async def status_command(update, context):
    """Reports status of the bot."""
    status_text = (
        f"🤖 **Bot Status: Online**\n\n"
        f"• **AI Engine:** `{Config.AI_PROVIDER.upper()}`\n"
        f"• **Model:** `{Config.GEMINI_MODEL if Config.AI_PROVIDER == 'gemini' else Config.OPENAI_MODEL}`\n"
        f"• **Typing Delay:** `{Config.AUTO_REPLY_DELAY}s`\n"
        f"• **Cooldown:** `{Config.REPLY_COOLDOWN_SECONDS}s`\n"
        f"• **Hourly Limit:** `{Config.MAX_REPLIES_PER_HOUR}/hr`\n"
        f"• **Mode:** `Private 1-on-1 Message Auto-Reply`"
    )
    await update.message.reply_markdown(status_text)

async def handle_private_message(update, context):
    """Processes incoming 1-on-1 private messages and generates an AI response."""
    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return

    is_private = chat.type == "private"
    is_bot = getattr(user, "is_bot", False)
    user_id = user.id
    username = user.username
    first_name = user.first_name or "Friend"
    message_text = (update.message.text or "").strip()

    if not message_text:
        return

    # Filter checks (whitelist, blacklist, bot check, private check)
    whitelist = Config.get_whitelist()
    blacklist = Config.get_blacklist()

    should_reply, reason = MessageFilter.should_reply(
        is_private=is_private,
        is_self=False,
        is_bot=is_bot,
        sender_id=user_id,
        username=username,
        whitelist=whitelist,
        blacklist=blacklist
    )

    if not should_reply:
        logger.info(f"Skipping message from {first_name} (ID: {user_id}): {reason}")
        return

    # Rate limiting check
    is_limited, limit_reason = rate_limiter.is_rate_limited(user_id)
    if is_limited:
        logger.info(f"Rate limited user {first_name} (ID: {user_id}): {limit_reason}")
        return

    logger.info(f"[Private Message] From {first_name} (@{username or user_id}): \"{message_text}\"")

    try:
        from telegram.constants import ChatAction
        # Typing indicator
        await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.TYPING)
        
        if Config.AUTO_REPLY_DELAY > 0:
            await asyncio.sleep(Config.AUTO_REPLY_DELAY)

        # Generate AI response
        reply_text = await ai.generate_reply(
            user_id=user_id,
            message_text=message_text,
            sender_name=first_name
        )

        if reply_text:
            await update.message.reply_text(reply_text)
            rate_limiter.record_reply(user_id)
            logger.info(f"[Replied to {first_name}]: \"{reply_text[:80]}...\"")

    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        await update.message.reply_text("I apologize, but I encountered an error processing your message.")

def main():
    try:
        from telegram import Update
        from telegram.ext import (
            Application,
            CommandHandler,
            MessageHandler,
            ContextTypes,
            filters
        )
    except ImportError:
        logger.error("=" * 60)
        logger.error("MISSING DEPENDENCY: python-telegram-bot is not installed!")
        logger.error("Please install: pip install -r requirements.txt")
        logger.error("=" * 60)
        sys.exit(1)

    if not Config.TELEGRAM_BOT_TOKEN:
        logger.error("=" * 60)
        logger.error("MISSING TELEGRAM_BOT_TOKEN!")
        logger.error("Please set TELEGRAM_BOT_TOKEN in .env")
        logger.error("Get your token by messaging @BotFather on Telegram")
        logger.error("=" * 60)
        sys.exit(1)

    logger.info("Starting Telegram Bot Application...")
    app = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("status", status_command))

    # Listen only to private text messages (excluding commands)
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT & (~filters.COMMAND),
        handle_private_message
    ))

    logger.info(f"Bot started! Polling for private messages... (AI: {Config.AI_PROVIDER.upper()})")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
