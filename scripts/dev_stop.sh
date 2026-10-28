#!/usr/bin/env bash
# CareerRadar AI · Lokal sunucuları DURDUR (API + Streamlit)
set -eu
PROJ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJ_ROOT"
PID_DIR="$PROJ_ROOT/.pids"

stop_pid() {
  local label="$1"; local pidfile="$PID_DIR/$2.pid"
  if [ -f "$pidfile" ]; then
    local pid
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "🛑 $label durduruluyor (PID=$pid)..."
      kill -TERM "$pid" 2>/dev/null || true
      sleep 1
      if kill -0 "$pid" 2>/dev/null; then
        kill -KILL "$pid" 2>/dev/null || true
      fi
    else
      echo "ℹ️  $label çalışmıyor (PID=$pidfile)"
    fi
    rm -f "$pidfile"
  else
    echo "ℹ️  $label için PID dosyası yok ($pidfile)"
  fi
}

stop_pid "Backend  (API 8000)"    "api"
stop_pid "Frontend (Streamlit 8501)" "streamlit"

# Ekstra fallback (pkill, güvenlik)
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "streamlit run streamlit_app.py" 2>/dev/null || true
echo "✅ Tüm servisler durduruldu (API + Streamlit)."
