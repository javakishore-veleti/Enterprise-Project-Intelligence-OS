#!/usr/bin/env bash
# Control the Angular portals for local development.
#
#   portals.sh start-all | stop-all | status-all
#
# On start-all each portal runs `npm install` first, so developers never run it
# manually after adding a dependency. PIDs/logs live under .run/.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
RUN_DIR="$HERE/.run"
mkdir -p "$RUN_DIR"

# portal-dir : port
PORTALS=(
  "Portals/Admin:4200"
  "Portals/Project-Tracker:4201"
)

cmd="${1:-status-all}"
for entry in "${PORTALS[@]}"; do
  IFS=":" read -r dir port <<< "$entry"
  path="$REPO_ROOT/$dir"
  name="$(basename "$dir")"
  pidfile="$RUN_DIR/portal-$name.pid"

  case "$cmd" in
    start-all)
      [[ -f "$path/package.json" ]] || { echo "skip     $name (not scaffolded yet)"; continue; }
      echo "install  $name (npm install) ..."
      ( cd "$path" && npm install --silent )
      echo "start    $name on :$port"
      ( cd "$path" && nohup npm start -- --port "$port" > "$RUN_DIR/portal-$name.log" 2>&1 & echo $! > "$pidfile" )
      ;;
    stop-all)
      if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
        kill "$(cat "$pidfile")" && echo "stopped  $name"
      else
        echo "not-run  $name"
      fi
      rm -f "$pidfile"
      ;;
    status-all)
      if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
        printf "%-18s running   pid %-8s :%s\n" "$name" "$(cat "$pidfile")" "$port"
      else
        printf "%-18s stopped   %-12s :%s\n" "$name" "-" "$port"
      fi
      ;;
    *) echo "usage: portals.sh start-all|stop-all|status-all"; exit 2 ;;
  esac
done
