# Airflow test fixtures

## `real_jira_issue.json` — CONFIRMED real shape (verified 2026-07-21)

`test_real_jira_issue_fixture_maps_cleanly` locks `transform_issue` against the
real dataset's document shape. The file is **synthetic** (fabricated values) but
its **structure is faithful** to what was verified live against a Mindville
restore of the public `JiraReposAnon` mongodump — the dataset itself stays out of
the repo per its license, so we commit the shape, not the data.

**What the live probe confirmed:** the dump is
`mongodump --db=JiraReposAnon --gzip --archive` (one collection per repo).
`key` / `fields.status.name` / `fields.created` at 100%; `priority` /
`resolutiondate` / `issuelinks` present where expected; status changes come from
`changelog.histories[].items[]` where `field=="status"` (`toString`), authors are
anonymized `<<|author_*|uuid|>>` tokens, links from `issuelinks[].type.name` +
`outwardIssue.key`. **The dataset has NO `fields.comment`** — comments are absent
everywhere, so the fixture omits them and the test asserts zero comments.

## Re-verifying (another repo, or after a fresh download)

The mapping was confirmed without the full ~60 GB restore — probe one repo:

```bash
# 1. Get the archive local (Admin portal -> Initial Dataset, or a direct Zenodo pull).
# 2. Restore ONE repo only (fast, a few hundred MB):
mongorestore --gzip --archive=mongodump-JiraReposAnon.archive \
  --nsInclude='JiraReposAnon.<repo>' --nsTo='jira_repos.<repo>'

# 3. Probe every restored collection against transform_issue's expected paths:
python -m project_dataset_ingest.probe_schema \
  --uri mongodb://localhost:27017 --db jira_repos --sample 200 --show-example

# 4. Save one real doc here to regression-lock the mapping:
mongosh jira_repos --quiet --eval \
  'JSON.stringify(db.getCollection("<repo>").findOne())' \
  > Airflow/tests/fixtures/real_jira_issue.json
```

If the probe flags a path below 100% (or `test_real_jira_issue_fixture...` fails
on `status Unknown`), update the path in
`Airflow/dags/project_dataset_ingest/tasks.py::transform_issue` (and
`EXPECTED_PATHS` alongside it) to the real field name, then re-run the tests.

Do **not** commit a real doc containing anything sensitive — the dataset is
already author-anonymized, but scrub any free-text you're unsure about first.
