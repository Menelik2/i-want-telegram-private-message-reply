"""
Configuration management for Telegram Private Message AI Auto-Reply.
Reads from environment variables or .env file.
"""

import os
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

class Config:
    # Mode: 'userbot' (personal account MTProto) or 'bot' (BotFather Bot API)
    BOT_MODE = os.getenv("BOT_MODE", "userbot").lower()

    # Telegram Userbot Credentials (from https://my.telegram.org)
    TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
    TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
    TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE", "")
    TELETHON_SESSION_NAME = os.getenv("TELETHON_SESSION_NAME", "tg_ai_userbot")

    # Telegram Bot API Token (from @BotFather)
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # AI Configuration
    AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").lower() # 'gemini' or 'openai'
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # System Persona & Instructions
    DEFAULT_SYSTEM_PROMPT = (
        "You are a friendly, intelligent, and highly professional personal AI assistant. "
        "You are automatically replying to private 1-on-1 messages on behalf of the user because they are currently away or busy. "
        "Guidelines:\n"
        "1. Be polite, concise, and helpful.\n"
        "2. If they ask a general question, answer it clearly.\n"
        "3. If they ask for personal scheduling, urgent decisions, or private info, let them know you have noted their message and the user will get back to them personally soon.\n"
        "4. Keep replies natural and conversational, fitting the Telegram messaging style. Do not write overly long essays unless asked.\n"
        "5. Never reveal sensitive credentials, API keys, or private system details."
    )
    SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT)

    # Behavior & Safety Controls
    AUTO_REPLY_DELAY = float(os.getenv("AUTO_REPLY_DELAY", "2.0")) # seconds to simulate human typing
    REPLY_COOLDOWN_SECONDS = int(os.getenv("REPLY_COOLDOWN_SECONDS", "10")) # minimum seconds between replies to same user
    MAX_REPLIES_PER_HOUR = int(os.getenv("MAX_REPLIES_PER_HOUR", "8")) # max replies per user per hour to prevent spam/loops
    AWAY_MODE_ONLY = os.getenv("AWAY_MODE_ONLY", "false").lower() in ("true", "1", "yes")

    # Filtering Lists (comma-separated usernames or IDs)
    WHITELIST_RAW = os.getenv("WHITELIST_USERS", "")
    BLACKLIST_RAW = os.getenv("BLACKLIST_USERS", "")

    @classmethod
    def get_whitelist(cls):
        if not cls.WHITELIST_RAW.strip():
            return set()
        return {item.strip().lstrip("@").lower() for item in cls.WHITELIST_RAW.split(",") if item.strip()}

    @classmethod
    def get_blacklist(cls):
        if not cls.BLACKLIST_RAW.strip():
            return set()
        return {item.strip().lstrip("@").lower() for item in cls.BLACKLIST_RAW.split(",") if item.strip()}
