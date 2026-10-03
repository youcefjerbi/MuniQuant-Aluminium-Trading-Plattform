# Operations and source onboarding

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| DATABASE_URL | sqlite:///./data/muniquant.db | SQLAlchemy connection URL; PostgreSQL uses postgresql+psycopg |
| SNAPSHOT_DIR | data/snapshots | Persistent evidence directory |
| WRITE_TOKEN | empty | Required bearer token for all writes; empty means read-only |
| WRITE_ACTOR | local-curator | Server-controlled identity recorded for the pilot curator |
| POSTGRES_PASSWORD | required in Compose | Database password; use URL-safe hexadecimal characters |

Secrets belong in the environment or an ignored `.env` file. Python does not automatically read `.env`; Docker Compose does. Use TLS and organizational identity before exposing the API beyond localhost. The current workspace endpoint includes all records and audit metadata; it has no read authorization or pagination.

## Health, logs and migrations

`GET /api/health` checks database connectivity and reports the compiled native module version. Database schema is created only by `alembic upgrade head`; starting the API does not silently create tables. Run migrations once before starting service replicas. `alembic check` detects model/schema drift.

Application request logs are JSON records with method, path, status and duration. Do not log tokens or uploaded content. Investigate failed acquisitions in the run manifest view. A 409 during concurrent document capture means a version/identity constraint conflict; reload and retry.

## Source onboarding

1. Record publisher, canonical URL, source category, access decision and notes.
2. Confirm the right to acquire, retain and redistribute the material. Set permitted only after review; restricted and review-required sources cannot be captured.
3. Capture the exact text/CSV/HTML/JSON content and original URL. Include the publication date when known. Current capture stores UTF-8 text; it does not claim to preserve original PDF binary bytes.
4. Download the snapshot to verify it. Repeated identical content retains its document ID; changed content at the same source URL creates a new version.
5. Register facility identity and aliases. Add the observation with the page/table/row/section locator.
6. Inspect quality and export. Preserve original values even when normalized.

Record only an environment-variable/key-vault reference in `credential_ref`; never
store an API key or password in the database. Retrieval attempts record outcome,
requested URL, timestamp and error information independently from successful
document snapshots.

## Quality, trace and export

Run the current ruleset from **Data quality** or call `POST /api/quality/runs` with
the curator bearer token. The run records its ruleset version and findings for
missing publication dates/locators, missing normalization, conflicting sourced
values and ownership totals above 100%. `GET /api/quality/latest` returns the most
recent run.

Use `GET /api/observations/{id}/trace` to follow an observation through entity,
document, source and acquisition run; the response re-verifies the stored snapshot
hash. `GET /api/export/cep-v1.jsonl` emits one active industrial observation per
line. The original `/api/export` draft contract remains available for compatibility.

## CSV ingestion

Capture a document with content type `text/csv`, then choose Import CSV. Required header:

```csv
facility_name,country,reported_value,reported_unit,valid_from,evidence_reference
Nordhaven Smelter,NO,420,kt/year,2025-01-01,row 2
```

This example is synthetic. Facilities must already exist and resolve uniquely. All rows succeed together or none are persisted. Limit: 1000 rows, subject to the request-size limit. Supported capacity units: t/year, kt/year, Mt/year. A second sequential import of the same document is a no-op. Do not submit simultaneous imports of the same document until concurrency hardening is delivered.

If a name is ambiguous, review the candidates. Current review decisions are recorded but do not automatically create an alias or rewrite CSV rows. Correct the source mapping explicitly before retrying.

## Evidence bundles and recovery

```sh
python -m app.bundle freeze data/frozen.zip
python -m app.bundle verify data/frozen.zip
```

The bundle contains a schema-validated JSON package and hash-addressed snapshots. Verification checks package and snapshot hashes. Restore into an **empty** migrated database, with a separate snapshot directory:

```sh
export DATABASE_URL=sqlite:///./data/restored.db
export SNAPSHOT_DIR=./data/restored-snapshots
alembic upgrade head
python -m app.bundle restore data/frozen.zip
```

Restore refuses a populated data-product database and checks that the reconstructed export equals the original. Bundle restore excludes reviews, acquisition runs and audit records. For full operational recovery, back up the entire database and snapshot volume together while writes are stopped. For PostgreSQL, use `pg_dump`/`pg_restore` and archive the evidence volume, then run a hash-verifying export after recovery. Test recovery before a production release.

## Known pilot limits

- Single shared curator token, no individual users, no read authorization.
- Local/pasted text acquisition and CSV parser; remote sources and binary PDF adapters remain planned.
- No licensed market feed, no automatic active/front-month contract selection.
- Supersession links are represented, but no entity merge/correction workflow or review-to-alias automation exists yet.
- Cross-source conflicts and ownership totals are detected, but adjudication remains a curator workflow.
- Workspace reads return the complete pilot dataset; pagination is required for larger deployments.
- ISO date/time strings and floating-point normalized capacities are initial implementation trade-offs.
- Frozen bundles reproduce stored data products, not arbitrary parser re-extraction or the operational audit database.
