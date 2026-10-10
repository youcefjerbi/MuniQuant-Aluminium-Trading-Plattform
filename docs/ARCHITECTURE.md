# Architecture — approved implementation

Status: sponsor authorized implementation on 2026-10-10 through the chat approval “i apporve on everythin that you do”. Requirements: 12 week Project Plan V01 (2).pdf, primary pages 1–28 (page 28 ends the original success criterion). Application release candidate 1.0.0rc1; evidence contract 1.0.0.

## Boundary

Permitted official source → audited access → bounded HTTPS capture → immutable byte snapshot → document version → versioned extraction → identity resolution → manual review when needed → dated industrial facts → quality → CommodityEvidencePackage v1. The responsibility ends at this package. Trading, predictions, recommendations, event impact and all prohibited downstream fields are excluded by a closed schema and recursive validation.

## Components

FastAPI and a same-origin static curator UI use SQLAlchemy and additive Alembic migrations. PostgreSQL is the deployment database; SQLite supports local use/tests. Normalized reference and specialization tables coexist with legacy entity IDs. Native date and exact Decimal specialization records are authoritative; legacy float fields are compatibility representations. Company-facility shares are exact and dated. Document versions link immutable snapshots; reviewed aliases and supersessions retain audit metadata.

Python handles network, parsing, normalization, transactions, quality and export. The C++17 pybind11 component performs bounded Unicode edit distance only. A seeded 1,000-pair microbenchmark verified equivalent outputs and measured 58.75× speedup on this workstation. Unique exact/normalized/alias matches alone resolve automatically. Similarity is a review suggestion.

Retrieval requires an audited approved host list, HTTPS/public addresses, pinned checked IPs with TLS hostname verification, redirect revalidation, bounded bytes and retries with attempt logs. No general crawler. Raw bytes are content-addressed and written atomically. Literal extraction recipes avoid user-supplied regular expressions. PDF extraction is text-based and bounded, with no OCR. Source rights must be reviewed before redistribution.

## Integrity and reproducibility

Relational foreign keys and range/date constraints complement application dimension checks. Quality findings carry code, severity, affected record and remediation. BLOCK/ERROR prohibit v1 export. Stable build/candidate identifiers and parser specifications permit offline re-extraction. SHA-256 verifies snapshots, recipes and packages. Manual facts are explicitly reported as normalization-only verification.

The closed v1 schema rejects unknown fields. Exact numeric values are decimal strings so consumers cannot silently lose precision. Sources, documents, entities, identity evidence and relationships have validated references. Breaking changes require a contract version increase. Legacy draft exports and stored-output bundle tooling are compatibility paths; use evidence_cli for v1 freezing and replay.

## Deployment and acceptance

Docker uses a non-root application, migration job, private PostgreSQL and loopback app port. Write credentials may map separately to reviewer identities. Optional authenticated reads and a separate read-only token are implemented. Enable REQUIRE_READ_AUTH and configure TLS/private ingress and credential lifecycle before shared use. PostgreSQL plus snapshot storage need coordinated backups.

Gate 1 approval is recorded. Gates 2–4 and the technical portion of Gate 5 have demonstrable retrieval, resolution, negative-fixture and frozen-contract evidence. Independent consumer sign-off and Gate 6 sponsor handover acceptance are not inferred from implementation approval. The real pilot has 15 identities / three publisher families, with capacity evidence for two facilities. Broader curated coverage, performance/concurrency acceptance and production operations remain explicit backlog items.
