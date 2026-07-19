#!/usr/bin/env bash
# Control the FastAPI middleware microservices for local development.
#
#   api-services.sh start-all | stop-all | status-all
#
# Each service runs on its own port. On start-all, every service's Python
# dependencies are installed into a per-service .venv, so developers never run
# pip manually after adding a dependency. PIDs/logs live under .run/.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
RUN_DIR="$HERE/.run"
mkdir -p "$RUN_DIR"

# service-dir : module-path : port
SERVICES=(
  "Middleware/Ingestion-API:ingestion_api.api.main:app:8001"
  "Middleware/Admin-API:admin_api.api.main:app:8002"
  "Middleware/Projects-API:projects_api.api.main:app:8003"
  "Middleware/RiskAnalytics-API:risk_analytics_api.api.main:app:8004"
)

start_one() {
  local dir="$1" module="$2" port="$3"
  local path="$REPO_ROOT/$dir"
  local name; name="$(basename "$dir")"
  [[ -d "$path" ]] || { echo "skip     $name (not scaffolded yet)"; return; }

  if [[ -f "$RUN_DIR/$name.pid" ]] && kill -0 "$(cat "$RUN_DIR/$name.pid")" 2>/dev/null; then
    echo "reuse    $name (already running, pid $(cat "$RUN_DIR/$name.pid"))"
    return
  fi

  echo "install  $name deps ..."
  # Python 3.12 matches the service Dockerfiles and supports every agentic
  # framework we target (LangGraph, CrewAI, OpenAI Agents, Strands, ADK, ...).
  local PY; PY="$(command -v python3.12 || command -v python3)"
  ( cd "$path"
    [[ -d .venv ]] || "$PY" -m venv .venv
    ./.venv/bin/pip install -q --upgrade pip
    # Editable path deps (sibling repo packages), one repo-relative path per line.
    if [[ -f local-deps.txt ]]; then
      while IFS= read -r dep || [[ -n "$dep" ]]; do
        [[ -z "$dep" || "$dep" == \#* ]] && continue
        ./.venv/bin/pip install -q -e "$REPO_ROOT/$dep"
      done < local-deps.txt
    fi
    ./.venv/bin/pip install -q -e ".[dev]"
  )

  echo "start    $name on :$port"
  ( cd "$path"
    nohup ./.venv/bin/uvicorn "$module" --host 0.0.0.0 --port "$port" \
      > "$RUN_DIR/$name.log" 2>&1 &
    echo $! > "$RUN_DIR/$name.pid"
  )
}

stop_one() {
  local name; name="$(basename "$1")"
  local pidfile="$RUN_DIR/$name.pid"
  if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    kill "$(cat "$pidfile")" && echo "stopped  $name"
  else
    echo "not-run  $name"
  fi
  rm -f "$pidfile"
}

status_one() {
  local dir="$1" port="$3"
  local name; name="$(basename "$dir")"
  local pidfile="$RUN_DIR/$name.pid"
  if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    printf "%-16s running   pid %-8s :%s\n" "$name" "$(cat "$pidfile")" "$port"
  else
    printf "%-16s stopped   %-12s :%s\n" "$name" "-" "$port"
  fi
}

cmd="${1:-status-all}"
for entry in "${SERVICES[@]}"; do
  IFS=":" read -r dir mod app port <<< "$entry"
  module="$mod:$app"
  case "$cmd" in
    start-all)  start_one "$dir" "$module" "$port" ;;
    stop-all)   stop_one "$dir" ;;
    status-all) status_one "$dir" "$module" "$port" ;;
    *) echo "usage: api-services.sh start-all|stop-all|status-all"; exit 2 ;;
  esac
done
