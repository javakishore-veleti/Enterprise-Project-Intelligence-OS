// Local-dev sample EVIDENCE (issues / histories / links) so deterministic metric
// computation produces meaningful numbers before the real 5.8GB dataset is ingested.
// Idempotent-ish: clears the sample docs it owns, then re-inserts.
//   mongosh "mongodb://localhost:27017/epi_os" Database/MongoDB/seed/002_sample_evidence.js
//
// Schema matches projects_api metric computation (tune once real archive is known):
//   issues:          {issue_key, project_key, status, priority, created_at, resolved_at}
//   issue_histories: {issue_key, project_key, field, to_value}
//   issue_links:     {source_issue_key, target_issue_key, link_type, project_key}

const db = db.getSiblingDB("epi_os");
const OPEN = ["Open", "In Progress"];
const REF = new Date("2025-06-01T00:00:00Z");
const days = (d) => new Date(REF.getTime() - d * 86400000);

// per-project: [count, openFrac, blockers, reopened, recentCreated, recentResolved, chainDepth]
const plan = {
  APACHE: [40, 0.35, 5, 4, 8, 2, 4],
  SPARK:  [24, 0.20, 1, 1, 3, 3, 2],
  KAFKA:  [18, 0.30, 3, 2, 5, 1, 3],
  FLINK:  [30, 0.45, 4, 3, 9, 2, 3],
};

for (const [pk, [n, openFrac, blockers, reopened, recNew, recRes, depth]] of Object.entries(plan)) {
  db.issues.deleteMany({ project_key: pk });
  db.issue_histories.deleteMany({ project_key: pk });
  db.issue_links.deleteMany({ project_key: pk });

  const openCount = Math.round(n * openFrac);
  const issues = [];
  for (let i = 0; i < n; i++) {
    const isOpen = i < openCount;
    // recent-created spread across the last 30 days; the rest are old.
    const created = i < recNew ? days(i % 30) : days(60 + i);
    const resolved = isOpen ? null : (i < openCount + recRes ? days((i % 20)) : days(90 + i));
    issues.push({
      issue_key: `${pk}-${i}`, project_key: pk,
      status: isOpen ? OPEN[i % 2] : "Resolved",
      priority: i < blockers ? "Blocker" : (i % 3 === 0 ? "Major" : "Minor"),
      created_at: created, resolved_at: resolved,
    });
  }
  db.issues.insertMany(issues);

  // reopened issues (must reference resolved ones)
  const hist = [];
  for (let i = 0; i < reopened; i++) {
    hist.push({ issue_key: `${pk}-${openCount + i}`, project_key: pk, field: "status", to_value: "Reopened" });
  }
  if (hist.length) db.issue_histories.insertMany(hist);

  // a dependency chain of the requested depth: -0 -> -1 -> ... -> -(depth-1)
  const links = [];
  for (let i = 0; i < depth - 1; i++) {
    links.push({ project_key: pk, source_issue_key: `${pk}-${i}`, target_issue_key: `${pk}-${i + 1}`, link_type: "blocks" });
  }
  if (links.length) db.issue_links.insertMany(links);
}

print("seeded sample evidence for: " + Object.keys(plan).join(", "));
print("issues=" + db.issues.countDocuments({}) + " histories=" + db.issue_histories.countDocuments({}) +
      " links=" + db.issue_links.countDocuments({}));
