#!/usr/bin/env bash
# Bring up local infra (MongoDB, PostgreSQL, ChromaDB, Airflow), reusing any
# container that is already running on the laptop. Idempotent.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"

# Load repo .env if present so compose interpolation matches the app.
if [[ -f "$REPO_ROOT/.env" ]]; then
  set -a; source "$REPO_ROOT/.env"; set +a
fi

# name:container:compose-subdir  (start order matters: datastores before Airflow)
SERVICES=(
  "MongoDB:local-mongodb:MongoDB"
  "PostgreSQL:local-postgres:PostgreSQL"
  "ChromaDB:local-chromadb:ChromDB"
  "Airflow:local-airflow:Airflow"
)

# Airflow is optional and heavy; skip unless WITH_AIRFLOW=1.
WITH_AIRFLOW="${WITH_AIRFLOW:-0}"

for entry in "${SERVICES[@]}"; do
  IFS=":" read -r name container subdir <<< "$entry"
  if [[ "$name" == "Airflow" && "$WITH_AIRFLOW" != "1" ]]; then
    echo "skip     $name (set WITH_AIRFLOW=1 to start)"
    continue
  fi
  if docker ps --format '{{.Names}}' | grep -qx "$container"; then
    echo "reuse    $name (container '$container' already running)"
  else
    echo "starting $name ..."
    docker compose -f "$HERE/$subdir/docker-compose.yaml" up -d
  fi
done

echo "infra up. Run 'status.sh' to check, then apply DB migrations:"
echo "  python \"$REPO_ROOT/Database/PostgreSQL/apply_migrations.py\""
