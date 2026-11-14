"""
Comprehensive Logic & Function Verification Test Suite.
Validates all core business logic, rate limits, away triggers, message filters,
Gemini history sanitizers, and conversation memory.
"""

import time
import unittest
import asyncio

from config import Config
from ai_engine import ConversationMemory, AIEngine, sanitize_gemini_turns
from filters import RateLimiter, AwayManager, MessageFilter, TELEGRAM_SERVICE_IDS

class TestConfigLogic(unittest.TestCase):
    """Verifies environment parsing, default values, and list sanitization."""

    def test_default_config_types(self):
        self.assertIsInstance(Config.BOT_MODE, str)
        self.assertIsInstance(Config.AUTO_REPLY_DELAY, float)
        self.assertIsInstance(Config.REPLY_COOLDOWN_SECONDS, int)
        self.assertIsInstance(Config.MAX_REPLIES_PER_HOUR, int)
        self.assertIsInstance(Config.SYSTEM_PROMPT, str)
        self.assertGreater(len(Config.SYSTEM_PROMPT), 10)

    def test_whitelist_parsing_logic(self):
        original = Config.WHITELIST_RAW
        try:
            Config.WHITELIST_RAW = " @Alice ,  bob , @Charlie_123, 100200300 "
            wl = Config.get_whitelist()
            self.assertIn("alice", wl)
            self.assertIn("bob", wl)
            self.assertIn("charlie_123", wl)
            self.assertIn("100200300", wl)
            self.assertEqual(len(wl), 4)

            # Test empty raw string
            Config.WHITELIST_RAW = "  "
            self.assertEqual(Config.get_whitelist(), set())
        finally:
            Config.WHITELIST_RAW = original

    def test_blacklist_parsing_logic(self):
        original = Config.BLACKLIST_RAW
        try:
            Config.BLACKLIST_RAW = "@Spam_Bot, ScamAccount, 999888777"
            bl = Config.get_blacklist()
            self.assertIn("spam_bot", bl)
            self.assertIn("scamaccount", bl)
            self.assertIn("999888777", bl)
            self.assertEqual(len(bl), 3)
        finally:
            Config.BLACKLIST_RAW = original


class TestConversationMemoryLogic(unittest.TestCase):
    """Verifies per-user session memory, sliding window, and TTL expiration."""

    def setUp(self):
        self.mem = ConversationMemory(max_history=3, ttl_seconds=2)

    def test_history_addition_and_retrieval(self):
        self.mem.add_message(101, "user", "Hello there")
        self.mem.add_message(101, "model", "General Kenobi!")
        
        hist = self.mem.get_history(101)
        self.assertEqual(len(hist), 2)
        self.assertEqual(hist[0], {"role": "user", "text": "Hello there"})
        self.assertEqual(hist[1], {"role": "model", "text": "General Kenobi!"})

    def test_sliding_window_truncation(self):
        # max_history is 3, which keeps at most 3*2 = 6 messages
        for i in range(8):
            self.mem.add_message(202, "user", f"Question {i}")
            self.mem.add_message(202, "model", f"Answer {i}")

        hist = self.mem.get_history(202)
        self.assertLessEqual(len(hist), 6)
        self.assertEqual(hist[-1]["text"], "Answer 7")
        self.assertEqual(hist[-2]["text"], "Question 7")

    def test_ttl_expiration(self):
        self.mem.add_message(303, "user", "Test message")
        self.assertEqual(len(self.mem.get_history(303)), 1)

        # Force timestamp back in time past the 2s TTL
        self.mem.sessions[303]["last_active"] = time.time() - 10
        self.assertEqual(len(self.mem.get_history(303)), 0)

    def test_clear_session(self):
        self.mem.add_message(404, "user", "Active conversation")
        self.mem.clear(404)
        self.assertEqual(len(self.mem.get_history(404)), 0)


