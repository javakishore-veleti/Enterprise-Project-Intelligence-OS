# Evidence backfills

One-off, idempotent scripts that fill fields onto already-ingested `epi_os`
evidence which newer ingestion writes but older evidence lacks. Safe to re-run.

## `backfill_release_fields.py` — release / component / tag

Phase 2a made `transform_issue` capture `fix_versions` / `components` / `labels`
onto every evidence issue, but only for **future** ingests. This backfills the
same three arrays onto existing `epi_os.issues` documents by reading the raw
`jira_repos.<repo>` dump collections and `$set`ting the fields on the matching
evidence doc (matched on `issue_key == raw key`). It only ever touches those three
fields and never creates evidence rows, so it is idempotent.

Needs `pymongo` — reuse the Projects-API venv (created by `api-services.sh`):

```bash
# all raw repos in jira_repos -> epi_os.issues
./Middleware/Projects-API/.venv/bin/python \
    Database/MongoDB/backfill/backfill_release_fields.py

# bounded smoke-run against one repo
./Middleware/Projects-API/.venv/bin/python \
    Database/MongoDB/backfill/backfill_release_fields.py --repos Sakai --limit 200
```

Env overrides: `MONGO_URI` (default `mongodb://localhost:27017`), `EVIDENCE_DB`
(`epi_os`), `STAGING_DB` (`jira_repos`). Flags: `--repos R1,R2`, `--limit N`
(0 = no cap), `--batch-size N`.

It logs per-repo `scanned` / `matched` / `modified` counts and a final total.
`matched` = evidence docs found for a raw key; `modified` = docs whose field
values actually changed (0 on a re-run once values are already set).
