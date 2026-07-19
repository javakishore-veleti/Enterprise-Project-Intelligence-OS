// MongoDB initialization for the project evidence store.
// Idempotent: safe to re-run. Run with:
//   mongosh "mongodb://localhost:27017/epi_os" Database/MongoDB/initialization/001_create_collections.js

const db = db.getSiblingDB("epi_os");

const collections = [
  "projects",
  "issues",
  "issue_histories",
  "comments",
  "issue_links",
  "users",
  "project_metrics",
];

for (const name of collections) {
  if (!db.getCollectionNames().includes(name)) {
    db.createCollection(name);
    print(`created collection: ${name}`);
  } else {
    print(`exists:  ${name}`);
  }
}
