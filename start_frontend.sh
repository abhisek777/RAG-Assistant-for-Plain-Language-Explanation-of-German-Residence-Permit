#!/bin/bash
# ─── Start Frontend ──────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/frontend"

echo "📦 Installing Node dependencies..."
npm install

echo ""
echo "🚀 Starting frontend on http://localhost:3000"
echo "   Make sure the backend is running on port 8000 first!"
echo "   Press Ctrl+C to stop"
echo ""
npm run dev
