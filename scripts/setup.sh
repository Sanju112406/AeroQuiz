#!/bin/bash
# ─────────────────────────────────────────────────────────────
# Aircraft Engineer Quiz Bot — Setup Script
# Run: bash scripts/setup.sh
# ─────────────────────────────────────────────────────────────

set -e

VENV_DIR=".venv"
PYTHON="${PYTHON:-python3}"

echo "✈️  Aircraft Engineer Quiz Bot — Setup"
echo "────────────────────────────────────────"

# Check Python
if ! command -v $PYTHON &>/dev/null; then
  echo "❌ Python 3 not found. Install it and retry."
  exit 1
fi

PY_VER=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "🐍 Python $PY_VER found"

# Create virtualenv
if [ ! -d "$VENV_DIR" ]; then
  echo "📦 Creating virtual environment..."
  $PYTHON -m venv $VENV_DIR
fi

source $VENV_DIR/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Create directories
mkdir -p data/chromadb data/sessions logs manuals

# Check .env
if grep -q "REPLACE_WITH_YOUR_KEY_HERE" .env; then
  echo ""
  echo "⚠️  ACTION REQUIRED:"
  echo "   Edit .env and set your ANTHROPIC_API_KEY"
  echo "   (and Teams credentials when you have them)"
  echo ""
fi

# Check for manuals
PDF_COUNT=$(find manuals/ -name "*.pdf" 2>/dev/null | wc -l | tr -d ' ')
if [ "$PDF_COUNT" -eq 0 ]; then
  echo "📂 Drop your aircraft manual PDFs into the ./manuals/ directory"
  echo "   Then run: python rag/ingest.py"
else
  echo "📚 Found $PDF_COUNT PDF(s) in ./manuals/"
  read -p "   Ingest them now? [y/N] " yn
  if [[ "$yn" =~ ^[Yy]$ ]]; then
    python rag/ingest.py
  fi
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Add manuals:        cp your-manual.pdf manuals/"
echo "  2. Ingest manuals:     python rag/ingest.py"
echo "  3. Set API key:        edit .env → ANTHROPIC_API_KEY"
echo "  4. Start bot:          python -m bot.app"
echo "  5. Teams setup:        see README.md"
