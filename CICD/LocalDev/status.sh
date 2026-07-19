#!/usr/bin/env bash
# Report status of local infra containers.
set -euo pipefail

CONTAINERS=("local-mongodb" "local-postgres" "local-chromadb" "local-airflow")

printf "%-16s %-10s %s\n" "SERVICE" "STATE" "PORTS"
for c in "${CONTAINERS[@]}"; do
  if docker ps --format '{{.Names}}' | grep -qx "$c"; then
    ports="$(docker ps --filter "name=^${c}$" --format '{{.Ports}}')"
    printf "%-16s %-10s %s\n" "$c" "running" "$ports"
  elif docker ps -a --format '{{.Names}}' | grep -qx "$c"; then
    printf "%-16s %-10s %s\n" "$c" "stopped" "-"
  else
    printf "%-16s %-10s %s\n" "$c" "absent" "-"
  fi
done
