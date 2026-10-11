# MuniQuant Aluminium Platform

An evidence-first industrial evidence workspace built with **Python, C++17, and PostgreSQL**, with a responsive web interface.

Start with [Architecture & 12-week delivery plan](docs/ARCHITECTURE.md). Operational instructions are in [the runbook](docs/RUNBOOK.md).

## Experimental event-chain and paper-engine branch

This branch adds the sponsor-requested downstream **research and simulated trading extension** beyond the original PDF's upstream-only scope. The evidence module and its export contract remain separate. The original twelve-week reports describe the upstream baseline, not acceptance of a live trading system.

Open **Patterns & paper trades** to register events, inspect relationship chains and historical analogues, configure a paper account, and inspect automatic BUY/SELL/HOLD decisions. Automation starts paused. There is no broker integration or real-money execution. See [the extension guide](docs/EVENT_CHAIN_PAPER_ENGINE.md) for the complete fictional demo, API ingestion, policy and limitations.

## Scope and delivery status

Implements the upstream-only **12 week Project Plan V01 (2)**. The sponsor approved implementation on 2026-10-10. The version 1.0.0 evidence contract is implemented; the application is a 1.0.0 release candidate. The upstream evidence module and exported evidence packages contain no trading signals, forecasts, recommendations or downstream proprietary logic. The experimental paper engine is an explicitly separate extension on this branch. Legacy market tables remain solely to preserve migration history.

The real-source pilot registers **15 facilities, five companies, three publisher families**, three capacity observations from preserved document versions, and four sourced ownership/operator relationships. Capacity coverage is only two facilities. Broad final coverage (50–100 facilities / 5–10 families), independent consumer acceptance and shared-production operations remain open. See [validation](docs/VALIDATION.md) and [backlog](docs/BACKLOG.md).

Reports: [Software Engineer 1](docs/reports/software-engineer-1.md), [Software Engineer 2](docs/reports/software-engineer-2.md), [Project Manager](docs/reports/project-manager.md). All cover twelve requirement weeks and distinguish implemented work, evidence and remaining acceptance work. They do not claim twelve elapsed weeks.

The complete replacement includes a [ready-to-restore fictional database and evidence snapshots](fixtures/demo/README.md), plus a [seven-minute narrated walkthrough](docs/demo/walkthrough.mp4), [captions](docs/demo/walkthrough.srt) and [exact practice instructions](docs/demo/walkthrough.md). The video uses a natural AI narrator and animated cursor over actual platform screens. PostgreSQL schema and migrations are included; deployment credentials are configured locally.

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

## Licensed event leads (Permutable AI)

Permutable AI events and headlines for aluminium (`ALI_COM`, COMEX) arrive on the **Event leads** screen as curator leads: each points to a possible curtailment, restart, outage or ownership change and shows which registered assets it mentions. Leads are not evidence. Confirm each one by capturing the primary source and recording the observation from it. Only factual feeds are captured; vendor sentiment, impact, signals and forecasts are not stored. Set `PERMUTABLE_API_KEY`, then run `python -m app.permutable setup` and schedule `python -m app.permutable poll`. See [ADR 0003](docs/adr/0003-permutable-lead-source.md) and [the runbook](docs/RUNBOOK.md).

## Starting guide: run locally with Python

Requires Python 3.11+ and a C++17 compiler (Apple Command Line Tools on macOS, g++ on Linux). Python 3.12 is used in CI and the container.

On macOS, install the compiler if needed with `xcode-select --install`, and complete the installation before continuing.

Open a terminal in the cloned `MuniQuant-Aluminium-Trading-Plattform` folder (the folder containing this README and `requirements.lock`). Run the following commands in the same terminal:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
pip install --no-build-isolation -e .
alembic upgrade head
python -m app.seed
export WRITE_TOKEN="$(python -c 'import secrets; print(secrets.token_hex(24))')"
printf '%s\n' "$WRITE_TOKEN"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Keep the terminal open while using the application. Once the server has started, open [the workspace](http://127.0.0.1:8000) in your browser. Open **Workspace access** and paste the token printed immediately before the server started to enable editing. The browser retains the token only until reload. API documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

The seed command adds fictional demonstration data; omit it if you want an empty workspace. This address runs on your computer; cloning the repository does not create a public hosted website.

To stop the server, press **Ctrl+C**. To start it again, activate the environment with `source .venv/bin/activate`, generate and print a new `WRITE_TOKEN` using the commands above, and run the `uvicorn` command again. Your database and evidence files remain saved. Without `WRITE_TOKEN`, read access works but all mutations are disabled.

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
