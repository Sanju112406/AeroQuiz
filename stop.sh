#!/bin/bash
# stop.sh — Stop both services

echo "🛑 Stopping AeroQuiz services..."
pkill -f "bot.app" 2>/dev/null && echo "   ✅ Bot stopped" || echo "   ℹ️  Bot was not running"
pkill -f "ui/app.py" 2>/dev/null && echo "   ✅ UI stopped" || echo "   ℹ️  UI was not running"
echo "Done."
