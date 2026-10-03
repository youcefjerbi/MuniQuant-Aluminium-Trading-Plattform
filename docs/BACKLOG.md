# Delivery backlog

The architecture document contains the twelve-week owner-based plan. This list distinguishes implemented foundations from remaining production work.

## Implemented in v0.1

- [x] Python API and responsive web workspace.
- [x] Compiled C++ capacity normalization and Unicode name distance.
- [x] Company/facility records, aliases and sourced dated relationships.
- [x] Source access metadata, SHA-256 snapshots, document versions and retrieval manifests.
- [x] Structured source-access references and per-attempt SUCCESS/UNCHANGED/FAILED acquisition records.
- [x] Historical capacity/status observations and distinct market observations.
- [x] Normalized/alias/fuzzy resolution evidence, uncertain candidate queue, one-time reviewed decisions.
- [x] Versioned cross-record quality checks, observation trace API and CEP v1 JSONL export.
- [x] Atomic CSV ingestion with sequential duplicate-import detection.
- [x] Schema-validated draft exports and verified frozen-bundle reconstruction.
- [x] Migrations, native/API tests, CI and container configuration.

## Next milestone: real permitted evidence

| Priority | Task | Acceptance |
|---|---|---|
| P0 | Curate source access and license register | Two industrial source families and one market provider have explicit acquisition/retention decisions |
| P0 | Controlled remote downloader | Allowlisted hosts, bounded size, redirects checked, timeouts/retries, exact bytes retained, failure manifests |
| P0 | Binary PDF adapter | Preserve original binary file, page-level extraction locator and parser version; golden test fixture |
| P0 | Curated pilot data | 10–15 real facilities with traceable observations; synthetic fixtures remain separate |
| P0 | Individual user access | Authenticated reviewer identities and role-based write/read access; token pilot retired for shared deployment |
| P1 | Resolution review application | Accepted matches can create audited aliases; supersession/merge policy preserves identity history |
| P1 | Concurrent import idempotency | Unique transactional import identity prevents double insertion under parallel requests |
| P1 | Market source adapter | Concrete contract IDs, timezone policy, original currency, source publication times and licensing respected |
| P1 | Strong reference data | Country/product/type tables and schema constraints; the in-code unit dimension catalog is implemented but should become governed reference data when curator editing is required |
| P1 | Operational hardening | Pagination, indexing, overlap/conflict checks, recovery drill, secret rotation and deployment tests |
| P2 | Contract v1 | Consumer review, compatibility fixtures and version policy agreed before freeze |
| P2 | Broader pilot | 50–100 verified facilities, 5–10 source families, ownership and operating-status history |

Simulated stock/options orders and charting are now implemented as a user-requested scope extension; see PAPER_TRADING.md. Live trading, price forecasting, and broker execution remain excluded.
