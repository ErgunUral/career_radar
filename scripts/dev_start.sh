#!/usr/bin/env bash
# CareerRadar AI · Lokal Geliştirme Sunucularını Başlat
#   Kullanım: ./scripts/dev_start.sh   (project root çalıştır)
#   Çıktı:  Backend  : http://127.0.0.1:8000/docs    (FastAPI + Swagger)
#           Frontend : http://localhost:8501          (Streamlit Dashboard)
set -eu
PROJ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJ_ROOT"

LOG_DIR="$PROJ_ROOT/logs"
mkdir -p "$LOG_DIR"
API_LOG="$LOG_DIR/api_$(date +%Y%m%d_%H%M%S).log"
FE_LOG="$LOG_DIR/streamlit_$(date +%Y%m%d_%H%M%S).log"
PID_DIR="$PROJ_ROOT/.pids"
mkdir -p "$PID_DIR"

# ──────────────────────────────────────────────────────────────────────────────
# 1. BACKEND — FastAPI + Uvicorn (port 8000)
# ──────────────────────────────────────────────────────────────────────────────
cd "$PROJ_ROOT/apps/api"
if [ -f "$PID_DIR/api.pid" ] && kill -0 "$(cat "$PID_DIR/api.pid")" 2>/dev/null; then
  echo "ℹ️  Backend zaten çalışıyor (PID=$(cat "$PID_DIR/api.pid"))"
else
  echo "🚀 Backend başlatılıyor (port 8000) — log: $API_LOG"
  nohup python3 -m uvicorn app.main:app \
    --host 127.0.0.1 --port 8000 --log-level info \
      >"$API_LOG" 2>&1 &
  API_PID=$!
  echo "$API_PID" > "$PID_DIR/api.pid"
  sleep 2.5
  if ! kill -0 "$API_PID" 2>/dev/null; then
    echo "❌ Backend BAŞLAMADI — log: $API_LOG"; tail -30 "$API_LOG"; exit 1
  fi
fi

# ──────────────────────────────────────────────────────────────────────────────
# 2. FRONTEND — Streamlit (port 8501)
# ──────────────────────────────────────────────────────────────────────────────
cd "$PROJ_ROOT/apps/frontend"
if [ -f "$PID_DIR/streamlit.pid" ] && kill -0 "$(cat "$PID_DIR/streamlit.pid")" 2>/dev/null; then
  echo "ℹ️  Frontend zaten çalışıyor (PID=$(cat "$PID_DIR/streamlit.pid"))"
else
  echo "🚀 Frontend başlatılıyor (port 8501) — log: $FE_LOG"
  nohup python3 -m streamlit run streamlit_app.py \
    --server.port 8501 --server.headless true --server.runOnSave true \
      >"$FE_LOG" 2>&1 &
  FE_PID=$!
  echo "$FE_PID" > "$PID_DIR/streamlit.pid"
  sleep 4
  if ! kill -0 "$FE_PID" 2>/dev/null; then
    echo "❌ Frontend BAŞLAMADI — log: $FE_LOG"; tail -30 "$FE_LOG"; exit 1
  fi
fi

# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  🎯 CareerRadar AI · Kişisel İş Radar Paneli — HAZIR          ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
printf "║  Backend  :  http://127.0.0.1:8000   (PID %-6d)             ║\n" "$(cat "$PID_DIR/api.pid" 2>/dev/null || echo "—")"
printf "║  Swagger  :  http://127.0.0.1:8000/docs                        ║\n"
printf "║  Frontend :  http://localhost:8501       (PID %-6d)         ║\n" "$(cat "$PID_DIR/streamlit.pid" 2>/dev/null || echo "—")"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║  Durdurmak için:  ./scripts/dev_stop.sh                        ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
