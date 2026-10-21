# Workspace runbook

Deployment, lead-feed operations, the split of existing databases and recovery for the Workspace. The Data Core has
its own runbook in its repository (source onboarding, export, freeze and replay, Core backups).

## Setup

The README has local and Docker instructions. Install the pinned dependencies and run `alembic upgrade head` before
starting the API; migrations never run hidden inside the API. A Data Core must be reachable for Core-backed pages.

| Variable | Purpose |
|---|---|
| DATABASE_URL | SQLAlchemy URL; default local SQLite `data/workspace.db`, deployed postgresql+psycopg |
| SNAPSHOT_DIR | Persistent directory for the lead feeds' saved copies (licensed data: keep private) |
| CORE_URL | How this server reaches the Data Core, default `http://127.0.0.1:8000` |
| CORE_PUBLIC_URL | The Core address people open in their browser (links in the screens); default CORE_URL |
| CORE_TOKEN | The Workspace's credential for the Core: an entry `"<token>": "workspace"` in the Core's WRITE_IDENTITIES_JSON (or its WRITE_TOKEN). Needed to propose candidate facts, and for reads when the Core sets REQUIRE_READ_AUTH |
| WRITE_TOKEN / WRITE_ACTOR | Single Workspace credential and recorded actor; absent token disables writes |
| WRITE_IDENTITIES_JSON | JSON map of separate bearer credentials to reviewer identities |
| REQUIRE_READ_AUTH / READ_TOKEN | Protect Workspace API reads except health; optional read-only credential |
| POSTGRES_PASSWORD | Compose database secret |
| PERMUTABLE_API_KEY / PERMUTABLE_TICKERS | Licensed Permutable key (only its variable name is stored) and tickers to poll, default `ALI_COM` |
| LICENSED_CREDENTIALS_JSON | Credential variable names and the only hosts allowed to receive them; default `{"PERMUTABLE_API_KEY": ["copilot-api.permutable.ai"]}` |
| CHAT_AI_ENABLED / OPENAI_API_KEY / CHAT_MODEL | Optional trader-assistant summaries |

With `compose.together.yaml`, also `CORE_HOME` (Core checkout), `CORE_POSTGRES_PASSWORD` and `CORE_WRITE_TOKEN`; the
file registers `CORE_TOKEN` in the Core as the identity `workspace`. Use an ignored `.env` for secrets; Compose loads
it, plain Python does not.

## Licensed event leads (Permutable AI)

Permutable is a lead-only source ([ADR 0003](adr/0003-permutable-lead-source.md)): its events point curators to
industrial changes; facts must cite a primary source in the Data Core.

```sh
export PERMUTABLE_API_KEY=...            # or set it in .env for Compose
python -m app.permutable setup           # lead source + audited access decision + reference responses
python -m app.permutable capture --feed events --mode historical --since 2026-07-01   # optional backfill
python -m app.permutable capture --feed event_headlines --mode historical --since 2026-07-01
python -m app.permutable poll            # live events + headlines; schedule every 15 minutes
python -m app.permutable refresh-search  # lead search text with current Core plant names; schedule hourly
```

The same operations are POST /api/permutable/source, /api/permutable/access (a new access decision: restrict, re-review
or permit again) and /api/permutable/capture, and buttons on the Event leads screen. Each response page is a
fingerprinted document in the lead store; an unchanged poll is a duplicate. Historical windows follow `next_token` up
to `max_pages` (default 10, 500 records each). A 403 means the key is missing, not recognised or not licensed for that
ticker; HTTP 429 is retried with 1 s and 2 s back-off. Keys with control characters are rejected and an echoed key is
redacted. Setup never reopens a restricted or under-review source. If the Core is unreachable during a capture, the
saved response stays registered and a failed run is logged without partial leads.

Curator workflow: filter leads by status, plant match and topic; open headline links; Follow up or Dismiss with a
reason. To confirm, capture the primary source (company, regulator, industry body) in the Data Core, then on the lead
choose **Propose fact to the Data Core**: the Core extracts the value from its saved copy, matches the plant and checks
quality, or sends an unclear name to its human review. When the Core has recorded the fact, **Confirm with primary
evidence** with that Core document and fact. POST /api/permutable/documents/{id}/replay re-parses a saved response and
proves the stored lead facts are equivalent; GET /api/permutable/documents/{id}/content returns its exact bytes.

## Split an existing platform database

`tools/split.py` turns a database of the combined platform (revision `d8317b920a11`, release `26a0bcd`) into a new
Data Core database and a new Workspace database. Upgrade an older platform database first, on a copy, with the
platform at `26a0bcd` (`alembic upgrade head`).

```sh
python -m tools.split PLATFORM_DB --core CORE_DB --workspace WORKSPACE_DB --report data/split-report.json \
  --snapshots PLATFORM_SNAPSHOT_DIR --core-snapshots NEW_CORE_SNAPSHOT_DIR --workspace-snapshots NEW_WORKSPACE_SNAPSHOT_DIR \
  [--core-home ../muniquant-data-core] [--core-python ../muniquant-data-core/.venv/bin/python] [--dry-run]
```

Rules: the source is opened read-only and never changed (a SQLite source is fingerprinted before and after); both
targets must be new (a SQLite path that does not exist, or an empty PostgreSQL database); `--dry-run` writes only the
report; the report (JSON, with a Markdown summary next to it) compares counts, IDs and fingerprints of every table
before and after, and the step fails on any difference. The Core side is written by the Core's own import tool in the
Core's environment, leaving out the rows that go to the Workspace; the Workspace side through the Workspace migrations.
Permutable material (every source with a lead-only access decision and its responses, copies, runs, attempts and
history) goes to the Workspace's lead store. The tool refuses, writing nothing, when a Core fact cites a vendor
response, a source mixes lead-only and evidence decisions, or the database holds unknown tables. Workspace references
that point to lead-store records rather than Core records (for example an investigation note citing a vendor response)
are kept and listed in the report.

Then point each application at its database and snapshot directory, run `alembic check` on both, and, on PostgreSQL,
`python -m app.permutable refresh-search` once. Run the pilot comparison on the new Core database (in the Core
repository: `python -m tools.compare_pilot --core-database CORE_DB --output NEW_DIR`).

## Logs, health and pagination

GET /api/health checks the database and reports the Core's reachability without failing on it. JSON request logs carry
method, path, status and duration, without tokens or content. Lead runs and retrieval attempts record successful,
duplicate and failed captures. GET /api/records/{type}?offset=0&limit=100 pages through leads, lead revisions and
headlines, the lead store and the audit history. `alembic check` detects schema drift.

## Coordinated backup and restore

Back up each part separately and keep the pairs together. For the Workspace: stop the app, dump the Workspace
PostgreSQL database (`docker compose exec -T db pg_dump -U workspace -d workspace -Fc`) and archive the lead snapshot
volume; record the migration revision and SHA-256 checksums. Restore into a fresh database and volume, never over the
working ones, then run `alembic upgrade head`, `alembic check` and a replay of a few lead documents before enabling
writes. Workspace records hold Core IDs, so restore Core and Workspace backups taken at the same time; a Workspace
reference to a Core record that a Core restore no longer holds shows up as "not registered" when written again.
For SQLite, use Python's sqlite3 backup on the quiescent database and archive its snapshots. Rehearse before shared use.
