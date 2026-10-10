# Software Engineer 1 — Data & Domain Engineering

Status: 2026-10-10. Sponsor authorized implementation. These are requirement-week allocations, not twelve elapsed weeks, meetings or 360 hours actually worked. Completed items refer to operational code and demonstrated artifacts. Remaining work and human acceptance are explicit.

## Week 1 — Discovery & Architecture

- **Done / implemented:** Designed and implemented the approved upstream domain boundary.
- **Evidence:** docs/ARCHITECTURE.md; ERD_v0.1.md
- **Blockers / remaining:** Keep private downstream models outside this repository.
- **Decision required:** No implementation authorization pending; follow the documented governance policy.
- **Next / planned:** Continue verification and artifacts for requirement week 2; subsequent sections state the work actually delivered.

## Week 2 — Asset Master Foundation

- **Done / implemented:** Added company/facility specializations, relational aliases, countries, regions, types, commodities and sourced company-facility relationships.
- **Evidence:** app/models.py; additive migrations; controlled-schema tests
- **Blockers / remaining:** Broaden curated real data beyond the 15-facility pilot.
- **Decision required:** No implementation authorization pending; follow the documented governance policy.
- **Next / planned:** Continue verification and artifacts for requirement week 3; subsequent sections state the work actually delivered.

## Week 3 — Source & Document Registry

- **Done / implemented:** Added audited source access, document-version/snapshot linkage and source-document relations.
- **Evidence:** source_access, document_version, source_snapshot, source_document_relation; real capture logs
- **Blockers / remaining:** Review publisher terms before shared redistribution.
- **Decision required:** No implementation authorization pending; follow the documented governance policy.
- **Next / planned:** Continue verification and artifacts for requirement week 4; subsequent sections state the work actually delivered.

## Week 4 — Capacity & Attribute Observations

- **Done / implemented:** Persisted native date intervals and exact Decimal capacity, power and percentage facts; capacity/status specialization views retain history.
- **Evidence:** ObservationDetail; decimal precision and historical/conflict tests
- **Blockers / remaining:** Curate more sourced historical change dates.
- **Decision required:** No implementation authorization pending; follow the documented governance policy.
- **Next / planned:** Continue verification and artifacts for requirement week 5; subsequent sections state the work actually delivered.

## Week 5 — Entity Resolution

- **Done / implemented:** Added normalized aliases, company matching and audited supersession with cycle prevention.
- **Evidence:** app/domain.py; 50-name benchmark and supersession tests
- **Blockers / remaining:** Expand domain-specific alias evidence with dataset coverage.
- **Decision required:** No implementation authorization pending; follow the documented governance policy.
- **Next / planned:** Continue verification and artifacts for requirement week 6; subsequent sections state the work actually delivered.

## Week 6 — Manual Review & Audit Trail

- **Done / implemented:** Recorded final decisions with selected entity, reviewer, reason, time and candidate IDs; newly verified identities can be attached with audit.
- **Evidence:** review decision/candidate endpoints; immutable-decision and review-to-observation tests
- **Blockers / remaining:** Apply the documented two-business-day review service target operationally.
- **Decision required:** No implementation authorization pending; follow the documented governance policy.
- **Next / planned:** Continue verification and artifacts for requirement week 7; subsequent sections state the work actually delivered.

## Week 7 — Data Acquisition Adapters

- **Done / implemented:** Persisted deterministic extracted candidates and observations transactionally.
- **Evidence:** EvidenceBuild/Candidate; CSV atomicity and HTML/PDF fixtures
- **Blockers / remaining:** More complicated publisher tables may need source-specific configuration.
- **Decision required:** No implementation authorization pending; follow the documented governance policy.
- **Next / planned:** Continue verification and artifacts for requirement week 8; subsequent sections state the work actually delivered.

## Week 8 — Data Quality Engine

- **Done / implemented:** Added FK, date, range and known-dimension checks; retained conflicting facts and exact ownership shares.
- **Evidence:** dimension migration; conflict warnings; invalid SQL and numeric tests
- **Blockers / remaining:** Warnings require curator decisions; they are not silently adjudicated.
- **Decision required:** No implementation authorization pending; follow the documented governance policy.
- **Next / planned:** Continue verification and artifacts for requirement week 9; subsequent sections state the work actually delivered.

## Week 9 — Evidence Versioning & Reproducibility

- **Done / implemented:** Preserved materially different document versions, immutable bytes and stable build/candidate identities.
- **Evidence:** pilot frozen replay: three builds/records, equivalent hash
- **Blockers / remaining:** Maintain parser versions when transformations change.
- **Decision required:** No implementation authorization pending; follow the documented governance policy.
- **Next / planned:** Continue verification and artifacts for requirement week 10; subsequent sections state the work actually delivered.

## Week 10 — Commodity Evidence Package v1

- **Done / implemented:** Mapped exact facts, identities, aliases, relationships and provenance into closed v1 records.
- **Evidence:** app/contract.py; evidence-v1.schema.json; independent consumer example
- **Blockers / remaining:** Breaking changes must increment contract version.
- **Decision required:** No implementation authorization pending; follow the documented governance policy.
- **Next / planned:** Continue verification and artifacts for requirement week 11; subsequent sections state the work actually delivered.

## Week 11 — Hardening & Integration Simulation

- **Done / implemented:** Exercised 500 synthetic facilities/facts, paginated reads, concurrent import deduplication and populated legacy-data migration.
- **Evidence:** tests/test_hardening.py; migration check; SQLite and PostgreSQL CI
- **Blockers / remaining:** 500 fixtures prove load correctness, not production throughput.
- **Decision required:** No implementation authorization pending; follow the documented governance policy.
- **Next / planned:** Continue verification and artifacts for requirement week 12; subsequent sections state the work actually delivered.

## Week 12 — Final Release & Handover

- **Done / implemented:** Delivered migrations, actual schema dictionary and setup documentation.
- **Evidence:** README.md; RUNBOOK.md; role report; frozen real-source artifact
- **Blockers / remaining:** Coordinate operational backup/restore and broader curation before shared production.
- **Decision required:** Final sponsor handover acceptance remains a human decision.
- **Next / planned:** Broader curation and operational deployment acceptance from the roadmap.

