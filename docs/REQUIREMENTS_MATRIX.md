# Authoritative PDF traceability

Requirements: **12 week Project Plan V01 (2).pdf**, original pp.1–28, followed by repeated material. Week allocations are not elapsed time. Sponsor authorized implementation; no private downstream repository is needed. Implemented means runnable code/documentation, not invented meetings or human sign-off.

| PDF section/pages | Required detail | Implementation / evidence | Status |
|---|---|---|---|
| Objective / pp.1–2 | Reusable upstream industrial evidence; no downstream logic | Architecture; active API/UI boundary; prohibited-field tests | Implemented |
| D1 / pp.2–3 | Company/facility/types/owners/operators/geography/products/history/status | models/domain; normalized migrations; observations/relationships; historical QA | Implemented |
| D2 / p.3 | Publisher/type/URL/access/publication/retrieval/hash/media/storage/version | Source/SourceAccess/Document/DocumentVersion/Snapshot/relations | Implemented; unknown publication dates warn |
| D3 / pp.3–4 | Capture/hash/dedup/logs/errors/versions/snapshots | acquisition.py; governed HTTPS; atomic bytes; retry logs; failed parser manifests | Implemented |
| D4 / p.4 | Normalized/alias/deterministic/candidate/ambiguous/manual/audit | domain/services/pipeline; review UI and audit | Implemented |
| D5 / pp.4–5 | Provenance/units/values/duplicates/dates/unresolved/metadata/export validation | quality.py; DB constraints; coded findings; negative tests | Implemented |
| D6 / pp.5–6 | Stable self-contained evidence fields | contract.py; closed schema; CONTRACT.md; consumer example | Implemented |
| Role design / pp.6–7 | Separate ownership/reporting | Three twelve-week role reports | Delivered as implementation/status reports, no invented staffing history |
| W1 / pp.8–9 | Architecture/ERD/taxonomy/dictionary/backlog/risks; prior approval | docs; recorded sponsor approval | Implemented / Gate 1 approved |
| W2 / pp.9–10 | Eight master tables/aliases; migrations/Docker/service/CI/schema tests; 10–15 real set | normalized tables plus facility_alias view; 15 real facilities in pilot | Implemented |
| W3 / pp.10–11 | Source access/version/relations; retrieval/hash/storage/logging; official priority | three official publisher policies and real HTTPS captures | Implemented / Gate 2 demonstrated |
| W4 / pp.11–12 | Attributed/capacity/status layer, exact dimensional units/dates/history; QA changes/conflicts/shares | observation_detail plus capacity/status views; Decimal; hardening tests | Implemented; real historical breadth remains curation |
| W5 / pp.12–13 | Aliases/external IDs/merge-supersession; all matching stages; difficult benchmark | audited supersession, no auto fuzzy trust; 50-case fixture; real capacities | Implemented / Gate 3 demonstrated |
| W6 / pp.13–14 | Reconstructable decision metadata; interface; SLA/categories/rules/escalation | review endpoints/UI; individual actor tests; REVIEW_POLICY.md | Implemented; operating SLA measurements not invented |
| W7 / pp.14–15 | 2–3 reusable source adapters and onboarding | HTML/PDF/CSV config recipes; RUNBOOK.md | Implemented; no OCR/complex arbitrary table inference |
| W8 / pp.15–16 | DB clear invariants; missing unit/date/provenance/ambiguity/jumps; severities/remediation | constraints and machine-readable quality; bad-fixture tests | Implemented / Gate 4 demonstrated |
| W9 / pp.16–17 | Runs/version/snapshots/hashes/manifests; frozen-input rebuild equivalence | evidence_cli and recipes; real offline parser replay | Implemented; no MEI PIT replay claimed |
| W10 / pp.17–18 | JSON/API export, schema, mappings, docs/versioning; all ten forbidden fields | closed 1.0.0 contract; independent consumer simulation | Implemented / technical Gate 5; human sign-off distinct |
| W11 / pp.18–19 | Indexes/migration/integrity/load/conflicts; CI/integration/retry/logs/Docker/package; UAT chain | 500-fixture load, concurrent import, populated migration/unsafe-input preflight, transport, container smoke | Implemented technical UAT |
| W12 / pp.20–21 | Migrations/docs/setup/deploy/CI/runbook/tests/onboarding/reports/releases/risks/roadmap; 12 demo steps | UAT.md; real-pilot artifacts; release notes; docs/reports | Delivered technical handover; Gate 6 human acceptance not fabricated |
| Dataset / pp.21–22 | Recommended 50–100 meaningful facilities; representative complexity | 15 real identities, sourced multi-owner/operator case; synthetic history/conflict/closure/load cases clearly labelled | Recommended breadth remains open |
| Sources / p.22 | Suggested 5–10 understood families; repeatable onboarding, no exhaustive crawler | three official families and three adapters | Suggested breadth remains open |
| Cadence / pp.22–23 | Planning/development/demo and weekly visible artifacts; Done/Evidence/Blockers/Decision/Next | UAT.md operating cadence; three role reports and PM consolidation | Documented; meetings and 360 hours not invented |
| Gates / pp.23–24 | Approval then real retrieval, resolution, bad fixtures, contract freeze, final acceptance | architecture, real pilot, tests, closed contract and handover artifacts | Technical evidence delivered; human acceptance remains human |
| Stop conditions / pp.24–25 | Preserve provenance/hash/identity/linkage/validation/tests/contract/reproducibility | RISKS.md; recommended breadth explicitly deferred | Enforced |
| Exclusions/access / pp.25–26 | No predictive/trading/analogue/private model dependencies | active route/schema tests; public-source-only implementation | Enforced |
| Evaluation / pp.26–27 | Technical competency rubric and strategic payoff | RISKS.md rubric; code/test/docs artifacts | Documented; no fabricated human scores |
| Success / pp.27–28 | Another engineer deploys/onboards/resolves/facts/validates/exports/traces/reproduces without private code | README/RUNBOOK/CONTRACT/UAT and independent consumer | Technical demonstration delivered |
