#!/usr/bin/env bash
cd "$(dirname "$0")"
echo "Avvio PAPP EA Chat Assistant..."
echo "DB: papp_ea@localhost"
echo "Ollama: qwen2.5:3b"
echo "Porta: 8000"
exec python3 -m uvicorn app:app --host 0.0.0.0 --port 8000
