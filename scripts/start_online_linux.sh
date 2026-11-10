#!/usr/bin/env bash
# Runs API and Streamlit on a single Linux host; Raj-0 should already listen on 127.0.0.1:8080.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -f .env ]; then echo 'Create .env from .env.example and set secure secrets first'; exit 1; fi
set -a
source .env
set +a
if [ -z "${APP_PASSWORD:-}" ] || [ -z "${API_KEY:-}" ]; then echo 'APP_PASSWORD and API_KEY are required'; exit 1; fi
python3 -m uvicorn api:app --host 127.0.0.1 --port 8000 &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT
exec python3 -m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501
