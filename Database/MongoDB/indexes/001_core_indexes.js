// Core indexes for the project evidence store. Idempotent.
//   mongosh "mongodb://localhost:27017/epi_os" Database/MongoDB/indexes/001_core_indexes.js

const db = db.getSiblingDB("epi_os");

db.projects.createIndex({ project_key: 1 }, { unique: true });
db.issues.createIndex({ project_key: 1, issue_key: 1 }, { unique: true });
db.issues.createIndex({ project_key: 1, status: 1 });
db.issue_histories.createIndex({ issue_key: 1, changed_at: 1 });
db.comments.createIndex({ issue_key: 1, created_at: 1 });
db.issue_links.createIndex({ source_issue_key: 1 });
db.issue_links.createIndex({ target_issue_key: 1 });
db.project_metrics.createIndex({ project_key: 1, computed_at: -1 });

print("core indexes ensured");
