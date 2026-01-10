#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-127.0.0.1}"

TES_PORT="${TES_PORT:-8080}"
TOOLSERVER_PORT="${TOOLSERVER_PORT:-9090}"
WORKBENCH_PORT="${WORKBENCH_PORT:-8000}"

# If your Django route differs, change this:
DJ_TES_STATUS_PATH_PREFIX="${DJ_TES_STATUS_PATH_PREFIX:-/plugins/llm_chat/tes/run}"

# ---------- helpers ----------
die(){ echo "[smoke] ERROR: $*" >&2; exit 1; }
log(){ echo "[smoke] $*"; }

has_cmd(){ command -v "$1" >/dev/null 2>&1; }

need_cmd(){
  has_cmd "$1" || die "Missing required command: $1"
}

wait_http(){
  local url="$1"
  local name="$2"
  local max="${3:-60}"
  local i=0
  while (( i < max )); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      log "$name is up: $url"
      return 0
    fi
    sleep 1
    (( i++ ))
  done
  die "$name did not become ready: $url"
}

wait_port(){
  local port="$1"
  local name="$2"
  local max="${3:-30}"
  local i=0
  while (( i < max )); do
    if lsof -ti :"$port" >/dev/null 2>&1; then
      log "$name port is listening: $port"
      return 0
    fi
    sleep 1
    (( i++ ))
  done
  die "$name port not listening: $port"
}

json_get(){
  local url="$1"
  curl -fsS "$url" | python -m json.tool
}

json_post(){
  local url="$1"
  local data="$2"
  curl -fsS -X POST -H "Content-Type: application/json" -d "$data" "$url" | python -m json.tool
}

# ---------- requirements ----------
need_cmd curl
need_cmd python
need_cmd lsof

log "Checking ports..."
wait_port "$TES_PORT" "TES"
wait_port "$TOOLSERVER_PORT" "ToolServer"
wait_port "$WORKBENCH_PORT" "Workbench"

log "Checking HTTP endpoints..."
# best-effort health checks; adjust if your services use different paths
wait_http "http://${HOST}:${TES_PORT}/health" "TES /health" 60 || true
wait_http "http://${HOST}:${TOOLSERVER_PORT}/health" "ToolServer /health" 60 || true
wait_http "http://${HOST}:${WORKBENCH_PORT}/" "Workbench /" 60 || true

log "Submitting TES Enrichr run..."
SUBMIT_JSON="$(cat <<'JSON'
{
  "tool_id": "enrichr_pathway",
  "inputs": {
    "genes": ["TP53","BRCA1","EGFR"],
    "description": "smoke test enrichr",
    "return_mode": "top",
    "top_n": 10,
    "sort_by": "adj_p_value",
    "libraries": ["WikiPathways_2024_Human","Reactome_2022"]
  },
  "resources": {"cpu": 1, "ram_gb": 1},
  "constraints": {"preferred_server_id": "enrichment_remote"}
}
JSON
)"

# validate
log "Validating run..."
json_post "http://${HOST}:${TES_PORT}/api/runs/validate" "$SUBMIT_JSON" >/dev/null || die "TES validate failed"

# submit
SUBMIT_OUT="$(curl -fsS -X POST -H "Content-Type: application/json" \
  -d "$SUBMIT_JSON" "http://${HOST}:${TES_PORT}/api/runs")"

RUN_ID="$(python - <<PY
import json,sys
j=json.loads(sys.stdin.read())
print(j.get("run_id",""))
PY
<<<"$SUBMIT_OUT")"

[[ -n "$RUN_ID" ]] || die "No run_id returned from TES submit: $SUBMIT_OUT"
log "Run submitted: $RUN_ID"

log "Polling via Workbench proxy (Django tes_run_status)..."
STATUS_URL="http://${HOST}:${WORKBENCH_PORT}${DJ_TES_STATUS_PATH_PREFIX}/${RUN_ID}/"

max=120
i=0
state="UNKNOWN"
while (( i < max )); do
  RAW="$(curl -fsS "$STATUS_URL" || true)"
  if [[ -n "$RAW" ]]; then
    state="$(python - <<PY
import json,sys
j=json.loads(sys.stdin.read())
print((j.get("state") or "UNKNOWN").upper())
PY
<<<"$RAW")"
  fi

  log "state=$state"
  if [[ "$state" == "COMPLETED" ]]; then
    break
  elif [[ "$state" == "FAILED" ]]; then
    echo "$RAW" | python -m json.tool | head -n 200
    die "Run failed"
  fi

  sleep 1
  (( i++ ))
done

[[ "$state" == "COMPLETED" ]] || die "Timed out waiting for completion"

log "Checking that enrichment rows exist..."
ROWS_COUNT="$(python - <<PY
import json,sys
j=json.loads(sys.stdin.read())
bq=j.get("bioquery") or {}
payload=bq.get("payload") or {}
rows=payload.get("rows") or []
print(len(rows))
PY
<<<"$RAW")"

if [[ "$ROWS_COUNT" -lt 1 ]]; then
  echo "$RAW" | python -m json.tool | head -n 250
  die "COMPLETED but no enrichment rows returned"
fi

log "OK: got $ROWS_COUNT enrichment rows."
log "Smoke test PASSED."

