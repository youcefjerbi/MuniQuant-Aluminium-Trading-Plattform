# Software Engineer 2 — Platform & Reliability Engineering

Status date: 2026-10-10. Week numbers allocate requirements; they are not twelve elapsed delivery weeks or a claim of 360 hours spent. Existing implementation predates this branch (baseline 0ed0c17). This branch adds scope correction, Gate 1 artifacts, CI migration targeting and local verification. No gate approval is assumed. The known remaining work below is planned, not implemented.

## Week 1 — Discovery & Architecture

- **Done / implemented:** Architecture authored; active market/trading routes/UI removed.
- **Evidence:** ARCHITECTURE.md; boundary test passes.
- **Blockers / remaining:** Gate 1 pending. Planned work below remains incomplete.
- **Decision required:** Approve architecture/C++ candidate-only ranking proposal.
- **Next / planned:** Implement post-gate acquisition platform.

## Week 2 — Asset Master Foundation

- **Done / implemented:** Existing API/Compose/CI retained; native build succeeds; CI migration URL fixed.
- **Evidence:** 18 tests pass; .github/workflows/ci.yml.
- **Blockers / remaining:** Fresh PostgreSQL deployment unverified. Planned work below remains incomplete.
- **Decision required:** Confirm deployment environment.
- **Next / planned:** Clean PostgreSQL and container verification.

## Week 3 — Source & Document Registry

- **Done / implemented:** Existing pasted UTF-8 capture stores hashes/versions and logs failures.
- **Evidence:** dedup/access tests pass.
- **Blockers / remaining:** Gate 2 real retrieval not passed. Planned work below remains incomplete.
- **Decision required:** Approve permitted hosts/access policy.
- **Next / planned:** Bounded remote retrieval, redirects/address checks, limits/retries.

## Week 4 — Capacity & Attribute Observations

- **Done / implemented:** Python Decimal capacity arithmetic and validation now operate; C++ limited to candidate name distance.
- **Evidence:** native conversion and rejection tests pass.
- **Blockers / remaining:** Historical baseline exists; dimensions incomplete. Planned work below remains incomplete.
- **Decision required:** Approve native ranking benchmark and exact Decimal persistence policy.
- **Next / planned:** Persist exact Decimal values and extend dimensional conversions.

## Week 5 — Entity Resolution

- **Done / implemented:** Unique normalized aliases resolve; native fuzzy candidates never trusted.
- **Evidence:** ambiguity/review test passes.
- **Blockers / remaining:** Gate 3 real facility demonstration pending. Planned work below remains incomplete.
- **Decision required:** Approve 50-name benchmark labels.
- **Next / planned:** Company resolution and real facility capacity demonstration.

## Week 6 — Manual Review & Audit Trail

- **Done / implemented:** Review UI and one-time decision endpoint work.
- **Evidence:** review audit test passes; app/static/app.js.
- **Blockers / remaining:** Individual reviewer identity missing. Planned work below remains incomplete.
- **Decision required:** Select identity provider/roles.
- **Next / planned:** Authenticated reviewer attribution; review SLA support.

## Week 7 — Data Acquisition Adapters

- **Done / implemented:** Pasted text capture and capacity CSV parser operate.
- **Evidence:** CSV idempotency test passes.
- **Blockers / remaining:** Real HTML/PDF/CSV adapter set incomplete. Planned work below remains incomplete.
- **Decision required:** Approve golden source fixtures.
- **Next / planned:** HTML/PDF/structured adapters with page/section/row locators.

## Week 8 — Data Quality Engine

- **Done / implemented:** Invalid facts rejected; warnings and hash-corruption failures operate.
- **Evidence:** bad-observation/corruption tests pass.
- **Blockers / remaining:** Gate 4 partial technical evidence only. Planned work below remains incomplete.
- **Decision required:** Approve INFO/WARN/ERROR/BLOCK policy.
- **Next / planned:** Structured finding codes and complete corruption fixtures.

## Week 9 — Evidence Versioning & Reproducibility

- **Done / implemented:** Freeze/verify/restore reproduces stored output.
- **Evidence:** frozen bundle test passes.
- **Blockers / remaining:** Frozen-input parser rerun absent. Planned work below remains incomplete.
- **Decision required:** Approve logical equivalence rules.
- **Next / planned:** Versioned parser reruns from frozen snapshots, not only restore.

## Week 10 — Commodity Evidence Package v1

- **Done / implemented:** Draft JSON schema export deterministic; market payload empty.
- **Evidence:** export and boundary tests pass.
- **Blockers / remaining:** Gate 5 v1 freeze pending. Planned work below remains incomplete.
- **Decision required:** Consumer/sponsor Gate 5 review.
- **Next / planned:** Closed v1 schema and prohibited-field rejection suite.

## Week 11 — Hardening & Integration Simulation

- **Done / implemented:** Current tests/logs/CI inspected and local suite passes.
- **Evidence:** 18 passed on Python 3.14/SQLite.
- **Blockers / remaining:** PostgreSQL/Docker/full UAT not verified. Planned work below remains incomplete.
- **Decision required:** Confirm PostgreSQL/Docker/UAT environment.
- **Next / planned:** Retries/concurrency/backups/load tests and full UAT.

## Week 12 — Final Release & Handover

- **Done / implemented:** Existing runbook retained; scoped README/reports delivered.
- **Evidence:** README.md; RUNBOOK.md.
- **Blockers / remaining:** Gate 6 final acceptance pending. Planned work below remains incomplete.
- **Decision required:** Sponsor Gate 6 final acceptance.
- **Next / planned:** Final real-source demonstration/deployment/handover.

