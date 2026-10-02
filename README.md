# MuniQuant Aluminium Platform

An evidence-first industrial and market-data workspace built with **Python, C++17, and PostgreSQL**, with a responsive web interface.

Start with [Architecture & 12-week delivery plan](docs/ARCHITECTURE.md). Operational instructions are in [the runbook](docs/RUNBOOK.md).

## Charts and paper trading

Open **Charts & trading** for candlestick/line charts, volume, simulated stock orders, calls and puts, limits, positions and P/L. Start with $100,000 of paper cash and advance the synthetic replay one session at a time. See [paper-trading rules](docs/PAPER_TRADING.md). Prices are fictional and there is no real-money execution.

## Working features

- Industrial asset and company register, aliases, sourced ownership/operator relationships.
- Historical capacity and operating-status observations, explicit units and C++ normalization.
- Distinct market instruments, futures contracts, prompt dates, price types, source currencies and provenance.
- Source registry, exact UTF-8 evidence snapshots, SHA-256 integrity checks and document versions.
- Atomic capacity CSV import; deterministic matching and an audited human-review queue.
- Machine-readable validation, quality warnings, acquisition manifests.
- Schema-validated JSON export and frozen evidence bundles with verified restore.
- Browser screens for overview, assets, markets, evidence, resolution, and quality.
- Alembic migrations, automated tests, PostgreSQL CI and Docker configuration.

**Status: v0.1 working pilot.** Included fixtures are explicitly fictional. This is not a live-price feed, a trading execution system, or the completed twelve-week production release. Remote acquisition, PDF parsing, licensed feeds, individual user authentication, and broader data curation are tracked in [the backlog](docs/BACKLOG.md).

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

## Verify

```sh
pytest -q
alembic check
python -m app.bundle freeze data/pilot-bundle.zip
python -m app.bundle verify data/pilot-bundle.zip
```

A freeze output must not already exist. See the runbook for restoring into a fresh migrated database. Frozen bundles restore the data product and evidence, not review/audit history or a full operational database backup.

## Project layout

```text
app/                 Python API, domain services, schemas, bundle tooling
app/static/          Browser interface (no separate Node build required)
cpp/                 C++17 normalization and Unicode edit-distance kernels
migrations/          Versioned Alembic database schema
scripts/             Draft export-schema generation
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

Keep the service local until individual authentication and read authorization are implemented. No license for redistribution of third-party source data is implied by this repository.
