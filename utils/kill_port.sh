#!/usr/bin/env bash
set -euo pipefail

PORT="$1"

if [[ -z "${PORT:-}" ]]; then
  echo "[kill-port] ERROR: No port provided"
  exit 1
fi

pids="$(lsof -ti :"$PORT" 2>/dev/null || true)"

if [[ -n "$pids" ]]; then
  echo "[kill-port] Port $PORT is busy → killing PID(s): $pids"
  kill $pids 2>/dev/null || true
  sleep 0.5

  still="$(lsof -ti :"$PORT" 2>/dev/null || true)"
  if [[ -n "$still" ]]; then
    echo "[kill-port] Force killing PID(s): $still"
    kill -9 $still 2>/dev/null || true
  fi
else
  echo "[kill-port] Port $PORT is free"
fi
