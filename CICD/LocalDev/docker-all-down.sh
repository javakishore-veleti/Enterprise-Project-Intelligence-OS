#!/usr/bin/env bash
# Stop local infra started by docker-all-up.sh.
# By default preserves named volumes (data survives). Pass --volumes to remove.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DOWN_ARGS=()
[[ "${1:-}" == "--volumes" ]] && DOWN_ARGS+=("--volumes")

for subdir in Airflow ChromDB PostgreSQL MongoDB; do
  compose="$HERE/$subdir/docker-compose.yaml"
  [[ -f "$compose" ]] || continue
  echo "stopping $subdir ..."
  docker compose -f "$compose" down "${DOWN_ARGS[@]}" || true
done

echo "infra stopped."
