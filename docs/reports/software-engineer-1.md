# Software Engineer 1 — Data & Domain Engineering

Status date: 2026-10-10. Week numbers allocate requirements; they are not twelve elapsed delivery weeks or a claim of 360 hours spent. Existing implementation predates this branch (baseline 0ed0c17). This branch adds scope correction, Gate 1 artifacts, CI migration targeting and local verification. No gate approval is assumed. The known remaining work below is planned, not implemented.

## Week 1 — Discovery & Architecture

- **Done / implemented:** ERD and migration proposal authored.
- **Evidence:** ERD_v0.1.md; DATA_DICTIONARY_v0.1.md.
- **Blockers / remaining:** Gate 1 pending. Planned work below remains incomplete.
- **Decision required:** Approve identity/schema model.
- **Next / planned:** Build additive normalized master tables.

## Week 2 — Asset Master Foundation

- **Done / implemented:** Existing entity/relationship tables retained.
- **Evidence:** app/models.py; FK test passes.
- **Blockers / remaining:** Fresh PostgreSQL deployment unverified. Planned work below remains incomplete.
- **Decision required:** Approve backfill policy.
- **Next / planned:** Company/facility/type/country/region/product/alias references; clean migration tests.

## Week 3 — Source & Document Registry

- **Done / implemented:** Existing source/document/version/hash persistence retained.
- **Evidence:** evidence dedup/version test passes.
- **Blockers / remaining:** Gate 2 real retrieval not passed. Planned work below remains incomplete.
- **Decision required:** Approve source-access model.
- **Next / planned:** Separate source_access/document_version/source_document_relation histories.

## Week 4 — Capacity & Attribute Observations

- **Done / implemented:** Existing sourced capacity/status history appends.
- **Evidence:** historical observation test passes.
- **Blockers / remaining:** Historical baseline exists; dimensions incomplete. Planned work below remains incomplete.
- **Decision required:** Approve native-date/Decimal dimension policy.
- **Next / planned:** Native dates, Decimal values, MW/percentage and conflicting vintages.

## Week 5 — Entity Resolution

- **Done / implemented:** Existing aliases preserve ambiguous candidates.
- **Evidence:** ambiguity test passes.
- **Blockers / remaining:** Gate 3 real facility demonstration pending. Planned work below remains incomplete.
- **Decision required:** Approve supersession/merge policy.
- **Next / planned:** Relational aliases, company matching, merge/supersession history.

## Week 6 — Manual Review & Audit Trail

- **Done / implemented:** Existing decisions record candidate/entity/reason/actor/time.
- **Evidence:** review audit test passes.
- **Blockers / remaining:** Individual reviewer identity missing. Planned work below remains incomplete.
- **Decision required:** Approve immutable history/identity policy.
- **Next / planned:** Authenticated review decisions and complete decision history.

## Week 7 — Data Acquisition Adapters

- **Done / implemented:** Existing CSV persistence is atomic.
- **Evidence:** CSV atomicity test passes.
- **Blockers / remaining:** Real HTML/PDF/CSV adapter set incomplete. Planned work below remains incomplete.
- **Decision required:** Approve evidence locator format.
- **Next / planned:** Persist extracted versioned HTML/PDF/CSV candidates.

## Week 8 — Data Quality Engine

- **Done / implemented:** Existing FK/nonnegative/interval model checks inspected.
- **Evidence:** app/models.py; rejection tests pass.
- **Blockers / remaining:** Gate 4 partial technical evidence only. Planned work below remains incomplete.
- **Decision required:** Approve invariant and finding severity policy.
- **Next / planned:** Known dimensional units/attribute constraints; fix migration constraint loss.

## Week 9 — Evidence Versioning & Reproducibility

- **Done / implemented:** Changed documents remain distinct; stored package restoration works.
- **Evidence:** frozen bundle restore test passes.
- **Blockers / remaining:** Frozen-input parser rerun absent. Planned work below remains incomplete.
- **Decision required:** Approve stable logical keys.
- **Next / planned:** Versioned parser/input persistence for equivalent frozen-input reruns.

## Week 10 — Commodity Evidence Package v1

- **Done / implemented:** Draft export mappings retained with market rows excluded.
- **Evidence:** export/boundary tests pass.
- **Blockers / remaining:** Gate 5 v1 freeze pending. Planned work below remains incomplete.
- **Decision required:** Consumer/sponsor Gate 5 freeze.
- **Next / planned:** Explicit required v1 mappings and schema compatibility fixtures.

## Week 11 — Hardening & Integration Simulation

- **Done / implemented:** Indexes and migration history inspected.
- **Evidence:** migrations/versions; local migration round trip.
- **Blockers / remaining:** PostgreSQL/Docker/full UAT not verified. Planned work below remains incomplete.
- **Decision required:** Approve deployment verification environment.
- **Next / planned:** PostgreSQL migration/integrity/load/conflict tests.

## Week 12 — Final Release & Handover

- **Done / implemented:** Schema dictionary proposal and role report delivered.
- **Evidence:** DATA_DICTIONARY_v0.1.md; this report.
- **Blockers / remaining:** Gate 6 final acceptance pending. Planned work below remains incomplete.
- **Decision required:** Sponsor Gate 6 acceptance.
- **Next / planned:** Finalize migrations/schema docs after implementation.

