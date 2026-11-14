# 🤖 Telegram Private Message AI Auto-Reply Bot

[![Telegram](https://img.shields.io/badge/Telegram-Private%20Messages-2CA5E0?logo=telegram&logoColor=white)](https://telegram.org)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://python.org)
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini-4285F4?logo=google&logoColor=white)](https://aistudio.google.com/)
[![OpenAI](https://img.shields.io/badge/AI-OpenAI%20GPT--4o-00A67E?logo=openai&logoColor=white)](https://platform.openai.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An intelligent, production-ready AI auto-responder for **Telegram 1-on-1 private messages (DMs)**. It automatically replies to incoming personal chats using **Google Gemini** or **OpenAI GPT-4o**, equipped with conversation memory, human-like typing simulation, anti-spam filters, and configurable persona instructions.

---

## ⚡ Highlights & Key Features

* **Strict Private Message Isolation**: Operates exclusively in 1-on-1 private chats. Never posts in groups or public channels.
* **Two Operating Modes**:
  1. **Personal Account Auto-Reply (`userbot.py`)**: Runs on your personal Telegram account via MTProto (`Telethon`). Answers contacts or strangers when you are away or busy.
  2. **Official Telegram Bot (`bot.py`)**: Runs as a standard `@BotFather` bot via Telegram Bot API (`python-telegram-bot`) for customer support or lead capture.
* **Multi-Provider AI Engine**: Native support for **Google Gemini** (`gemini-1.5-flash`, `gemini-1.5-pro`) and **OpenAI** (`gpt-4o`, `gpt-4o-mini`).
* **Conversational Memory**: Remembers previous messages in the chat session so replies stay context-aware.
* **Human-Like Behavior**: Simulates real Telegram typing indicator with custom delays before sending.
* **Loop & Spam Protection**:
  - Automatically ignores other bots to avoid infinite loop cascades.
  - Per-user cooldown and hourly rate limiters.
  - Whitelist and blacklist filtering.
* **Zero-Setup Web Dashboard & Simulator**: Test and preview private message responses right from your browser.

---

## 📋 Architecture Flow

```
   Incoming Private DM (Telegram)
               │
               ▼
   [Private Chat Validation] ────────► (If Group/Channel: Discard)
               │
               ▼
      [Anti-Loop & Filters] ─────────► (If Sender is Bot or Blacklisted: Discard)
               │
               ▼
     [Rate Limiter & Cooldown] ──────► (If Exceeded: Skip)
               │
               ▼
   [Simulate Typing Indicator]
               │
               ▼
  [AI Engine (Gemini / OpenAI)] ◄────► [Context History Memory]
               │
               ▼
   Send Auto-Reply to Private DM
```

---

## 🚀 Quick Start (5 Minutes)

### 1. Clone & Install Dependencies

```bash
git clone https://github.com/Menelik2/i-want-telegram-private-message-reply.git
cd i-want-telegram-private-message-reply

# Run automatic setup
chmod +x setup.sh
./setup.sh
```

Or manually:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

---

### 2. Configure Credentials (`.env`)

Choose between **Personal Account (Userbot)** or **Bot API (BotFather)**:

#### Option A: Personal Account Auto-Reply (Userbot)
1. Visit [my.telegram.org](https://my.telegram.org) and log in with your phone number.
2. Go to **API development tools** and create an application to obtain:
   - `TELEGRAM_API_ID`
   - `TELEGRAM_API_HASH`
3. Get a free Gemini API key from [Google AI Studio](https://aistudio.google.com/).
4. Put them in your `.env`:
   ```ini
   BOT_MODE=userbot
   TELEGRAM_API_ID=12345678
   TELEGRAM_API_HASH=your_api_hash_here
   TELEGRAM_PHONE=+1234567890
   
   AI_PROVIDER=gemini
   GEMINI_API_KEY=your_gemini_key_here
   ```

#### Option B: Official Telegram Bot
1. Open Telegram and search for `@BotFather`.
2. Send `/newbot`, name your bot, and copy the HTTP API Token.
3. Put it in `.env`:
   ```ini
   BOT_MODE=bot
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
   AI_PROVIDER=gemini
   GEMINI_API_KEY=your_gemini_key_here
   ```

---

### 3. Run the Bot

**For Personal Account (Userbot):**
```bash
python3 userbot.py
```
*(On the first run, Telethon will ask you for a login confirmation code sent to your Telegram app).*

**For Official Bot:**
```bash
python3 bot.py
```

---

## 🐳 Running with Docker

Run 24/7 inside a lightweight Docker container:

```bash
# Build and start in background
docker compose up -d

# View live logs
docker compose logs -f
```

---

## ⚙️ Configuration Reference

| Variable | Default | Description |
| :--- | :--- | :--- |
| `BOT_MODE` | `userbot` | Choose `userbot` (personal account) or `bot` (BotFather) |
| `AI_PROVIDER` | `gemini` | `gemini` or `openai` |
| `GEMINI_API_KEY` | - | Your Google AI Studio API key |
| `GEMINI_MODEL` | `gemini-1.5-flash` | Model identifier (`gemini-1.5-flash`, `gemini-1.5-pro`) |
| `OPENAI_API_KEY` | - | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model identifier (`gpt-4o-mini`, `gpt-4o`) |
| `AUTO_REPLY_DELAY` | `2.0` | Seconds to show "typing..." before replying |
| `REPLY_COOLDOWN_SECONDS` | `10` | Minimum gap between consecutive replies to the same user |
| `MAX_REPLIES_PER_HOUR` | `8` | Maximum AI replies per user within an hour |
| `SYSTEM_PROMPT` | *(Included)* | Persona, role description, and instructions for the AI |
| `WHITELIST_USERS` | `""` | Comma-separated usernames or user IDs to exclusively reply to |
| `BLACKLIST_USERS` | `""` | Comma-separated usernames or user IDs to completely ignore |

---

## ❓ Frequently Asked Questions

#### Q: Will this reply to group chats or channels?
**No.** Both `userbot.py` and `bot.py` have strict validation checks:
```python
if not event.is_private:
    return
```
Only 1-on-1 direct messages are processed.

#### Q: Can my Telegram account get banned for using a userbot?
Telethon connects via the official MTProto protocol. To prevent flood limits:
- Keep `AUTO_REPLY_DELAY` between 2 to 5 seconds.
- Keep `MAX_REPLIES_PER_HOUR` at a reasonable number (default 8).
- We never initiate unsolicited DMs; we only respond to incoming ones.

#### Q: Can I run this on a cheap VPS or Raspberry Pi?
Yes! The Python script consumes under 60MB of RAM and runs smoothly on any Linux VPS, Docker host, Raspberry Pi, or cloud provider (e.g., Railway, Render, Fly.io).

---

## 📄 License
MIT License. Free to use, modify, and distribute.
