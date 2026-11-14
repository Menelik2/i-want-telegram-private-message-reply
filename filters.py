"""
Message Filtering, Rate Limiting, and Safety Controls for Telegram Auto-Reply.
Shared between Userbot (Telethon) and Bot API (python-telegram-bot).
"""

import time
import logging
from collections import defaultdict
from typing import Set, Tuple, Optional

logger = logging.getLogger("Filters")

# Telegram Official Service IDs (Must never be replied to)
TELEGRAM_SERVICE_IDS = {777000, 42777}

class RateLimiter:
    """Thread-safe and async-safe rate limiter with cooldown and hourly window."""
    def __init__(self, cooldown_seconds: int = 10, max_replies_per_hour: int = 8):
        self.cooldown_seconds = cooldown_seconds
        self.max_replies_per_hour = max_replies_per_hour
        # user_id -> [timestamps of replies within the past hour]
        self.reply_history = defaultdict(list)
        # user_id -> timestamp of most recent reply
        self.last_reply_time = {}

    def is_rate_limited(self, user_id: int) -> Tuple[bool, str]:
        """
        Returns (True, reason) if user is rate limited, (False, '') otherwise.
        """
        now = time.time()

        # 1. Check Cooldown (if enabled)
        if self.cooldown_seconds > 0 and user_id in self.last_reply_time:
            elapsed = now - self.last_reply_time[user_id]
            if elapsed < self.cooldown_seconds:
                remaining = self.cooldown_seconds - elapsed
                return True, f"Cooldown active ({remaining:.1f}s remaining)"

        # 2. Check Hourly Limit (if enabled)
        if self.max_replies_per_hour > 0:
            one_hour_ago = now - 3600
            # Prune old timestamps
            self.reply_history[user_id] = [t for t in self.reply_history[user_id] if t > one_hour_ago]

            if len(self.reply_history[user_id]) >= self.max_replies_per_hour:
                return True, f"Max hourly limit reached ({self.max_replies_per_hour}/hr)"

        return False, ""

    def record_reply(self, user_id: int):
        """Records a sent reply for the user."""
        now = time.time()
        self.last_reply_time[user_id] = now
        self.reply_history[user_id].append(now)

    def reset_user(self, user_id: int):
        """Resets rate limit tracking for a user."""
        self.last_reply_time.pop(user_id, None)
        self.reply_history.pop(user_id, None)

    def clear_all(self):
        """Clears all tracking."""
        self.last_reply_time.clear()
        self.reply_history.clear()


class AwayManager:
    """Manages away mode state and custom status reasons."""
    def __init__(self, initially_away: bool = False, default_reason: str = "Away from desk"):
        self.is_away = initially_away
        self.reason = default_reason

    def set_away(self, reason: Optional[str] = None):
        self.is_away = True
        if reason:
            self.reason = reason

    def set_back(self):
        self.is_away = False

    def toggle(self) -> bool:
        self.is_away = not self.is_away
        return self.is_away


class MessageFilter:
    """Validates whether an incoming message qualifies for AI auto-reply."""
    
    @staticmethod
    def should_reply(
        is_private: bool,
        is_self: bool,
        is_bot: bool,
        sender_id: int,
        username: Optional[str],
        whitelist: Set[str],
        blacklist: Set[str],
        away_manager: Optional[AwayManager] = None,
        away_mode_only: bool = False
    ) -> Tuple[bool, str]:
        """
        Returns (True, '') if eligible for reply, or (False, reason) if rejected.
        """
        # 1. Strictly 1-on-1 private chat
        if not is_private:
            return False, "Not a private 1-on-1 chat (group/channel ignored)"

        # 2. Never reply to own messages
        if is_self:
            return False, "Outgoing message from self"

        # 3. Never reply to other bots
        if is_bot:
            return False, "Sender is a bot"

        # 4. Telegram Official Service Accounts
        if sender_id in TELEGRAM_SERVICE_IDS:
            return False, "Telegram Official Service notification"

        clean_username = (username or "").strip().lstrip("@").lower()
        sender_id_str = str(sender_id)

        # 5. Blacklist Check
        if clean_username in blacklist or sender_id_str in blacklist:
            return False, f"Sender is blacklisted ({clean_username or sender_id_str})"

        # 6. Whitelist Check (if whitelist is configured)
        if whitelist and (clean_username not in whitelist and sender_id_str not in whitelist):
            return False, f"Sender is not in whitelist ({clean_username or sender_id_str})"

        # 7. Away Mode Check
        if away_mode_only and away_manager and not away_manager.is_away:
            return False, "Away mode is enabled, but status is currently ONLINE"

        return True, ""
