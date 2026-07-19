# Repo-wide Tests

Cross-service suites that exercise the platform as a whole (per-service unit,
integration, and contract tests live inside each service under its own `tests/`).

- `end_to_end/` — flows spanning ingestion → evidence → analysis → reports.
- `performance/` — load and throughput.
- `resilience/` — failure injection and recovery.
- `fixtures/` — shared datasets and factories.
