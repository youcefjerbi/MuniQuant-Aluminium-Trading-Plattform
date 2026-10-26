# MuniQuant Workspace

Where we experiment: **Permutable news leads, research and practice trading, investigations and the map**, with a
responsive web interface. Built with Python and PostgreSQL (SQLite for local use).

Facts about aluminium plants live in the separate **[Data Core](https://github.com/alekspetrov9e/muniquant-data-core)**:
companies and plants, sources and the exact saved copies of their pages, dated facts, matching and human review,
quality checks and the one export, CommodityEvidencePackage 1.0.0. The Workspace talks to the Core only through
the Core's API ([app/core_client.py](app/core_client.py)): it stores Core IDs, never copies, and sends candidate facts
that the Core checks with its own rules before accepting them. The two used to share one codebase and database;
[the split note](docs/SPLIT.md) explains what moved where (DC1 step B).

Start with [the architecture and data diagram](docs/ARCHITECTURE.md). Operations are in [the runbook](docs/RUNBOOK.md);
how the Workspace uses the Core is in [the contract note](docs/CONTRACT.md).

## Working features

- **Event leads** (Permutable AI, licensed, lead-only): events and headlines for aluminium point curators to possible
  curtailments, restarts, outages or ownership changes and show which Core plants they mention. Leads are not
  evidence: confirm each one with a primary source in the Core, propose the fact to the Core, then confirm the lead
  with the Core document and fact. Vendor responses, their saved copies and the leads stay in the Workspace and never
  reach the Core. See [ADR 0003](docs/adr/0003-permutable-lead-source.md).
- **Search events by text similarity**: on Event leads, a query such as `smelter power outage` ranks events by shared
  words over title, summary, topic, matched Core plant names and headlines. PostgreSQL uses an indexed full-text
  projection; SQLite uses offline TF-IDF. See [scalable event storage](docs/SCALABLE_EVENT_STORAGE.md).
- **Patterns & paper trades**: experimental event chains over Core plants and their ownership links, historical
  analogues and a cash-only paper account with automatic BUY/SELL/HOLD decisions. No broker, no real money. See
  [the extension guide](docs/EVENT_CHAIN_PAPER_ENGINE.md).
- **Investigations**: analyst-led cases with evidence from Core documents, hypotheses, contradictions, tasks and a
  revision history. See [the investigation guide](docs/INVESTIGATIONS.md).
- **Asset map**: locations and dependencies of Core plants, each with a Core source document. See [the map guide](docs/ASSET_MAP.md).
- **Trader assistant**: finds stored leads, Core plant facts, investigations and paper decisions with source references.
  See [the chatbot guide](docs/TRADER_CHATBOT.md).

## Run locally with Python

Requires Python 3.11+ and a running Data Core (its README shows how; here it runs on port 8000).

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
pip install -e .
alembic upgrade head
export WRITE_TOKEN="$(python -c 'import secrets; print(secrets.token_hex(24))')"
printf '%s\n' "$WRITE_TOKEN"
CORE_URL=http://127.0.0.1:8000 CORE_TOKEN=... uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Open [the Workspace](http://127.0.0.1:8001), choose **Workspace access** and paste the printed token to enable editing.
`CORE_TOKEN` is the Workspace's credential for the Core (its `WRITE_TOKEN`, or better an entry `"<token>": "workspace"`
in the Core's `WRITE_IDENTITIES_JSON`, so the Core's history names the Workspace); it is needed to propose facts and
for a Core that protects reads. SQLite is the default (`data/workspace.db`, lead-feed copies in `data/snapshots`); set
`DATABASE_URL` and `SNAPSHOT_DIR` for anything else. Without a reachable Core the Workspace still starts; its health
check and the Core-backed pages say the Core is unavailable.

For the fictional demo, restore the Core's demo in the Core repository and this repository's demo here
(`python scripts/restore_demo.py`), then start both on them; see [fixtures/demo](fixtures/demo/README.md).

## Run with PostgreSQL and Docker

```sh
cp .env.example .env
# Replace the placeholder secrets with independent generated hexadecimal strings.
docker compose up --build -d                                  # the Workspace alone, using a Core at CORE_URL
docker compose -f compose.together.yaml up --build -d         # the Data Core and the Workspace together
```

`compose.together.yaml` builds the Core from a checkout of its repository (`CORE_HOME`, default `../muniquant-data-core`);
the Core answers on port 8000 and the Workspace on port 8001, each with its own PostgreSQL database and volumes.
`docker compose down` stops without deleting data.

## Test

```sh
pytest -q
TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/test_db pytest -q
alembic check
```

The tests run every Workspace feature against a real Data Core: each test starts the Core as its own process with a
new database, from `CORE_HOME` (default `../muniquant-data-core`) with `CORE_PYTHON` (default its `.venv/bin/python`).
`tests/test_together.py` checks a running pair, for example the Docker Compose one; CI runs it
([.github/workflows/ci.yml](.github/workflows/ci.yml)).

## Split an existing platform database

```sh
python -m tools.split data/platform.db --core data/core.db --workspace data/workspace.db --report data/split-report.json \
  --snapshots data/snapshots --core-snapshots data/core-snapshots --workspace-snapshots data/workspace-snapshots --dry-run
```

Drop `--dry-run` to write. The source is only read; both targets must be new; the report compares counts, IDs and
fingerprints of every table before and after. Permutable material goes to the Workspace, everything else to the Core
through the Core's own import tool. See [the runbook](docs/RUNBOOK.md#split-an-existing-platform-database).

## Project layout

```text
app/          Workspace API and screens: leads, research, investigations, map, chatbot; the Core API client
tools/        Split tool (DC1 step B3)
migrations/   The Workspace migration line
scripts/      Demo restore, brand film rendering
fixtures/     The Workspace half of the fictional demo
tests/        Workspace tests against a running Data Core, the split tool and the together test
docs/         Architecture, decisions, operations and guides
```

Individual write identities are supported through `WRITE_IDENTITIES_JSON`. Reads are open by default on loopback;
enable `REQUIRE_READ_AUTH` and configure TLS/private ingress before shared deployment. Raw Permutable responses are
licensed data: keep the snapshot store private and never commit captures. No licence for redistribution of
third-party source data is implied by this repository.
