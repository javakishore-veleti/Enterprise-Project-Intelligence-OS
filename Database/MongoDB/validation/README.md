# MongoDB Schema Validation

JSON Schema validators (`db.runCommand({ collMod, validator })`) for the
evidence collections. Added incrementally as the evidence model stabilizes so
malformed documents are rejected at write time.
