"""
Unified AI Engine for Telegram Private Message Reply
Supports Google Gemini and OpenAI with per-user conversation memory.
"""

import os
import time
import logging
from typing import Dict, List, Optional

logger = logging.getLogger("AIEngine")

class ConversationMemory:
    """Manages rolling conversation history per user."""
    def __init__(self, max_history: int = 10, ttl_seconds: int = 3600):
        self.max_history = max_history
        self.ttl_seconds = ttl_seconds
        # user_id -> {"last_active": timestamp, "messages": [{"role": "user"|"model", "text": "..."}]}
        self.sessions: Dict[int, dict] = {}

    def get_history(self, user_id: int) -> List[dict]:
        now = time.time()
        if user_id in self.sessions:
            session = self.sessions[user_id]
            if now - session["last_active"] > self.ttl_seconds:
                # Expired conversation context
                self.sessions[user_id] = {"last_active": now, "messages": []}
            return self.sessions[user_id]["messages"]
        self.sessions[user_id] = {"last_active": now, "messages": []}
        return self.sessions[user_id]["messages"]

    def add_message(self, user_id: int, role: str, text: str):
        now = time.time()
        history = self.get_history(user_id)
        history.append({"role": role, "text": text})
        if len(history) > self.max_history * 2:
            # Keep the most recent messages
            self.sessions[user_id]["messages"] = history[-(self.max_history * 2):]
        self.sessions[user_id]["last_active"] = now

    def clear(self, user_id: int):
        if user_id in self.sessions:
            self.sessions[user_id]["messages"] = []
            self.sessions[user_id]["last_active"] = time.time()


def sanitize_gemini_turns(history: List[dict], current_prompt: str) -> List[dict]:
    """
    Sanitizes conversation history for Google Gemini:
    1. Ensures contents strictly start with 'user'.
    2. Ensures alternating sequence ('user', 'model', 'user', ...).
    3. Merges consecutive same-role parts to prevent Gemini 400 Bad Request.
    """
    contents = []
    
    # Process history turns
    for item in history:
        role = "user" if item.get("role") in ("user", "human") else "model"
        text = (item.get("text") or "").strip()
        if not text:
            continue
            
        if not contents:
            if role != "user":
                # First message must be user in Gemini
                continue
            contents.append({"role": "user", "parts": [text]})
        else:
            prev = contents[-1]
            if prev["role"] == role:
                # Same role consecutive - merge into parts
                prev["parts"].append(text)
            else:
                contents.append({"role": role, "parts": [text]})

    # Add the current user prompt
    if not contents or contents[-1]["role"] != "user":
        contents.append({"role": "user", "parts": [current_prompt]})
    else:
        # Merge if previous was somehow user
        contents[-1]["parts"].append(current_prompt)

    return contents


class AIEngine:
    def __init__(
        self,
        provider: str = "gemini",
        gemini_api_key: Optional[str] = None,
        gemini_model: str = "gemini-1.5-flash",
        openai_api_key: Optional[str] = None,
        openai_model: str = "gpt-4o-mini",
        system_instruction: str = "",
        max_history: int = 10
    ):
        self.provider = provider.lower()
        self.system_instruction = system_instruction
        self.memory = ConversationMemory(max_history=max_history)

        self.gemini_model_name = gemini_model
        self.openai_model_name = openai_model
        self.gemini_client = None
        self.openai_client = None

        if self.provider == "gemini":
            key = gemini_api_key or os.getenv("GEMINI_API_KEY")
            if key:
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=key)
                    self.gemini_client = genai.GenerativeModel(
                        model_name=self.gemini_model_name,
                        system_instruction=self.system_instruction or None
                    )
                    logger.info(f"Gemini client initialized with model: {self.gemini_model_name}")
                except Exception as e:
                    logger.error(f"Failed to initialize Gemini: {e}")
            else:
                logger.warning("GEMINI_API_KEY is not set!")

        elif self.provider == "openai":
            key = openai_api_key or os.getenv("OPENAI_API_KEY")
            if key:
                try:
                    from openai import AsyncOpenAI
                    self.openai_client = AsyncOpenAI(api_key=key)
                    logger.info(f"OpenAI client initialized with model: {self.openai_model_name}")
                except Exception as e:
                    logger.error(f"Failed to initialize OpenAI: {e}")
            else:
                logger.warning("OPENAI_API_KEY is not set!")

    async def generate_reply(self, user_id: int, message_text: str, sender_name: str = "User") -> str:
        """Generates an AI reply to a private message with conversation history."""
        if not message_text or not message_text.strip():
            return ""

        formatted_prompt = f"[{sender_name}]: {message_text.strip()}"

        try:
            if self.provider == "gemini" and self.gemini_client:
                return await self._reply_gemini(user_id, formatted_prompt, message_text.strip())
            elif self.provider == "openai" and self.openai_client:
                return await self._reply_openai(user_id, formatted_prompt, message_text.strip())
            else:
                # Built-in contextual fallback response
                return (
                    f"Hi {sender_name}! I received your private message: \"{message_text.strip()}\". "
                    "I am currently in auto-reply mode. Please set GEMINI_API_KEY or OPENAI_API_KEY to activate dynamic AI reasoning."
                )
        except Exception as e:
            logger.error(f"Error in generate_reply: {e}", exc_info=True)
            return "Thank you for reaching out! I received your message and will follow up shortly."

    async def _reply_gemini(self, user_id: int, formatted_prompt: str, raw_text: str) -> str:
        import asyncio
        history = self.memory.get_history(user_id)
        gemini_contents = sanitize_gemini_turns(history, formatted_prompt)

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.gemini_client.generate_content(gemini_contents)
        )

        reply_text = ""
        try:
            if response and response.text:
                reply_text = response.text.strip()
        except (ValueError, AttributeError):
            if response and response.candidates:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    reply_text = candidate.content.parts[0].text.strip()

        if not reply_text:
            reply_text = "I received your message and will get back to you shortly."

        # Update memory
        self.memory.add_message(user_id, "user", raw_text)
        self.memory.add_message(user_id, "model", reply_text)
        return reply_text

    async def _reply_openai(self, user_id: int, formatted_prompt: str, raw_text: str) -> str:
        history = self.memory.get_history(user_id)
        messages = []
        if self.system_instruction:
            messages.append({"role": "system", "content": self.system_instruction})
        
        for item in history:
            role = "user" if item["role"] == "user" else "assistant"
            messages.append({"role": role, "content": item["text"]})
            
        messages.append({"role": "user", "content": formatted_prompt})

        response = await self.openai_client.chat.completions.create(
            model=self.openai_model_name,
            messages=messages,
            max_tokens=600,
            temperature=0.7,
        )
        reply_text = response.choices[0].message.content.strip()

        # Update memory
        self.memory.add_message(user_id, "user", raw_text)
        self.memory.add_message(user_id, "assistant", reply_text)
        return reply_text
