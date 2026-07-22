// Local-dev per-user project assignments (the scoping seam). Idempotent (upserts).
// Powers Projects-API GET /portfolio-summary with an `X-User-Key` header:
// a known user with assignments gets a portfolio scoped to just their projects.
// Not production data — replaced by real RBAC/assignments once identity lands.
//   mongosh "mongodb://localhost:27017/epi_os" Database/MongoDB/seed/003_project_assignments.js
//
// Docs: { org_id, user_key, project_key, role }  role in owner|manager|member

const db = db.getSiblingDB("epi_os");
const ORG = "default";

// Keep the per-user lookup indexed (matches the DAO's defensive index).
db.project_assignments.createIndex({ user_key: 1 });
db.project_assignments.createIndex({ org_id: 1, user_key: 1 });

// director -> every project currently in the evidence store (portfolio owner).
const allKeys = db.projects.distinct("project_key");

// Managers own a real subset of the ingested/seeded project keys.
const assignments = [
  ...allKeys.map((k) => ({ user_key: "director", project_key: k, role: "owner" })),
  ...["Sakai", "Spring", "Sonatype", "JiraEcosystem"].map((k) => ({
    user_key: "mgr-apac", project_key: k, role: "manager",
  })),
  ...["MariaDB", "Hyperledger", "IntelDAOS", "Mindville"].map((k) => ({
    user_key: "mgr-data", project_key: k, role: "manager",
  })),
];

for (const a of assignments) {
  db.project_assignments.updateOne(
    { org_id: ORG, user_key: a.user_key, project_key: a.project_key },
    { $set: { org_id: ORG, user_key: a.user_key, project_key: a.project_key, role: a.role } },
    { upsert: true },
  );
}

print(
  `seeded ${db.project_assignments.countDocuments({})} assignments across users: ` +
  db.project_assignments.distinct("user_key").join(", "),
);
