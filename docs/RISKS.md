# Risk register and governance

| Risk | Observed state | Mitigation / owner |
|---|---|---|
| Downstream scope/IP exposure | Active market/trading UI/API removed; closed schema blocks prohibited fields | Keep private logic/code out; PM |
| Source access/copyright | Three curated public publisher families; local-retention policies, no redistribution license | Review terms per source before hosting raw snapshots; PM |
| Site/name ambiguity | 50 deliberate cases include collisions, country and normalization differences | No fuzzy auto-trust; audited final manual decisions; SE1/PM |
| Invalid/conflicting facts | Exact/date/dimension checks; overlapping facts and excessive ownership warn | Preserve independent source vintages; curator adjudication; SE1 |
| Snapshot/database divergence | Exact byte hashes, blocking missing/corrupt files | Coordinated backups and deployment restore drill; SE2 |
| Legacy data precision/migration | Exact values backfilled from reported values; populated migration test | Inspect migration failures; preserve IDs, do not round or rewrite source values; SE1 |
| Live publisher change | Different HTML bytes already produced extra versions | Frozen replay, versioned literal recipes and failed-parser logs; SE2 |
| Incomplete coverage | 15 identities, capacity facts for two, three source families | Recommended broader curation 50–100 / 5–10 remains roadmap; PM |
| Unknown publication dates/company provenance | Real pilot has 13 WARN findings | Register explicit source dates/evidence when found; never invent values; PM |
| Shared deployment access | Read-only token/individual writers optional; loopback default | Enable read protection, TLS/private ingress and credential lifecycle; SE2/operations |
| PDF semantics | Portland page 2 mismatched header, no OCR | Extract page 1 only; require exact locator and reviewer context; SE2/PM |
| Performance / native complexity | 500 synthetic load correctness; C++ distance equivalence and 58.75× microbenchmark | No production throughput claims; profile actual deployment; SE2 |
| Human acceptance | Automated technical demo complete; human meetings/sign-off not invented | Sponsor/consumer review artifacts and runbook; PM |

Escalate identity conflicts and access uncertainty to the project owner; do not resolve them by inventing metadata. Optional dataset breadth should shrink before provenance, hashing, identity, source linkage, validation, tests, contract or reproducibility (PDF pp.24–25).

The talent-evaluation rubric from PDF p.26 is preserved: SE1—model/migration/temporal/SQL/edge-case quality; SE2—reliability/testing/API/failure/automation/maintainability; PM—technical understanding/priorities/scope/criteria/risk/docs. This repository supplies artifacts to evaluate these competencies; it does not fabricate three months of human contribution or performance ratings.
