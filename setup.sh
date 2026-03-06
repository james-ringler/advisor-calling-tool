#!/bin/bash
set -e

echo "=== Advisor Calling Tool Setup ==="

# Check for .env
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "⚠️  Created .env from .env.example"
  echo "    Fill in your API keys before starting:"
  echo "    - HUBSPOT_TOKEN      → HubSpot private app token"
  echo "    - AIRCALL_API_ID     → Aircall API ID"
  echo "    - AIRCALL_API_TOKEN  → Aircall API token"
  echo "    - ANTHROPIC_API_KEY  → Anthropic API key"
  echo "    - DATABASE_URL       → Set automatically by Railway"
  echo ""
fi

# Backend
echo "→ Setting up Python backend..."
cd backend
python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet "fastapi==0.111.0" "uvicorn[standard]==0.29.0" "httpx==0.27.0" \
  "python-dotenv==1.0.1" "pydantic>=2.7,<3" "pydantic-settings>=2.3,<3" "anthropic>=0.28" "asyncpg>=0.29"
echo "✓ Backend ready"
cd ..

# Frontend
echo "→ Setting up React frontend..."
cd frontend
if ! command -v npm &> /dev/null; then
  echo ""
  echo "⚠️  Node.js / npm not found."
  echo "    Install Node.js from: https://nodejs.org (LTS version)"
  echo "    Then re-run this script."
  echo ""
  exit 1
fi
npm install --silent
echo "✓ Frontend ready"
cd ..

echo ""
echo "=== Setup complete! ==="
echo ""
echo "To start the app, open two terminals:"
echo ""
echo "  Terminal 1 (backend):"
echo "    cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8000"
echo ""
echo "  Terminal 2 (frontend):"
echo "    cd frontend && npm run dev"
echo ""
echo "Then open: http://localhost:5173"
