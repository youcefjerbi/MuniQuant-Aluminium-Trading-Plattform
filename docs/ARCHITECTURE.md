# ARCHITECTURE_v0.1 — Gate 1 review

Date: 2026-10-10. Status: proposed; sponsor approval pending.
Authoritative requirements: 12 week Project Plan V01 (2).pdf, pp. 1–27 (later pages repeat).
This document supersedes the repository's earlier market-data and paper-trading scope extensions for this delivery.

## Boundary and decisions

Public/permitted source → registry → acquisition → exact raw snapshot → industrial asset master → entity resolution → attributed observations → quality → candidate export.
Responsibility ends at CommodityEvidencePackage. No private downstream access, market predictions, sentiment, event scoring, impact/supply pressure models, analogue selection, recommendations, trading, or portfolio optimization.

Retain a modular Python FastAPI service with SQLAlchemy, Alembic, PostgreSQL and a minimal same-origin curator UI. Docker Compose deploys database, migration job and API; GitHub Actions tests SQLite and PostgreSQL, schema generation and container build. SQLite is a test/local convenience only.

Python owns HTTP, adapters, parsing, transactions, Decimal unit conversion, quality and exports. C++ is justified only for bounded O(m*n) edit-distance candidate ranking over many normalized names; it must never trust a fuzzy candidate automatically. Trivial unit multiplication now uses Python Decimal arithmetic (legacy storage still float). Benchmark name distance against Python before retaining the build burden for production; no speedup is claimed now.

## Existing implementation and compatibility

Baseline commit: 0ed0c17. Existing entities/observations/sources/documents/relationships/reviews/runs/audit provide a working pilot. Dates are string columns, aliases JSON, document/version in one table. These are not the full week-2/3 normalized domain model. This branch removes market endpoints, workspace market data, charts/order application and navigation. The draft export retains an empty market_observations array for draft compatibility, never historical market rows. Old tables and migration history remain to avoid destructive data loss; archive/removal is a later reviewed migration.

## Proposed schema and migration strategy

See ERD_v0.1 and DATA_DICTIONARY_v0.1. Incremental migrations must preserve existing IDs, exact source bytes, document links, observations and review decisions. Backfill native dates only after invalid legacy dates are identified; reject unsafe migrations. Split aliases/reference data into relational tables. Company/facility specializations retain stable external entity identity. Document versions and source access records are separate histories. Constraints include nonnegative values, known dimensional units, valid intervals and foreign keys; PostgreSQL migration round trips must run against PostgreSQL, not only SQLite.

## Acquisition and evidence

Register an approved source-access decision before retrieval. Explicit URL configuration only: no general crawler. Bounded HTTP retrieval requires public-address checks, approved host policy, redirect revalidation, timeouts, byte limits, retries with logged attempts, and rate limits. Preserve original PDF/HTML/CSV bytes under SHA-256 content-addressed storage using atomic writes. Documents record publisher/source URL, publication and retrieval timestamps, media type, storage reference and version. Hash equality deduplicates content without conflating provenance. HTML/PDF adapters extract candidates with section/page locators and parser versions; CSV imports use unique transactional import identities.

## Identity, review, quality, reproducibility

Exact/normalized/alias matches resolve only when unique. Candidate or ambiguous matches enter a queue. Decisions carry candidate IDs, selected entity, authenticated reviewer, reason and time; merges/supersessions retain history. No fuzzy auto-acceptance. Company resolution is still missing in the baseline.

Machine-readable findings include code, severity INFO/WARN/ERROR/BLOCK, affected record, and remediation. Aggregate PASS/WARN/FAIL is derived; BLOCK prevents export. Validate provenance, dimensions, finite values, dates, unresolved entities, duplicates and suspicious history changes. Observations append; conflicting facts remain distinct.

Frozen evidence builds must rerun versioned parsers against preserved inputs and reproduce logical records. Current bundle restoration only reconstructs stored output; it does not satisfy this gate. Stable logical identifiers and canonical ordering must exclude volatile run/retrieval timing from equivalence checks while retaining timestamps in provenance.

## Export and deployment

Keep package 0.1.0-draft until week-10 Gate 5 consumer approval. v1 records must expose external_entity_id, entity_type, canonical_name, aliases, facility_type, country/region, attribute_type, reported_value/normalized_value/unit, valid_from/to, published_at/retrieved_at, source_id/document_id/content_hash, resolution_status/quality_status and pipeline/package versions. Closed schemas reject extra fields, including every prohibited field listed on plan p.18. No breaking v1 changes without version increment.

The single configured write actor/token is local-pilot authentication, not multi-user accountability. Before shared deployment add authenticated identities, read/write roles, TLS, secret rotation, backup/restore and observability. Baseline run instructions remain in RUNBOOK.md. Final production release is not claimed.

## Review gates

1. Week 1: sponsor approves this architecture, ERD, source model and boundary; pending. No large implementation before approval.
2. Week 3: a real permitted source is retrieved, hashed, snapshotted and registered; not passed (paste-only baseline).
3. Week 5: a real raw facility name resolves to sourced capacity; not passed (synthetic tests only).
4. Week 8: corrupted fixtures give predictable machine-readable findings; partial (HTTP rejection tests, incomplete quality engine).
5. Week 10: consumer understands and approves frozen v1 contract; pending.
6. Week 12: final end-to-end demonstration and handover accepted; pending.

Approval requested: upstream-only boundary, incremental normalized PostgreSQL schema, Python orchestration/Decimal conversion, bounded native candidate-ranking component subject to benchmark, governed adapters and closed export contract. Approval authorizes implementing weeks 2–12; it does not mark subsequent acceptance gates passed.
