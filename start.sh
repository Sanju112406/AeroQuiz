#!/bin/bash
# start.sh — Start both the Telegram bot and Gradio UI in the background

cd "$(dirname "$0")"
source .venv/bin/activate

# Kill any existing instances
pkill -f "bot.app" 2>/dev/null
pkill -f "ui/app.py" 2>/dev/null
sleep 2

mkdir -p logs

echo "🚀 Starting Telegram bot..."
nohup python3 -m bot.app > logs/bot.log 2>&1 &
echo "   Bot PID: $!"

echo "🌐 Starting Gradio UI..."
nohup python3 ui/app.py > logs/ui.log 2>&1 &
echo "   UI PID: $!"

echo ""
echo "✅ Both services running!"
echo "   Telegram bot: check logs/bot.log"
echo "   Gradio UI:    http://127.0.0.1:7860  (check logs/ui.log)"
echo ""
echo "To stop everything: bash stop.sh"
