#!/usr/bin/env bash
cd "$(dirname "$0")"
# Carica le variabili da .env nell'ambiente (SECRET_KEY, DATABASE_URL, ...)
set -a
[ -f .env ] && . ./.env
set +a
echo "Avvio PAPP EA Chat Assistant..."
echo "DB: papp_ea@localhost"
echo "API: opencode/deepseek-v4-flash-free (via desktop app attach)"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
echo "Bind: ${HOST}:${PORT}"
exec python3 -m uvicorn app:app --host "$HOST" --port "$PORT"
