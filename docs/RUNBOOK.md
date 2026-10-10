# Deployment, source onboarding and recovery

## Setup

README.md contains complete local and Docker instructions. Install pinned dependencies, build the C++ extension and run `alembic upgrade head` before starting the API. PostgreSQL is the deployment target; SQLite supports local demonstrations. Migration startup is explicit, never hidden in the API. Use a C++17 compiler for source builds; runtime containers need no compiler.

| Variable | Purpose |
|---|---|
| DATABASE_URL | SQLAlchemy URL; default local SQLite, deployed postgresql+psycopg |
| SNAPSHOT_DIR | Persistent content-addressed snapshot directory |
| WRITE_TOKEN / WRITE_ACTOR | Single curator credential and recorded actor; absent token disables writes |
| WRITE_IDENTITIES_JSON | JSON map of separate bearer credentials to reviewer identities; credentials must be unique and nonempty |
| REQUIRE_READ_AUTH | `true` protects API reads except health; default `false` for loopback pilot |
| READ_TOKEN | Optional read-only bearer credential; cannot authorize writes |
| POSTGRES_PASSWORD | Compose database secret; use independent URL-safe generated hexadecimal string |

Use environment/ignored .env for secrets. Compose loads .env; ordinary Python does not. The UI retains the credential only in memory until reload. If protected reads are enabled, enter a read/write credential in Workspace access to load data. UI snapshot/schema downloads send the in-memory bearer credential, including for read-only access. Direct API requests require the bearer header when protected reads are enabled. TLS/private ingress, rotation and identity-provider integration are deployment-owner controls. Compose exposes only loopback port 8000, not the database.

## Source onboarding

1. Register publisher, source category, canonical URL and access/licensing notes. Prioritize official companies, then government/regulators/public bodies.
2. Record an audited access decision with exact lowercase permitted hostnames, reviewed basis and retention/redistribution limitations. Only permitted policies can retrieve URLs. Later restriction revokes capture/export.
3. Retrieve an explicit HTTPS URL from Sources & evidence or POST /api/acquire. Public-address pinning/TLS checks, redirect revalidation, 20-second timeouts, four redirects, three attempts and 10 MB limits apply. No general crawler or login bypass.
4. Inspect metadata and download byte-exact evidence. Identical bytes at the same provenance retain the document ID; changed bytes create a new version. HTML/PDF/CSV bytes are preserved unchanged.
5. Create controlled companies/facilities; record identity evidence with document ID and locator. Curate aliases and owner/operator relationships with dates and source locators. Unknown effective dates must be labelled capture/observation dates, not inferred historical dates.
6. Configure an existing adapter: HTML/PDF use literal words before/after a number, reported unit, raw facility name/country and dates; PDF may restrict a page. CSV uses the headers below. Text PDFs only, maximum 200 pages; scanned documents require manual sourced facts or a future OCR adapter.
7. Review ambiguous/unresolved candidates using REVIEW_POLICY.md. Register a missing facility then Add verified candidate; final acceptance persists the sourced observation and alias. Rejection remains auditable.
8. Inspect machine-readable quality. Fix BLOCK/ERROR; document WARN consideration. Export v1 and trace a record to exact document/hash/locator.

```csv
facility_name,country,reported_value,reported_unit,valid_from,valid_to,attribute,evidence_reference
Synthetic Example,NO,420,kt/year,2025-01-01,,capacity,table 1
Synthetic Example,NO,closed,status,2024-01-01,2024-12-31,status,section 2
```

The rows above are fictional. Capacity units: t/year, kt/year, Mt/year; power: MW; ownership: percentage; operational status: operating/closed/suspended/planned/construction with status unit. Required CSV fields are name, country, reported value/unit, start date and evidence locator. Optional attribute defaults to capacity and optional end date to null. Maximum 1,000 rows/build. Invalid numeric/date/status rows leave no partial facts; failure logs remain. Valid unresolved rows enter review rather than becoming trusted. Duplicate builds are idempotent. Concurrent duplicates either reuse the build or return 409; refresh/retry after a conflict.

## Logs, health and pagination

GET /api/health checks database and native module. JSON request logs include method/path/status/duration without token/content. Runs and retrieval attempts expose successful, duplicate and failed captures; parser failures persist failed manifests without partial facts. GET /api/quality returns findings and coverage. The UI initially shows at most 1,000 rows/type; GET /api/records/{type}?offset=0&limit=100 paginates all supported register, fact, review, manifest and access records. `alembic check` checks schema drift; constraints also have direct SQL tests.

## Freeze and independently verify

```sh
python -m app.evidence_cli export data/evidence-v1.json
python -m app.evidence_cli freeze data/evidence-v1.zip
python -m app.evidence_cli replay data/evidence-v1.zip
python scripts/consume_evidence.py data/evidence-v1.json
```

Output paths must not already exist. Freeze contains the closed package, recipes, identities, review decisions and snapshots; replay is offline, checks hashes and reruns versioned parsers. It reports manual facts separately as normalization-only verification. Source licensing still applies. These are evidence artifacts, not full operational backups. Legacy app.bundle stored-output tooling belongs to the earlier draft format; use evidence_cli for v1.

## Coordinated operational backup / restore

Stop application writes before capturing the database and snapshots. In Compose, stop `app` while leaving `db` running. Create a PostgreSQL custom-format dump and archive the evidence volume, preserving owner/permissions. For example, redirect `docker compose exec -T db pg_dump -U muniquant -d muniquant -Fc` into a new backup file. A stopped app prevents new observations pointing at snapshots outside the matching archive. Store dump and archive together with migration revision, SHA-256 checksums and date; treat them as private operational data.

Restore into a separate fresh PostgreSQL deployment and separate evidence volume, never over the working database. Use pg_restore to that empty database, restore the matching evidence archive with appuser ownership, verify the migration revision, then run `alembic upgrade head`, `alembic check`, a hash-validating v1 export and frozen replay before enabling writes. A missing/corrupt snapshot must block export. Keep the original deployment until verification succeeds. For SQLite, use Python sqlite3 backup against the quiescent database and archive its matching snapshots. Rehearse this procedure in the actual deployment environment before shared production acceptance.

## Real demonstration and limits

Use app.pilot with the separate database/storage settings in README.md. It captures Alcoa, Hydro and Rio Tinto publications, verifies 15 identities and extracts Portland/Husnes capacities. The Portland PDF page 2 has a mismatched Huntly header; page 1 alone supports extracted values/ownership. Company jurisdiction metadata needs additional source evidence. PDF/HTML publication dates may be unknown and warn. Three parsed records reflect two facility capacities and one document revision; ten document versions are preserved. Recommended broader dataset/source-family coverage remains work for curation, not a fabricated release claim.
