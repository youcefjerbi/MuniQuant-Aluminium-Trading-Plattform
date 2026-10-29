# DC1-B status: reconnect the Workspace

**Signed off.** DC1 was signed off (A and B, including A8 and B6) on 2026-10-26. Core pull
requests #1 and #2 and this repository's #19 are merged. The report below is the state at review time.

Status on 2026-10-21, in the team's report form: Done, Evidence, Blockers, Decisions, Next. Work is on this
repository's `feature/dc1-b-reconnect-workspace`. The Data Core's side (`feature/dc1-b-core-api`, Core pull request #2)
was merged into the Core's `main` on 2026-10-26, after DC1-A (Core pull request #1). DC1-A's own status is in the Core
repository (`docs/DC1-A-STATUS.md`).

The specification says DC1-B "starts only after every DC1-A step has passed". It started on 2026-10-21 at Aleks's
request while A8 (the dates note) still awaits review and Core pull request #1 awaits sign-off; nothing in DC1-B
depends on the dates note.

## Done

| Step                            | State                                                             | Done when (specification)                                                                                                                                                                                                                                                              |
| ------------------------------- | ----------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| B1 Clean Workspace database     | **Done locally**, CI pending                                      | One straight migration creates the Workspace's own tables and no Core table; links to Core tables are plain reference fields. Setup, drift check and round trip pass on SQLite, PostgreSQL 16 and 17 (`tests/test_schema.py`).                                                         |
| B2 Connect them                 | **Done locally**, CI pending                                      | A small API client (`app/core_client.py`) serves plants, names, documents, facts and candidate facts. Leads, research, investigations, the map and the trader assistant work end to end against a running Core: every Workspace test starts a real Core process with its own database. |
| B3 Split tool                   | **Done locally**, CI pending                                      | `python -m tools.split` works on the real pilot and the demo data with a report that matches before and after; Permutable material goes to the Workspace side.                                                                                                                         |
| B4 Same results after the split | **Done**                                                          | A6 run again on the Core database the split tool produced: same result, all checks pass.                                                                                                                                                                                               |
| B5 Running together             | **Done locally**; CI **blocked**                                  | Docker, setup and the demo restore work for each part alone and both together, and one test runs them together. Both projects green in CI is blocked: the Workspace CI cannot read the private Core repository yet (Blockers).                                                         |
| B6 Docs                         | **Done**: reviewed and agreed with the DC1 sign-off on 2026-10-26 | README, contract, runbook and data diagram in both repositories, and [a short note on the split](SPLIT.md).                                                                                                                                                                            |

## Evidence

- **Tests, locally** (the Workspace's run against a real Core): Workspace 98 passed on SQLite, 100 on PostgreSQL 16
  and 100 on PostgreSQL 17 (the remaining skips are PostgreSQL-only tests on SQLite and the together test, which runs
  against a running pair); Core 101 passed on each of the three databases.
- **B1**: the Workspace baseline equals today's platform tables (release `26a0bcd`, revision `d8317b920a11`) field by
  field, on SQLite and PostgreSQL, except the documented split differences (`tests/fixtures/schema`): the lead feed's
  rows in their own `lead_*` tables, links to Core tables as plain fields, no `usage_scope` column, no triggers.
- **B2**: `tests/test_core_connection.py` confirms a lead with a fact the Core accepted from a Workspace proposal,
  sends an unclear plant name to the Core's human review, refuses proposals the Core cannot check, builds research
  chains from Core ownership links the Core had recorded in time, and reports an unreachable Core instead of guessing.
  The screens were checked in a browser against the Docker pair.
- **B3, real pilot of 2026-10-21**: PASS. All 15 plants, 5 companies, 7 documents and the other rows went to the Core
  unchanged; the Workspace received the old trading screens' practice account. The pilot database's SHA-256 was the
  same before and after (`289b6847…bbdb0`).
- **B3, demo**: PASS, and the Core side exports the platform demo's package unchanged (build hash `c6f6b3d6…2b8a95`).
- **B3, Permutable material**: a mixed database made by the platform's own code at `26a0bcd`
  (`tests/fixtures/platform-mixed`) splits with its lead source, access decision, three responses and their saved
  copies, five capture runs, three attempts and their history on the Workspace side, the evidence on the Core side; both
  applications then work on their halves. A local copy of a real Permutable test database (500 leads, licensed, never
  committed) split the same way.
- **B4**: `tools.compare_pilot --core-database` on the split Core database: PASS, 16 of 16 checks (the 15 of A6 plus
  "Core database unchanged"): byte-identical export (`abfc10ff…bd32`), build hash `87894401…695e`, recipe
  `568cc60a…80305`, the same 7 saved pages, matching decisions and quality (WARN, 11).
- **B5**: `compose.together.yaml` builds and starts both with their own PostgreSQL databases; `tests/test_together.py`
  passes against them, and the Core's history names the Workspace's proposal `workspace`. The Workspace image runs alone
  without a Core (health OK, Core reported unavailable, Core pages answer 503). Both demo restores pass `alembic check`.

## Blockers

- **The Workspace CI needs read access to the private Core repository.** Its tests, the container job and the together
  test check out the Core. Either make the Core repository public (its code was public in this repository until the
  split) or add a read-only token as the secret `CORE_REPOSITORY_TOKEN` here. Until then the Workspace CI fails at the
  Core checkout.
- **Reviews**: A8 (dates note), B6 (docs) and sign-off of the pull requests.
- **The pilot baseline files exist on one machine only**, as noted for DC1-A; B4 ran there.

## Decisions

Each follows the specification as closely as possible.

1. **Permutable material gets its own store in the Workspace.** The specification: "the Permutable responses, their
   saved pages and the lead tables all live in the Workspace". The platform kept them in Core tables, so the Workspace
   now has `lead_source`, `lead_source_access`, `lead_snapshot`, `lead_document`, `lead_document_version`,
   `lead_source_document`, `lead_run` and `lead_retrieval_attempt`, shaped exactly like the tables they came from, and
   the capture code works on them unchanged. `usage_scope` is gone: every lead source is lead-only.
2. **The Core API grew only generic reads**: one record by ID, equality filters, and supersessions as a record type
   ("new code is only for the separation: ... the API connection"). Nothing in the Core refers to the Workspace.
3. **Candidate facts use the Core's existing extraction endpoint**: "It runs the same steps as for any other fact".
   No new Core write path.
4. **The lead-search triggers became application code.** One of them lived on the Core's plant table, and "the Core does
   not know the Workspace". The text is identical (compared on PostgreSQL); a Core rename reaches it on the next
   `refresh-search` run.
5. **References that stay meaningful**: a confirmed lead keeps the Core document version and the fact; a research chain
   keeps every Core ownership or operator link it used with that link's document version; investigations keep document
   versions; the map keeps plant and document IDs. No Workspace record uses an export, so none stores a build
   fingerprint; each proposal's Core build ID is in the Workspace's history.
6. **The data screens are the Core's.** The Workspace removes them from its screens and links to the Core; its pages
   read Core data through Workspace routes that use the client, never from the browser.
7. **One Workspace identity in the Core.** The Workspace authenticates as `workspace` (an entry in the Core's
   `WRITE_IDENTITIES_JSON`); the curator's name is in the Workspace's own history.
8. **The split tool lives in the Workspace**, which knows both sides. The Core side is written by the Core's own import
   tool in the Core's environment, so the Workspace never writes the Core database. It reads only platform databases at
   the last release's revision; older ones are upgraded on a copy first.
9. **Nothing is changed to make a check pass.** References that point to lead-feed records instead of Core records are
   kept and listed in the split report; a Core fact citing a vendor response stops the split.
10. **The old trading screens' tables stay as they are** ("no connection needed"); `market_observations.document_id`
    became a plain field.
11. **The Workspace demo is the Workspace half of the platform demo** (the practice account). The fictional research
    demo stays `python -m app.research_demo`.
12. **Ports**: the Core keeps 8000; the Workspace uses 8001 next to it.
13. **The Workspace CI tests against the Core's `main`** (DC1-A and the Core side of DC1-B, merged 2026-10-26); it
    should pin the Core's v1.0.0 tag at the handover.

## Next

- Decide the CI access to the Core repository (Blockers), then push this branch and open the pull request.
- Review: A8, B6 and the three pull requests. Merge order: Core #1 (DC1-A), the Core's DC1-B branch, then this one.
- Tag the Core v1.0.0, pin the Workspace CI to it, and hand over the split reports, the A6 and B4 comparisons and a
  private copy of the pilot baseline with the Core's frozen pilot export.