class TestGeminiHistorySanitizer(unittest.TestCase):
    """Verifies Gemini multi-turn format constraints."""

    def test_ensures_user_is_first_turn(self):
        # If history started with a model turn, sanitizer must strip or skip it
        bad_history = [
            {"role": "model", "text": "Initial greeting"},
            {"role": "user", "text": "My question"},
            {"role": "model", "text": "My answer"}
        ]
        sanitized = sanitize_gemini_turns(bad_history, "Next question")
        self.assertEqual(sanitized[0]["role"], "user")
        self.assertEqual(sanitized[0]["parts"], ["My question"])

    def test_merges_consecutive_same_roles(self):
        # Gemini does not allow consecutive user turns: ['user', 'user']
        two_user_history = [
            {"role": "user", "text": "Part 1 of thought"},
            {"role": "user", "text": "Part 2 of thought"},
            {"role": "model", "text": "Combined answer"}
        ]
        sanitized = sanitize_gemini_turns(two_user_history, "Final question")
        self.assertEqual(sanitized[0]["role"], "user")
        self.assertEqual(sanitized[0]["parts"], ["Part 1 of thought", "Part 2 of thought"])
        self.assertEqual(sanitized[1]["role"], "model")
        self.assertEqual(sanitized[2]["role"], "user")


class TestAIEngineFallbacks(unittest.TestCase):
    """Verifies AI reply generation and fallback logic."""

    def test_graceful_fallback_without_api_keys(self):
        engine = AIEngine(provider="gemini", gemini_api_key="")
        reply = asyncio.run(engine.generate_reply(
            user_id=505,
            message_text="Hello, are you available for a project?",
            sender_name="Sarah"
        ))
        self.assertIsInstance(reply, str)
        self.assertIn("Sarah", reply)
        self.assertIn("Hello, are you available for a project?", reply)

    def test_empty_input_produces_empty_reply(self):
        engine = AIEngine(provider="gemini", gemini_api_key="")
        reply = asyncio.run(engine.generate_reply(
            user_id=505,
            message_text="   \n  \t ",
            sender_name="Sarah"
        ))
        self.assertEqual(reply, "")


class TestRateLimiter(unittest.TestCase):
    """Verifies cooldown intervals and hourly threshold limits."""

    def setUp(self):
        self.limiter = RateLimiter(cooldown_seconds=4, max_replies_per_hour=3)

    def test_cooldown_behavior(self):
        user_id = 1001
        # 1st request: permitted
        limited, _ = self.limiter.is_rate_limited(user_id)
        self.assertFalse(limited)
        self.limiter.record_reply(user_id)

        # Immediate 2nd request: blocked by cooldown
        limited, reason = self.limiter.is_rate_limited(user_id)
        self.assertTrue(limited)
        self.assertIn("Cooldown active", reason)

        # Simulate cooldown time elapsed
        self.limiter.last_reply_time[user_id] = time.time() - 5
        limited, _ = self.limiter.is_rate_limited(user_id)
        self.assertFalse(limited)

    def test_hourly_limit_behavior(self):
        user_id = 1002
        self.limiter.cooldown_seconds = 0 # Disable cooldown for this test

        for _ in range(3):
            limited, _ = self.limiter.is_rate_limited(user_id)
            self.assertFalse(limited)
            self.limiter.record_reply(user_id)

        # 4th request: blocked by hourly limit
        limited, reason = self.limiter.is_rate_limited(user_id)
        self.assertTrue(limited)
        self.assertIn("Max hourly limit reached", reason)

        # Simulate 1 hour passing
        self.limiter.reply_history[user_id] = [t - 3601 for t in self.limiter.reply_history[user_id]]
        limited, _ = self.limiter.is_rate_limited(user_id)
        self.assertFalse(limited)

    def test_disabled_limits(self):
        # 0 or negative should disable limiter
        disabled_limiter = RateLimiter(cooldown_seconds=0, max_replies_per_hour=0)
        for _ in range(10):
            limited, _ = disabled_limiter.is_rate_limited(1003)
            self.assertFalse(limited)
            disabled_limiter.record_reply(1003)


