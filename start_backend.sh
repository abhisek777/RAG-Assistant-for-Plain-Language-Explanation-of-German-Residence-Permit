#!/bin/bash
# ─── Start Backend ───────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/backend"

# Load .env
if [ -f "../.env" ]; then
  export $(grep -v '^#' ../.env | xargs)
  echo "✅ Loaded .env"
else
  echo "⚠️  No .env file found. Copy .env.example to .env and set your API key."
  exit 1
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "❌ ANTHROPIC_API_KEY is not set in .env"
  exit 1
fi

# Detect python3 vs python
PYTHON=$(command -v python3 || command -v python)
if [ -z "$PYTHON" ]; then
  echo "❌ Python not found. Install Python 3 first."
  exit 1
fi

# Install dependencies if needed
echo "📦 Checking Python dependencies..."
$PYTHON -m pip install -r requirements_lite.txt -q

# Download spaCy model if missing
$PYTHON -c "import spacy; spacy.load('de_core_news_sm')" 2>/dev/null || {
  echo "📥 Downloading German spaCy model (one-time)..."
  $PYTHON -m spacy download de_core_news_sm
}

echo ""
echo "🚀 Starting backend on http://localhost:8000"
echo "   Press Ctrl+C to stop"
echo ""
$PYTHON -m uvicorn main_lite:app --reload --port 8000
