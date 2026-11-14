"""
Comprehensive Test Suite for Telegram Private Message AI Auto-Reply
Tests all functions, logic branches, rate-limiters, memory managers, and filters.
"""

import os
import sys
import time
import unittest
import asyncio

# Import project modules
from config import Config
from ai_engine import ConversationMemory, AIEngine
import userbot

class TestConfig(unittest.TestCase):
    """Tests configuration loading, sanitization, and parsing."""
    
    def test_default_values(self):
        self.assertIn(Config.BOT_MODE, ["userbot", "bot"])
        self.assertIn(Config.AI_PROVIDER, ["gemini", "openai"])
        self.assertGreaterEqual(Config.AUTO_REPLY_DELAY, 0.0)
        self.assertGreaterEqual(Config.REPLY_COOLDOWN_SECONDS, 0)
        self.assertGreaterEqual(Config.MAX_REPLIES_PER_HOUR, 0)
        self.assertTrue(len(Config.DEFAULT_SYSTEM_PROMPT) > 20)

    def test_whitelist_parsing(self):
        # Test parsing with @ symbols, spaces, uppercase
        original = Config.WHITELIST_RAW
        try:
            Config.WHITELIST_RAW = " @Alice , Bob, @Charlie_123, 987654321 "
            wl = Config.get_whitelist()
            self.assertIn("alice", wl)
            self.assertIn("bob", wl)
            self.assertIn("charlie_123", wl)
            self.assertIn("987654321", wl)
            self.assertEqual(len(wl), 4)

            # Empty whitelist test
            Config.WHITELIST_RAW = "   "
            self.assertEqual(Config.get_whitelist(), set())
        finally:
            Config.WHITELIST_RAW = original

    def test_blacklist_parsing(self):
        original = Config.BLACKLIST_RAW
        try:
            Config.BLACKLIST_RAW = "@SpamBot, bad_actor, 112233"
            bl = Config.get_blacklist()
            self.assertIn("spambot", bl)
            self.assertIn("bad_actor", bl)
            self.assertIn("112233", bl)
            self.assertEqual(len(bl), 3)
        finally:
            Config.BLACKLIST_RAW = original


class TestConversationMemory(unittest.TestCase):
    """Tests conversation history, truncation, and TTL expiration."""

    def setUp(self):
        self.mem = ConversationMemory(max_history=3, ttl_seconds=2)

    def test_add_and_retrieve_messages(self):
        self.mem.add_message(101, "user", "Hello")
        self.mem.add_message(101, "model", "Hi there!")
        
        history = self.mem.get_history(101)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0], {"role": "user", "text": "Hello"})
        self.assertEqual(history[1], {"role": "model", "text": "Hi there!"})

    def test_max_history_truncation(self):
        # max_history is 3 turns (3 user + 3 model = 6 messages max)
        for i in range(5):
            self.mem.add_message(202, "user", f"User msg {i}")
            self.mem.add_message(202, "model", f"Bot reply {i}")

        history = self.mem.get_history(202)
        # Should be truncated to max_history * 2 = 6 messages
        self.assertLessEqual(len(history), 6)
        # The latest message should be the last one added
        self.assertEqual(history[-1]["text"], "Bot reply 4")

    def test_ttl_expiration(self):
        self.mem.add_message(303, "user", "Initial message")
        self.assertEqual(len(self.mem.get_history(303)), 1)
        
        # Simulate time passing beyond TTL (ttl_seconds=2)
        # Directly modify last_active to 5 seconds ago
        self.mem.sessions[303]["last_active"] = time.time() - 5
        
        # Should now be expired and reset to empty
        history = self.mem.get_history(303)
        self.assertEqual(len(history), 0)

    def test_clear_memory(self):
        self.mem.add_message(404, "user", "Test clear")
        self.assertEqual(len(self.mem.get_history(404)), 1)
        self.mem.clear(404)
        self.assertEqual(len(self.mem.get_history(404)), 0)


class TestAIEngine(unittest.TestCase):
    """Tests the AI engine responses, system prompts, and fallbacks."""

    def test_fallback_response_without_keys(self):
        engine = AIEngine(
            provider="gemini",
            gemini_api_key="",
            system_instruction="You are a helpful assistant."
        )
        reply = asyncio.run(engine.generate_reply(
            user_id=123,
            message_text="Can we schedule a call?",
            sender_name="Alex"
        ))
        self.assertIsInstance(reply, str)
        self.assertIn("Alex", reply)
        self.assertTrue(len(reply) > 10)

    def test_empty_message_ignored(self):
        engine = AIEngine(provider="gemini", gemini_api_key="")
        reply = asyncio.run(engine.generate_reply(
            user_id=123,
            message_text="    ",
            sender_name="Alex"
        ))
        self.assertEqual(reply, "")


class TestRateLimiterAndSafety(unittest.TestCase):
    """Tests userbot rate limiting, anti-spam, and cooldown logic."""

    def setUp(self):
        userbot.reply_history.clear()
        userbot.last_reply_time.clear()

    def test_cooldown_enforcement(self):
        user_id = 999
        Config.REPLY_COOLDOWN_SECONDS = 5
        Config.MAX_REPLIES_PER_HOUR = 10

        # First reply should NOT be rate-limited
        self.assertFalse(userbot.is_rate_limited(user_id))
        
        # Record reply
        userbot.record_reply(user_id)

        # Immediately checking should be rate-limited due to cooldown
        self.assertTrue(userbot.is_rate_limited(user_id))

        # Simulate cooldown time elapsed
        userbot.last_reply_time[user_id] = time.time() - 10
        self.assertFalse(userbot.is_rate_limited(user_id))

    def test_max_hourly_replies_enforcement(self):
        user_id = 888
        Config.REPLY_COOLDOWN_SECONDS = 0
        Config.MAX_REPLIES_PER_HOUR = 3

        # Add 3 replies
        for _ in range(3):
            self.assertFalse(userbot.is_rate_limited(user_id))
            userbot.record_reply(user_id)

        # 4th reply should be blocked by hourly cap
        self.assertTrue(userbot.is_rate_limited(user_id))

        # Simulate 1 hour passed
        userbot.reply_history[user_id] = [t - 3601 for t in userbot.reply_history[user_id]]
        # Old timestamps expire, so now it should be allowed again
        self.assertFalse(userbot.is_rate_limited(user_id))


if __name__ == "__main__":
    unittest.main()
