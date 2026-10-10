# Software Engineer 2 — Platform & Reliability Engineering

Status: 2026-10-10. Sponsor authorized implementation. These are requirement-week allocations, not twelve elapsed weeks, meetings or 360 hours actually worked. Completed items refer to operational code and demonstrated artifacts. Remaining work and human acceptance are explicit.

## Week 1 — Discovery & Architecture

- **Done / implemented:** Implemented the approved Python modular service and upstream export boundary; removed active trading routes/screens.
- **Evidence:** FastAPI; static UI; upstream-boundary tests
- **Blockers / remaining:** No downstream code or analytical outputs are included.
- **Decision required:** No implementation authorization pending; follow the documented governance policy.
- **Next / planned:** Continue verification and artifacts for requirement week 2; subsequent sections state the work actually delivered.

## Week 2 — Asset Master Foundation

- **Done / implemented:** Provided Docker, migration service, non-root app image, PostgreSQL service and CI matrix.
- **Evidence:** Dockerfile; compose.yaml; GitHub Actions
- **Blockers / remaining:** Local Docker daemon is stopped; container checks run in CI.
- **Decision required:** No implementation authorization pending; follow the documented governance policy.
- **Next / planned:** Continue verification and artifacts for requirement week 3; subsequent sections state the work actually delivered.

## Week 3 — Source & Document Registry

- **Done / implemented:** Implemented bounded HTTPS URL capture, public-address pinning, approved hosts, redirects, retries and durable attempts.
- **Evidence:** app/acquisition.py; real official capture plus transport-policy tests
- **Blockers / remaining:** Live publications can change; preserve and use frozen inputs.
- **Decision required:** No implementation authorization pending; follow the documented governance policy.
- **Next / planned:** Continue verification and artifacts for requirement week 4; subsequent sections state the work actually delivered.

## Week 4 — Capacity & Attribute Observations

- **Done / implemented:** Implemented deterministic Decimal conversion for t/kt/Mt per year, MW and percentage, and status validation.
- **Evidence:** app/services.py; exact precision and invalid-dimension tests
- **Blockers / remaining:** No dimensional inference or market conversions.
- **Decision required:** No implementation authorization pending; follow the documented governance policy.
- **Next / planned:** Continue verification and artifacts for requirement week 5; subsequent sections state the work actually delivered.

## Week 5 — Entity Resolution

- **Done / implemented:** Implemented deterministic resolution and native candidate ranking; never auto-trust fuzzy/ambiguous suggestions.
- **Evidence:** 50 difficult-name cases; equivalent native microbenchmark 58.75× faster
- **Blockers / remaining:** Microbenchmark results are not whole-system throughput.
- **Decision required:** No implementation authorization pending; follow the documented governance policy.
- **Next / planned:** Continue verification and artifacts for requirement week 6; subsequent sections state the work actually delivered.

## Week 6 — Manual Review & Audit Trail

- **Done / implemented:** Connected the UI to audited final review decisions, alias creation and persisted extracted facts; individual write credentials and optional read-only authorization supported.
- **Evidence:** review UI/API; individual-actor and separate-read-token tests
- **Blockers / remaining:** TLS, credential rotation and identity-provider integration remain operations choices.
- **Decision required:** No implementation authorization pending; follow the documented governance policy.
- **Next / planned:** Continue verification and artifacts for requirement week 7; subsequent sections state the work actually delivered.

## Week 7 — Data Acquisition Adapters

- **Done / implemented:** Implemented configurable HTML, PDF and structured CSV adapters over byte-exact snapshots.
- **Evidence:** app/pipeline.py; real Portland PDF and Hydro HTML; CSV fixtures
- **Blockers / remaining:** PDF OCR and arbitrary complex tables are outside the text-adapter capability.
- **Decision required:** No implementation authorization pending; follow the documented governance policy.
- **Next / planned:** Continue verification and artifacts for requirement week 8; subsequent sections state the work actually delivered.

## Week 8 — Data Quality Engine

- **Done / implemented:** Implemented coded severity findings and blocked unsafe exports; UI shows actual backend findings.
- **Evidence:** app/quality.py; corrupt snapshot, ambiguity, metadata, dimensions and conflict tests
- **Blockers / remaining:** WARN findings stay visible for human governance.
- **Decision required:** No implementation authorization pending; follow the documented governance policy.
- **Next / planned:** Continue verification and artifacts for requirement week 9; subsequent sections state the work actually delivered.

## Week 9 — Evidence Versioning & Reproducibility

- **Done / implemented:** Implemented manifest, stable recipes and offline parser reruns; logs parser failures without partial candidate facts.
- **Evidence:** evidence_cli freeze/replay; frozen corruption/missing-output tests
- **Blockers / remaining:** Manual facts receive normalization verification only, explicitly counted.
- **Decision required:** No implementation authorization pending; follow the documented governance policy.
- **Next / planned:** Continue verification and artifacts for requirement week 10; subsequent sections state the work actually delivered.

## Week 10 — Commodity Evidence Package v1

- **Done / implemented:** Implemented schema validation, hash/reference checks and rejection of all ten prohibited fields; supplied a database-independent consumer.
- **Evidence:** export API; schema; scripts/consume_evidence.py
- **Blockers / remaining:** Version changes follow contract governance.
- **Decision required:** No implementation authorization pending; follow the documented governance policy.
- **Next / planned:** Continue verification and artifacts for requirement week 11; subsequent sections state the work actually delivered.

## Week 11 — Hardening & Integration Simulation

- **Done / implemented:** Verified negative fixtures, retries, concurrent import, 500-record load and legacy migration preservation; CI builds/runs the container against PostgreSQL.
- **Evidence:** test suite; GitHub Actions; container health/seed/freeze/replay/export smoke
- **Blockers / remaining:** Operational restore drills still need the deployment owner’s environment.
- **Decision required:** No implementation authorization pending; follow the documented governance policy.
- **Next / planned:** Continue verification and artifacts for requirement week 12; subsequent sections state the work actually delivered.

## Week 12 — Final Release & Handover

- **Done / implemented:** Delivered runnable backend/UI, environment examples, deployment/source onboarding/recovery instructions and release documentation.
- **Evidence:** README.md; docs/RUNBOOK.md; real-pilot outputs
- **Blockers / remaining:** Production exposure requires TLS and private access configuration.
- **Decision required:** Final sponsor handover acceptance remains a human decision.
- **Next / planned:** Broader curation and operational deployment acceptance from the roadmap.

