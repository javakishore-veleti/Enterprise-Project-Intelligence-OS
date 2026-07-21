# TODOS

Status of remaining work on the Enterprise Project Intelligence OS platform.
Legend: ✅ done · 🔲 open (optional) · 🚧 in progress · ⛔ blocked (needs external action)

_Last updated: 2026-07-21_

## Real-data end-to-end run — ✅ DONE

Proven live on the real public Jira dataset (bounded to fit local Docker disk):

- ✅ Download the 5.8 GB Zenodo archive through the governed path (Ingestion-API → Airflow `project_dataset_acquire`), md5-verified, stored on local disk.
- ✅ Confirm `transform_issue` maps the real `mongodump` shape (Mindville restore + `probe_schema`); regression-locked by `Airflow/tests/fixtures/real_jira_issue.json`.
- ✅ Bounded ingest of 10 repos (~337k issues) → normalize to 336,785 issues / 832,864 histories / 122,362 links.
- ✅ Deterministic metrics computed on real evidence (14 projects).
- ✅ Full 7-detector LangGraph/Claude fan-out + review pipeline + 3 reports on Sakai, grounded in the real metrics.
- ✅ Custom `epi-airflow` image bakes in `mongorestore` + `pymongo`/`requests` (survives restart).

## Open / optional

- ⛔ **Ingest the 6 large repos** (Apache ~1M, Mojang, RedHat, Jira, Qt, MongoDB) for the full ~2.7M-issue corpus.
  - Blocked by local Docker Desktop VM disk (~58 GB total / ~30 GB free); the full restore is ~60 GB.
  - Action needed (user): raise Docker Desktop → Resources → Disk to ~100 GB+ and restart Docker. Then re-run ingest without the `repos` filter (or with the remaining repos).

- 🔲 **Clean seed-project metrics.** The `Database/MongoDB/seed/002_sample_evidence.js` seed projects (APACHE, etc.) still carry sample `project_metrics` alongside the 10 real repos. Optional: drop them so only real-data projects remain.

- 🔲 **`airflow standalone` admin password.** `standalone` generates a random admin password and ignores `_AIRFLOW_WWW_USER_*`, so the Ingestion-API's `admin/admin` REST trigger 403s on a fresh metadata DB (worked around by recreating the admin user). Optional: switch to an explicit webserver+scheduler setup or seed a fixed admin so first-boot needs no manual fix.

- 🔲 **Portals against real data.** The Project-Tracker / Admin portals were verified against seed data; spot-check them against the freshly ingested repos (metrics panel, analysis history, per-agent breakdown).

## Notes

- The full real dataset is **not** committed to the repo (its own license); it is acquired at runtime and lives under `Downloads/Datasets/`.
- Remaining alternative-framework adapters (`strands`/`google_adk`/`ms_agent_framework`) stay intentionally deferred — the team runs LangGraph-only for now.
