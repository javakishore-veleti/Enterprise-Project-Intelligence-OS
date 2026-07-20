# Airflow test fixtures

## `real_jira_issue.json` (add after a partial restore)

`test_real_jira_issue_fixture_maps_cleanly` **skips** until this file exists.

The DAG's `transform_issue` maps standard Jira-REST-v2 issue documents into our
evidence rows. The real Zenodo dataset is an **anonymized** `mongodump`
(`JiraReposAnon`), so before a full ingest we confirm the real document shape
matches what the mapper reads. To capture a real sample without the full
~60 GB restore:

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
