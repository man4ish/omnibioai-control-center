#!/usr/bin/env bash
set -euo pipefail

SESSION="omnibioai"

# Base paths (repos)
OMNI_CORE=~/Desktop/machine/omnibioai
OMNI_TES=~/Desktop/machine/omnibioai-tes
OMNI_TOOL=~/Desktop/machine/omnibioai-toolserver
OMNI_LIMS=~/Desktop/machine/omnibioai-lims

# Optional: load your env (uncomment + set the right file if you use one)
# [ -f ~/.bashrc ] && source ~/.bashrc
# [ -f ~/.zshrc ] && source ~/.zshrc
# [ -f ~/.omnibioai.env ] && source ~/.omnibioai.env

tmux has-session -t "$SESSION" 2>/dev/null && tmux kill-session -t "$SESSION"
tmux new-session -d -s "$SESSION" -n services

# Pane 0 — Core app
tmux send-keys -t "$SESSION:services" \
  "cd \"$OMNI_CORE\" && bash scripts/start_app.sh" C-m

# Pane 1 — TES
tmux split-window -h -t "$SESSION:services"
tmux send-keys -t "$SESSION:services.1" \
  "cd \"$OMNI_TES\" && bash scripts/start_app.sh" C-m

# Pane 2 — Tool server
tmux split-window -v -t "$SESSION:services.0"
tmux send-keys -t "$SESSION:services.2" \
  "cd \"$OMNI_TOOL\" && bash scripts/start_app.sh" C-m

# Pane 3 — LIMS
tmux split-window -v -t "$SESSION:services.1"
tmux send-keys -t "$SESSION:services.3" \
  "cd \"$OMNI_LIMS\" && bash scripts/start_app.sh" C-m

tmux select-layout -t "$SESSION" tiled
tmux attach -t "$SESSION"
