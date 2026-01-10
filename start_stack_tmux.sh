#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/Desktop/machine"
UTILS="$ROOT/utils/kill_port.sh"

# Ports
TES_PORT="${TES_PORT:-8080}"
TOOLSERVER_PORT="${TOOLSERVER_PORT:-9090}"
WORKBENCH_PORT="${WORKBENCH_PORT:-8000}"
LIMSX_PORT="${LIMSX_PORT:-7000}"

SESSION="${SESSION:-omnibioai}"

# Optional venv
VENV_ACTIVATE="$ROOT/omnibioai_workbench/.venv/bin/activate"

activate_env() {
  # shellcheck disable=SC1090
  [[ -f "$VENV_ACTIVATE" ]] && source "$VENV_ACTIVATE"
}

# ---- Kill busy ports ----
"$UTILS" "$TES_PORT"
"$UTILS" "$TOOLSERVER_PORT"
"$UTILS" "$WORKBENCH_PORT"
"$UTILS" "$LIMSX_PORT"

# ---- tmux session ----
if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "tmux session '$SESSION' already exists → killing it so we can restart cleanly."
  tmux kill-session -t "$SESSION"
fi

tmux new-session -d -s "$SESSION" -n tes

# TES
tmux send-keys -t "$SESSION:tes" \
  "cd \"$ROOT/omnibioai-tool-exec\" && $(declare -f activate_env); activate_env; HOST=127.0.0.1 PORT=$TES_PORT TES_UPGRADE=0 ./scripts/restart_tes.sh" C-m

# ToolServer
tmux new-window -t "$SESSION" -n toolserver
tmux send-keys -t "$SESSION:toolserver" \
  "cd \"$ROOT/omnibioai-toolserver\" && $(declare -f activate_env); activate_env; uvicorn toolserver_app:create_app --factory --host 127.0.0.1 --port $TOOLSERVER_PORT" C-m

# LIMS-X (replace when ready)
tmux new-window -t "$SESSION" -n limsx
tmux send-keys -t "$SESSION:limsx" \
  "cd \"$ROOT/LIMS-X\" && $(declare -f activate_env); activate_env; echo 'START LIMS-X HERE'; sleep 999999" C-m

# Workbench
tmux new-window -t "$SESSION" -n workbench
tmux send-keys -t "$SESSION:workbench" \
  "cd \"$ROOT/omnibioai_workbench\" && $(declare -f activate_env); activate_env; python manage.py runserver 127.0.0.1:$WORKBENCH_PORT" C-m

# Smoke test window (wait a bit + run)
tmux new-window -t "$SESSION" -n smoke
tmux send-keys -t "$SESSION:smoke" \
  "cd \"$ROOT/omnibioai_workbench\" && $(declare -f activate_env); activate_env; sleep 3; bash smoke_test_stack.sh" C-m

tmux select-window -t "$SESSION:workbench"

echo "OmniBioAI stack started"
echo "Attach with: tmux attach -t $SESSION"