class TestMessageFilter(unittest.TestCase):
    """Verifies strict 1-on-1 private filtering, bot rejection, and blacklists."""

    def test_rejects_non_private_chats(self):
        should_reply, reason = MessageFilter.should_reply(
            is_private=False,
            is_self=False,
            is_bot=False,
            sender_id=123,
            username="user1",
            whitelist=set(),
            blacklist=set()
        )
        self.assertFalse(should_reply)
        self.assertIn("Not a private", reason)

    def test_rejects_self_messages(self):
        should_reply, reason = MessageFilter.should_reply(
            is_private=True,
            is_self=True,
            is_bot=False,
            sender_id=123,
            username="user1",
            whitelist=set(),
            blacklist=set()
        )
        self.assertFalse(should_reply)
        self.assertIn("Outgoing message from self", reason)

    def test_rejects_bot_senders(self):
        should_reply, reason = MessageFilter.should_reply(
            is_private=True,
            is_self=False,
            is_bot=True,
            sender_id=123,
            username="some_bot",
            whitelist=set(),
            blacklist=set()
        )
        self.assertFalse(should_reply)
        self.assertIn("Sender is a bot", reason)

    def test_rejects_telegram_official_service(self):
        for s_id in TELEGRAM_SERVICE_IDS:
            should_reply, reason = MessageFilter.should_reply(
                is_private=True,
                is_self=False,
                is_bot=False,
                sender_id=s_id,
                username="telegram",
                whitelist=set(),
                blacklist=set()
            )
            self.assertFalse(should_reply)
            self.assertIn("Telegram Official Service", reason)

    def test_blacklist_enforcement(self):
        blacklist = {"blocked_user", "888999"}
        # Test blocked by username
        should_reply, _ = MessageFilter.should_reply(
            is_private=True, is_self=False, is_bot=False,
            sender_id=111, username="blocked_user",
            whitelist=set(), blacklist=blacklist
        )
        self.assertFalse(should_reply)

        # Test blocked by user_id string
        should_reply, _ = MessageFilter.should_reply(
            is_private=True, is_self=False, is_bot=False,
            sender_id=888999, username="random_name",
            whitelist=set(), blacklist=blacklist
        )
        self.assertFalse(should_reply)

    def test_whitelist_enforcement(self):
        whitelist = {"vip_client", "777666"}
        
        # Allowed VIP user
        should_reply, _ = MessageFilter.should_reply(
            is_private=True, is_self=False, is_bot=False,
            sender_id=111, username="vip_client",
            whitelist=whitelist, blacklist=set()
        )
        self.assertTrue(should_reply)

        # Disallowed non-VIP user
        should_reply, reason = MessageFilter.should_reply(
            is_private=True, is_self=False, is_bot=False,
            sender_id=222, username="regular_user",
            whitelist=whitelist, blacklist=set()
        )
        self.assertFalse(should_reply)
        self.assertIn("not in whitelist", reason)

    def test_away_mode_filter(self):
        away_mgr = AwayManager(initially_away=False)
        
        # When AWAY_MODE_ONLY=True and status is ONLINE: should NOT reply
        should_reply, reason = MessageFilter.should_reply(
            is_private=True, is_self=False, is_bot=False,
            sender_id=111, username="friend",
            whitelist=set(), blacklist=set(),
            away_manager=away_mgr, away_mode_only=True
        )
        self.assertFalse(should_reply)
        self.assertIn("currently ONLINE", reason)

        # When status changes to AWAY: should reply!
        away_mgr.set_away("In an executive meeting")
        should_reply, _ = MessageFilter.should_reply(
            is_private=True, is_self=False, is_bot=False,
            sender_id=111, username="friend",
            whitelist=set(), blacklist=set(),
            away_manager=away_mgr, away_mode_only=True
        )
        self.assertTrue(should_reply)


class TestAwayManager(unittest.TestCase):
    """Verifies away mode state transitions and custom status messages."""

    def test_toggle_and_reason_updates(self):
        mgr = AwayManager(initially_away=False, default_reason="Out for lunch")
        self.assertFalse(mgr.is_away)

        mgr.set_away("Attending conference")
        self.assertTrue(mgr.is_away)
        self.assertEqual(mgr.reason, "Attending conference")

        mgr.set_back()
        self.assertFalse(mgr.is_away)

        new_state = mgr.toggle()
        self.assertTrue(new_state)
        self.assertTrue(mgr.is_away)


if __name__ == "__main__":
    unittest.main(verbosity=2)
