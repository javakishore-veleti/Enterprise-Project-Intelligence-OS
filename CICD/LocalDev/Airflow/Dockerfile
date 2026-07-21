# Custom Airflow worker image for Enterprise Project Intelligence OS.
#
# The stock apache/airflow image lacks two things the operational DAGs need, and
# `PIP_ADDITIONAL_REQUIREMENTS` is IGNORED under `command: standalone`, so we bake
# them in rather than installing at runtime (which is lost on container restart):
#   - mongodb-database-tools (`mongorestore`) — the project_dataset_ingest DAG
#     restores the JiraReposAnon mongodump into the staging DB.
#   - pymongo + requests — the DAGs' Mongo client and HTTP client.
FROM apache/airflow:2.10.0-python3.12

# --- mongorestore (arch-aware; MongoDB has no debian-bookworm arm64 apt pkg) ---
USER root
ARG MONGO_TOOLS_VERSION=100.10.0
RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
      arm64) pkg="ubuntu2204-arm64" ;; \
      amd64) pkg="ubuntu2204-x86_64" ;; \
      *) echo "unsupported arch: $arch" >&2; exit 1 ;; \
    esac; \
    curl -fsSL "https://fastdl.mongodb.org/tools/db/mongodb-database-tools-${pkg}-${MONGO_TOOLS_VERSION}.tgz" -o /tmp/tools.tgz; \
    tar -xzf /tmp/tools.tgz -C /tmp; \
    cp /tmp/mongodb-database-tools-*/bin/mongorestore /usr/local/bin/mongorestore; \
    chmod +x /usr/local/bin/mongorestore; \
    rm -rf /tmp/tools.tgz /tmp/mongodb-database-tools-*; \
    mongorestore --version | head -1

# --- Python deps used by the DAG task callables ---
USER airflow
RUN pip install --no-cache-dir "pymongo>=4.8" "requests>=2.31.0"
