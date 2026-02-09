#!/bin/bash
set -e

echo "=============================="
echo "Starting OmniBioAI stack"
echo "=============================="

ROOT=~/Desktop/machine

# ----------------------------
# Start omnibioai-tes
# ----------------------------
echo "[1/2] Starting tool-exec..."
cd $ROOT/omnibioai-tes

# kill old server if running
pkill -f "tool_exec" || true

# start tool-exec
python manage.py runserver 8081 --noreload > tool_exec.log 2>&1 &

sleep 2
echo "tool-exec running on :8081"

# ----------------------------
# Start OmniBioAI
# ----------------------------
echo "[2/2] Starting OmniBioAI..."
cd $ROOT/omnibioai

bash omnibioai/scripts/start_app.sh

