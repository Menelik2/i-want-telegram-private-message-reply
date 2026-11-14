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
                        system_instruction=self.system_instruction
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
        # Check if text is empty
        if not message_text or not message_text.strip():
            return ""

        # Format input with sender's name for extra context
        formatted_prompt = f"[{sender_name}]: {message_text}"

        try:
            if self.provider == "gemini" and self.gemini_client:
                return await self._reply_gemini(user_id, formatted_prompt, message_text)
            elif self.provider == "openai" and self.openai_client:
                return await self._reply_openai(user_id, formatted_prompt, message_text)
            else:
                # Fallback template if no API key is configured yet
                return (
                    f"Hi {sender_name}! I received your private message: \"{message_text}\". "
                    "I am an automated AI assistant. Please configure my GEMINI_API_KEY or OPENAI_API_KEY to enable smart replies!"
                )
        except Exception as e:
            logger.error(f"Error in generate_reply: {e}", exc_info=True)
            return "Thank you for reaching out! I received your message and will review it as soon as possible."

    async def _reply_gemini(self, user_id: int, formatted_prompt: str, raw_text: str) -> str:
        import asyncio
        history = self.memory.get_history(user_id)
        
        # Build contents list for Gemini
        gemini_contents = []
        for item in history:
            role = "user" if item["role"] == "user" else "model"
            gemini_contents.append({"role": role, "parts": [item["text"]]})
        
        gemini_contents.append({"role": "user", "parts": [formatted_prompt]})

        # Run async in executor since google-generativeai SDK sync call
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.gemini_client.generate_content(gemini_contents)
        )
        reply_text = response.text.strip() if response and response.text else "Message received."

        # Update memory
        self.memory.add_message(user_id, "user", raw_text)
        self.memory.add_message(user_id, "model", reply_text)
        return reply_text

    async def _reply_openai(self, user_id: int, formatted_prompt: str, raw_text: str) -> str:
        history = self.memory.get_history(user_id)
        messages = [{"role": "system", "content": self.system_instruction}]
        
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
