# BACKLOG_v0.1 — governed delivery

Gate 1 approval is pending; week numbers are requirements allocations, not elapsed work or completed gates. Baseline code predates this authoritative scope reconciliation.

| Priority | Week | Deliverable / acceptance | Owner |
|---|---|---|---|
| P0 | 1 | Approve architecture, ERD, source model, boundary | Sponsor / PM |
| P0 | 2 | Controlled master/reference schema, additive migrations; fresh PostgreSQL deploy | SE1 |
| P0 | 2 | Docker/API/CI schema tests; 10–15 sourced real facilities | SE2 / PM |
| P0 | 3 | Source access/document/version relations; one real retrieved and hash-verified snapshot | SE1 / SE2 / PM |
| P0 | 4 | Historical capacity/status, Decimal dimensional units; conflicts/vintages preserved | SE1 / SE2 |
| P0 | 5 | Company/facility alias/supersession, ambiguity benchmark of 50 names; real sourced resolution | SE1 / SE2 / PM |
| P0 | 6 | Immutable authenticated review decisions, review SLA/escalation; reconstruct every decision | SE1 / SE2 / PM |
| P1 | 7 | HTML/PDF/CSV adapters, parser locators, config-driven onboarding | SE2 |
| P0 | 8 | DB invariants, machine-readable quality/severity; predictable corrupt-fixture failures | SE1 / SE2 / PM |
| P0 | 9 | Run manifests, frozen-input parser rerun and equivalent logical evidence output | SE1 / SE2 |
| P0 | 10 | Closed v1 package, schema/consumer validation and version freeze | SE1 / SE2 / PM |
| P0 | 11 | PostgreSQL migration integrity, import concurrency, retries, recovery, end-to-end UAT | All |
| P0 | 12 | Release/runbook/handover; real-source full demonstration; final sponsor acceptance | All |

Protect provenance, hashing, identity, source linkage, validation, tests, contract and reproducibility. If capacity is insufficient remove nice dashboards first, extra adapters second, dataset breadth third, advanced matching fourth.

## Risks and required decisions

Access/licensing and live source reliability: PM records explicit policy. Incorrect identity merge: never auto-accept ambiguity. Legacy string dates/float capacity: SE1 audits migration/backfill. Snapshot/DB divergence: SE2 verifies hashes and coordinated recovery. C++ cost without measured benefit: benchmark distance; move trivial conversion to Python. Shared write actor: local pilot only until individual identities. Scope drift: active market/trading removed; no downstream proprietary logic. Target final coverage 50–100 meaningful facilities and 5–10 source families; neither has been achieved.
