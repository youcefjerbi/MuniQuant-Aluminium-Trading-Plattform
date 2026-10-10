# Validation — 2026-10-10

Baseline 0ed0c17; branch codex/upstream-evidence-gate1; PR #2. Scope implementation approved by sponsor.

| Check | Actual evidence |
|---|---|
| Local suite | 64 passed on macOS / Python 3.14; one Starlette/httpx deprecation warning |
| PostgreSQL and SQLite CI | 64-test release implementation commit 9d8a198 passes both database jobs, migration round trips, schema checks, PostgreSQL container runtime/seed/freeze/replay/export smoke and coordinated PostgreSQL/snapshot restore equivalence |
| Exact values/dimensions | Decimal 24 integer / 6 fractional digits, t/kt/Mt per year, MW, percentage, status; invalid/nonfinite/negative/unit/date facts rejected |
| Master/resolution | Controlled references, company matching, audited aliases/supersession; 50 difficult names preserve ambiguity |
| Review/auth | Final immutable audited decisions create candidate facts/aliases; newly verified candidates can be attached; individual writers and optional read-only credentials tested |
| Acquisition | Real official URLs captured; mocked TLS/public-IP pin/redirect/size/retry policy fixtures; durable retrieval and parser-failure manifests |
| Adapters | Configurable HTML/PDF/CSV; original binary PDF retained and exact page locator; status CSV replay and bad-status tests |
| Quality/boundary | Missing/corrupt provenance, bad dimensions, conflicts/ambiguity fail or warn predictably; all ten prohibited fields rejected; active market/trading routes absent |
| Reproducibility | Real frozen bundle re-extracts three candidates/builds, equivalent build hash; zero manually entered observation records; tamper/missing-output tests reject |
| Load/concurrency/migrations | 500 labelled synthetic facilities/facts import/export; pagination; concurrent duplicate imports retain one build/fact; populated legacy migration preserves high-precision source value/ID/hash/alias |
| Additional contract integrity | Local identity/registry consistency and rejected-build input provenance checks pass; final SQLite/PostgreSQL and recovery CI passes |
| Consumer | Independent example validates closed schema and traces source/document/locator without database or private downstream code |
| UI | Browser preview verified real 15-facility overview and Portland sourced capacity; JavaScript syntax check passes; quality/read-token/download/value display synchronized with backend |
| Local Docker | Daemon stopped; no local container runtime result claimed |
| Recommended real coverage | 15 facilities / three families; recommended 50–100 / 5–10 not yet achieved; capacity data covers two facilities only |

Verified release implementation CI: https://github.com/youcefjerbi/MuniQuant-Aluminium-Trading-Plattform/actions/runs/38087340435 . All SQLite/PostgreSQL, migration, schema, container and coordinated recovery checks passed at 9d8a198. Earlier implementation checks also passed at 56cfa78. One intermediate restore smoke failed on copied snapshot permissions; preserving appuser ownership fixed it and the final restore reproduced the exact package hash.

Real pilot: ten registered document versions from seven configured official URLs, five companies, 15 facilities across three countries, three parsed capacity records and four owner/operator relations. Quality WARN: 13 findings, no BLOCK/ERROR. Publication dates are unknown for eight documents and five company identity records lack explicit identity locators. No metadata invented to make quality PASS.

Frozen hash: 415879f2f8a9c5feae9f966947f9be1765b3dd1bb9d490141d7294296edf59e2. Native microbenchmark verified equal output, 1,000 Unicode pairs, measured 58.75× speedup; no whole-pipeline performance claim.

Human meetings, actual 360 person-hours, operational SLA attainment, private consumer sign-off, final sponsor acceptance and production certification are not fabricated. Raw publisher snapshots are retained in local deliverables, not uploaded to this public repository.
