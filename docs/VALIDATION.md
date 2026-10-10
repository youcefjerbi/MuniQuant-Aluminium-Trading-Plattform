# Validation — 2026-10-10

Baseline 0ed0c17, scope correction branch codex/upstream-evidence-gate1.

| Check | Actual result |
|---|---|
| Install pinned requirements and editable package | Pass on macOS / Python 3.14; C++17 extension compiles |
| pytest -q | 18 passed, one Starlette/httpx deprecation warning |
| Unit/API fixtures | Pass: Python capacity conversion, native Unicode name distance, authorization, document dedup/version, append-only history, invalid facts, ambiguity/review audit, atomic/sequential-idempotent CSV, source access, FK, UI headers, export integrity/determinism, frozen stored-output restoration |
| Upstream boundary regression | Pass: market API absent, no market/trading OpenAPI routes, no market workspace payload, empty draft market export, removed navigation and unavailable trading script |
| Alembic upgrade → check → downgrade base → upgrade → check | Commands pass on SQLite; no schema diff detected; WARNING: legacy SQLite batch downgrade omits unnamed observation CHECK constraints (known integrity risk, not clean production migration proof) |
| Generated export schema | Unchanged after scripts/export_schema.py |
| JavaScript syntax | node --check app/static/app.js passes |
| Whitespace diff check | git diff --check passes |
| PostgreSQL / Docker | Not run locally: installed Docker CLI cannot connect to stopped daemon |
| Remote CI | Outcome not assumed; inspect PR checks |
| Real source acquisition / PDF extraction / full UAT / frozen-input parser rerun | Not implemented or demonstrated; synthetic/local fixtures only |

CI now sets DATABASE_URL to PostgreSQL for the PostgreSQL migration round-trip job; previously both migration checks used SQLite. This configuration change is not itself proof of PostgreSQL success.

Legacy observation CHECK constraints must be named/restored through migration before production acceptance. alembic check alone does not prove CHECK-constraint integrity. Candidate equivalence from bundle restore is not evidence of acquisition/parser rerun reproducibility. Real data coverage has not been measured or fabricated.

No Gate 1–6 approval, completed twelve-week delivery, production release or downstream integration is claimed.
