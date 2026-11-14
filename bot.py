"""
Official Telegram Bot Private Message AI Auto-Reply.
Runs via Telegram Bot API Token (from @BotFather) to handle private 1-on-1 chats.
Built using python-telegram-bot (v20+ async).
"""

import sys
import asyncio
import logging
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from config import Config
from ai_engine import AIEngine

logging.basicConfig(
    format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("TelegramBot")

ai = AIEngine(
    provider=Config.AI_PROVIDER,
    gemini_api_key=Config.GEMINI_API_KEY,
    gemini_model=Config.GEMINI_MODEL,
    openai_api_key=Config.OPENAI_API_KEY,
    openai_model=Config.OPENAI_MODEL,
    system_instruction=Config.SYSTEM_PROMPT
)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clears conversation context memory for this user."""
    user_id = update.effective_user.id
    ai.memory.clear(user_id)
    await update.message.reply_text("🧹 Conversation memory cleared! Let's start fresh.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reports status of the bot."""
    status_text = (
        f"🤖 **Bot Status: Online**\n\n"
        f"🧠 **AI Engine:** `{Config.AI_PROVIDER.upper()}`\n"
        f"⚡ **Model:** `{Config.GEMINI_MODEL if Config.AI_PROVIDER == 'gemini' else Config.OPENAI_MODEL}`\n"
        f"⏱️ **Typing Delay:** `{Config.AUTO_REPLY_DELAY}s`\n"
        f"🛡️ **Mode:** `Private 1-on-1 Message Auto-Reply`"
    )
    await update.message.reply_markdown(status_text)

async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes incoming 1-on-1 private messages and generates an AI response."""
    # 1. Enforce private chats only
    if update.effective_chat.type != "private":
        return

    user = update.effective_user
    user_id = user.id
    username = (user.username or "").lower()
    first_name = user.first_name or "Friend"
    message_text = update.message.text

    if not message_text or not message_text.strip():
        return

    # 2. Check blacklist
    blacklist = Config.get_blacklist()
    if username in blacklist or str(user_id) in blacklist:
        logger.info(f"Ignored blacklisted user: {username} (ID: {user_id})")
        return

    logger.info(f"[Private Message] From {first_name} (@{username or user_id}): \"{message_text}\"")

    try:
        # 3. Send typing indicator
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        
        if Config.AUTO_REPLY_DELAY > 0:
            await asyncio.sleep(Config.AUTO_REPLY_DELAY)

        # 4. Generate AI response
        reply_text = await ai.generate_reply(
            user_id=user_id,
            message_text=message_text,
            sender_name=first_name
        )

        if reply_text:
            await update.message.reply_text(reply_text)
            logger.info(f"[Replied to {first_name}]: \"{reply_text[:80]}...\"")

    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        await update.message.reply_text("I apologize, but I encountered an error processing your message.")

def main():
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
