# Project Manager — Data Product & Delivery

Status date: 2026-10-10. Week numbers allocate requirements; they are not twelve elapsed delivery weeks or a claim of 360 hours spent. Existing implementation predates this branch (baseline 0ed0c17). This branch adds scope correction, Gate 1 artifacts, CI migration targeting and local verification. No gate approval is assumed. The known remaining work below is planned, not implemented.

## Week 1 — Discovery & Architecture

- **Done / implemented:** Authoritative scope reconciled; architecture/ERD/taxonomy/dictionary/backlog authored.
- **Evidence:** Gate 1 packet in docs/.
- **Blockers / remaining:** Gate 1 pending. Planned work below remains incomplete.
- **Decision required:** Sponsor approves ERD/source model/boundary.
- **Next / planned:** Record Gate 1 approval before large implementation.

## Week 2 — Asset Master Foundation

- **Done / implemented:** Fictional fixtures distinguished from real facility coverage.
- **Evidence:** app/seed.py; tests/conftest.py.
- **Blockers / remaining:** Fresh PostgreSQL deployment unverified. Planned work below remains incomplete.
- **Decision required:** Choose source/facility pilot.
- **Next / planned:** Curate 10–15 real facilities across countries/ownership structures.

## Week 3 — Source & Document Registry

- **Done / implemented:** Source priority and governed onboarding procedure proposed.
- **Evidence:** SOURCE_TAXONOMY_v0.1.md.
- **Blockers / remaining:** Gate 2 real retrieval not passed. Planned work below remains incomplete.
- **Decision required:** Approve per-source access/retention basis.
- **Next / planned:** Register high-quality sources and witness real Gate 2 capture.

## Week 4 — Capacity & Attribute Observations

- **Done / implemented:** Temporal/dimensional QA requirements documented.
- **Evidence:** DATA_DICTIONARY_v0.1.md.
- **Blockers / remaining:** Historical baseline exists; dimensions incomplete. Planned work below remains incomplete.
- **Decision required:** Approve unit/QA expected outcomes.
- **Next / planned:** Curate changes, unit differences, source conflicts and ownership changes.

## Week 5 — Entity Resolution

- **Done / implemented:** Manual ambiguity policy captured.
- **Evidence:** ARCHITECTURE.md; ambiguity test.
- **Blockers / remaining:** Gate 3 real facility demonstration pending. Planned work below remains incomplete.
- **Decision required:** Approve labeled matches/escalations.
- **Next / planned:** Create 50 difficult-name benchmark and witness Gate 3.

## Week 6 — Manual Review & Audit Trail

- **Done / implemented:** Existing reviewed decisions inspected.
- **Evidence:** review audit test.
- **Blockers / remaining:** Individual reviewer identity missing. Planned work below remains incomplete.
- **Decision required:** Adopt proposed 2-working-day triage SLA and domain-owner escalation.
- **Next / planned:** Define categories/decision rules and accountable review owner.

## Week 7 — Data Acquisition Adapters

- **Done / implemented:** Source onboarding steps drafted.
- **Evidence:** SOURCE_TAXONOMY_v0.1.md.
- **Blockers / remaining:** Real HTML/PDF/CSV adapter set incomplete. Planned work below remains incomplete.
- **Decision required:** Approve representative source families.
- **Next / planned:** Onboard permitted HTML/PDF/CSV fixtures and maintenance owners.

## Week 8 — Data Quality Engine

- **Done / implemented:** Quality vocabulary/protected requirements documented.
- **Evidence:** dictionary/backlog; bad-fixture tests.
- **Blockers / remaining:** Gate 4 partial technical evidence only. Planned work below remains incomplete.
- **Decision required:** Approve severity/remediation thresholds.
- **Next / planned:** Measure findings/coverage and witness Gate 4 corrupt-fixture demo.

## Week 9 — Evidence Versioning & Reproducibility

- **Done / implemented:** Output restoration distinguished from acquisition replay.
- **Evidence:** ARCHITECTURE.md; bundle test.
- **Blockers / remaining:** Frozen-input parser rerun absent. Planned work below remains incomplete.
- **Decision required:** Approve frozen inputs and equivalence definition.
- **Next / planned:** Run same frozen inputs/version twice; compare logical output.

## Week 10 — Commodity Evidence Package v1

- **Done / implemented:** Draft version retained; upstream-only boundary documented.
- **Evidence:** ARCHITECTURE.md; package.schema.json.
- **Blockers / remaining:** Gate 5 v1 freeze pending. Planned work below remains incomplete.
- **Decision required:** Consumer/sponsor Gate 5 contract approval.
- **Next / planned:** Publish field explanations and breaking-version policy.

## Week 11 — Hardening & Integration Simulation

- **Done / implemented:** Local validation evidence recorded without production claims.
- **Evidence:** VALIDATION.md.
- **Blockers / remaining:** PostgreSQL/Docker/full UAT not verified. Planned work below remains incomplete.
- **Decision required:** Assign UAT owner and test environment.
- **Next / planned:** End-to-end UAT and real coverage target 50–100 meaningful facilities.

## Week 12 — Final Release & Handover

- **Done / implemented:** Three distinct reports and scope-corrected review branch prepared.
- **Evidence:** docs/reports; README.md.
- **Blockers / remaining:** Gate 6 final acceptance pending. Planned work below remains incomplete.
- **Decision required:** Sponsor Gate 6 final acceptance.
- **Next / planned:** Release notes/risks/roadmap/handover; target 5–10 verified source families.

