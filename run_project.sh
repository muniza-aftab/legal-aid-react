#!/bin/bash
# Pakistan AI Legal Aid — macOS/Linux Launcher

set -e
cd "$(dirname "$0")"
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

echo ""
echo "  ⚖️  Pakistan AI Legal Aid Assistant"
echo "  ======================================"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
  echo -e "${RED}[ERROR]${NC} Python 3 not found. Install from https://python.org"
  exit 1
fi

# Check Node
if ! command -v node &>/dev/null; then
  echo -e "${RED}[ERROR]${NC} Node.js not found. Install from https://nodejs.org"
  exit 1
fi

echo -e "${GREEN}[OK]${NC} Python $(python3 --version) and Node $(node --version) found."

# Setup backend venv
cd backend
if [ ! -d "venv" ]; then
  echo -e "${YELLOW}[INFO]${NC} Creating Python virtual environment..."
  python3 -m venv venv
fi
source venv/bin/activate

# Install backend deps
echo -e "${YELLOW}[INFO]${NC} Installing/verifying Python dependencies..."
pip install -r requirements.txt -q

# Copy .env if missing
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo -e "${RED}[ACTION]${NC} Please edit backend/.env and add your GROQ_API_KEY, then re-run."
  exit 1
fi

# Build index if needed
if [ ! -d "data/faiss_index" ] || [ -z "$(ls -A data/faiss_index 2>/dev/null)" ]; then
  echo -e "${YELLOW}[INFO]${NC} Building legal document index (first run, may take several minutes)..."
  python build_index.py
fi

# Install frontend deps
cd ../frontend
if [ ! -d "node_modules" ]; then
  echo -e "${YELLOW}[INFO]${NC} Installing frontend dependencies..."
  npm ci -q
fi

cd ..

# Start backend
echo -e "${GREEN}[START]${NC} Starting backend at http://localhost:8000 ..."
cd backend
source venv/bin/activate
python main.py &
BACKEND_PID=$!
cd ..

sleep 3

# Start frontend
echo -e "${GREEN}[START]${NC} Starting frontend at http://localhost:5173 ..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "  =========================================="
echo "  ✅ Application running!"
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo "  API Docs: http://localhost:8000/api/docs"
echo "  =========================================="
echo ""
echo "  Press Ctrl+C to stop both servers."
echo ""

# Wait and cleanup
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Servers stopped.'" INT TERM
wait
