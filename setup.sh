#!/bin/bash
set -e

echo "=========================================================="
echo "  Telegram Private Message AI Auto-Reply Setup Script     "
echo "=========================================================="

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.10+ and re-run."
    exit 1
fi

echo "📦 Creating virtual environment (.venv)..."
python3 -m venv .venv
source .venv/bin/activate

echo "⬇️ Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create .env if not present
if [ ! -f .env ]; then
    echo "📝 Copying .env.example to .env..."
    cp .env.example .env
    echo "👉 Please edit the .env file with your Telegram credentials and AI API key."
else
    echo "✅ .env file already exists."
fi

echo ""
echo "=========================================================="
echo "  Setup Complete! 🚀"
echo "=========================================================="
echo "To run Personal Account Auto-Reply (Userbot):"
echo "  source .venv/bin/activate && python3 userbot.py"
echo ""
echo "To run Official BotFather Bot:"
echo "  source .venv/bin/activate && python3 bot.py"
echo "=========================================================="
