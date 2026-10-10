# MuniQuant Aluminium Platform

An evidence-first industrial evidence workspace built with **Python, C++17, and PostgreSQL**, with a responsive web interface.

Start with [Architecture & 12-week delivery plan](docs/ARCHITECTURE.md). Operational instructions are in [the runbook](docs/RUNBOOK.md).

## Scope and delivery status

Implements the upstream-only **12 week Project Plan V01 (2)**. The sponsor approved implementation on 2026-10-10. The version 1.0.0 evidence contract is implemented; the application is a 1.0.0 release candidate. No trading signals, forecasts, recommendations or downstream proprietary logic are present in the active service. Legacy market tables remain solely to preserve migration history.

The real-source pilot registers **15 facilities, five companies, three publisher families**, three capacity observations from preserved document versions, and four sourced ownership/operator relationships. Capacity coverage is only two facilities. Broad final coverage (50–100 facilities / 5–10 families), independent consumer acceptance and shared-production operations remain open. See [validation](docs/VALIDATION.md) and [backlog](docs/BACKLOG.md).

Reports: [Software Engineer 1](docs/reports/software-engineer-1.md), [Software Engineer 2](docs/reports/software-engineer-2.md), [Project Manager](docs/reports/project-manager.md). All cover twelve requirement weeks and distinguish implemented work, evidence and remaining acceptance work. They do not claim twelve elapsed weeks.

## Working features

- Controlled company/facility masters, countries, regions, commodities, relational aliases, audited supersession and sourced ownership/operator relationships.
- Append-only capacity/status/power/ownership facts with exact Decimal normalization, native dates and source locators.
- Audited source access; HTTPS acquisition with checked/pinned public IPs, approved hosts, redirects, retries, limits and attempt logs.
- Byte-exact HTML/PDF/CSV snapshots, SHA-256 content addressing and document version history.
- Versioned configurable HTML/PDF/CSV extraction, deterministic candidate identities, ambiguity review and individually attributable write credentials.
- INFO/WARN/ERROR/BLOCK quality findings, PASS/WARN/FAIL aggregation and blocked unsafe exports.
- Closed CommodityEvidencePackage v1 schema; frozen parser-input replay and verified logical output equivalence.
- Browser forms backed by actual APIs; migrations, PostgreSQL CI and a non-root Docker deployment.

Python owns acquisition, parsing, transactions and unit conversion. C++ only ranks name candidates using Unicode edit distance. Its measured microbenchmark was 58.75× faster than equivalent Python; this is not an end-to-end throughput claim.

## Start locally

Requires Python 3.11+ and a C++17 compiler (Apple Command Line Tools on macOS, g++ on Linux). Python 3.12 is used in CI and the container.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
pip install --no-build-isolation -e .
alembic upgrade head
python -m app.seed  # optional: fictional demonstration dataset
export WRITE_TOKEN="$(python -c 'import secrets; print(secrets.token_hex(24))')"
export WRITE_ACTOR="pilot-curator"
# Copy the token into the UI's Workspace access dialog to enable writes.
printf '%s\n' "$WRITE_TOKEN"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open [the workspace](http://127.0.0.1:8000) and [API documentation](http://127.0.0.1:8000/docs). Without `WRITE_TOKEN`, read access works but all mutations are disabled. The browser retains the token only until reload.

SQLite is the default local database at `data/muniquant.db`. PostgreSQL is the shared deployment target. Set `DATABASE_URL` before running migrations and the app to use it.

## Start with PostgreSQL and Docker

```sh
cp .env.example .env
# Replace both placeholder secrets with independent generated hexadecimal strings.
docker compose up --build -d
# Optional demo data:
docker compose exec app python -m app.seed
```

Open [the workspace](http://127.0.0.1:8000). The migration service runs before the app. PostgreSQL and snapshots have separate persistent volumes. Use `docker compose down` to stop without deleting data. Do not use `down -v` unless you intend to delete the database and evidence volumes.

## Verify and freeze

```sh
pytest -q
alembic check
python scripts/export_v1_schema.py
python -m app.evidence_cli export data/evidence-v1.json
python -m app.evidence_cli freeze data/evidence-v1.zip
python -m app.evidence_cli replay data/evidence-v1.zip
```

Output files must not already exist. Replay is offline and re-extracts parser-produced records from preserved bytes. Manually entered facts receive normalization verification only; the result explicitly reports their count. Frozen bundles are evidence artifacts, not operational database backups.

## Real-source demonstration

Use a separate database and snapshot directory so fictional fixtures cannot mix with public-source evidence:

```sh
DATABASE_URL=sqlite:///data/real-pilot.db alembic upgrade head
DATABASE_URL=sqlite:///data/real-pilot.db SNAPSHOT_DIR=data/real-pilot-snapshots \
  python -m app.pilot --online --as-of 2026-10-10 --output data/real-pilot-export
DATABASE_URL=sqlite:///data/real-pilot.db SNAPSHOT_DIR=data/real-pilot-snapshots \
  uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The online demonstration explicitly captures seven configured official publisher URLs. Live pages may change; use frozen replay to verify a previous capture. Undated facts use an observed-at date, not an inferred historical change date. Evidence links and limitations are described in [the runbook](docs/RUNBOOK.md).

## Project layout

```text
app/                 Python API, domain services, schemas, bundle tooling
app/static/          Browser interface (no separate Node build required)
cpp/                 C++17 Unicode edit-distance candidate-ranking kernel
migrations/          Versioned Alembic database schema
scripts/             Contract generation and native benchmark
tests/              Native, API, integrity and reproducibility tests
docs/               Architecture, decisions, backlog and operations
```

## First useful workflow

1. Browse a fictional facility and its historical observation.
2. Open its source document and download the exact snapshot.
3. Set Workspace access using your local write token.
4. Register a permitted source, capture its content, and add a sourced observation.
5. Try a facility alias under Resolution & review.
6. Export a package from Data quality and verify its source/document references.

Individual write identities are supported through WRITE_IDENTITIES_JSON. Reads are open by default on loopback. Enable REQUIRE_READ_AUTH and configure TLS/private ingress before shared deployment. No license for redistribution of third-party source data is implied by this repository.
