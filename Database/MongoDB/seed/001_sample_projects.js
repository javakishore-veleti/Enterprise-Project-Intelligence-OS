// Local-dev sample data for the project evidence store. Idempotent (upserts).
// Not production data — remove once real ingestion populates the store.
//   mongosh "mongodb://localhost:27017/epi_os" Database/MongoDB/seed/001_sample_projects.js

const db = db.getSiblingDB("epi_os");

const projects = [
  { project_key: "APACHE", name: "Apache HTTP Server", category: "infrastructure", issue_count: 1240, open_issue_count: 310 },
  { project_key: "SPARK", name: "Apache Spark", category: "data", issue_count: 980, open_issue_count: 145 },
  { project_key: "KAFKA", name: "Apache Kafka", category: "data", issue_count: 760, open_issue_count: 88 },
  { project_key: "FLINK", name: "Apache Flink", category: "data", issue_count: 640, open_issue_count: 120 },
];

for (const p of projects) {
  db.projects.updateOne({ project_key: p.project_key }, { $set: p }, { upsert: true });
}

db.project_metrics.updateOne(
  { project_key: "APACHE", computed_at: new Date("2026-07-01T00:00:00Z") },
  { $set: {
      project_key: "APACHE",
      computed_at: new Date("2026-07-01T00:00:00Z"),
      backlog_growth: 0.18,
      reopen_rate: 0.07,
      blocker_count: 5,
      dependency_depth: 4,
  } },
  { upsert: true },
);

print(`seeded ${db.projects.countDocuments({})} projects, ${db.project_metrics.countDocuments({})} metric docs`);
