# The split: Data Core and Workspace

DC1 gave the two parts of the platform their own homes. Until release `26a0bcd` (2026-10-20), one codebase, one
database and one migration history held both the data part and the research part. Now:

- **The Data Core** ([muniquant-data-core](https://github.com/alekspetrov9e/muniquant-data-core)) holds plants, companies,
  sources, documents and facts and proves where every fact came from: 26 tables and 3 views, the capture, matching,
  review and quality code, the data screens and the one export, CommodityEvidencePackage 1.0.0 (unchanged). It has no
  code that refers to leads, research, investigations or the map. Step A separated it.
- **The Workspace** (this repository) holds leads, research and practice trading, investigations, the map, the trader
  assistant and the old trading screens, with its own tables and migrations. Step B reconnected it to the Core.

## One connection

The Workspace reads and writes Core data only through the Core API, with [app/core_client.py](../app/core_client.py).
It stores Core IDs, never copies, and asks the Core for details. When a curator has checked a lead against a primary
source, the Workspace sends the Core a candidate fact with that source; the Core runs its own source check, matching
(unclear names go to its human review) and quality checks before the fact exists. The Core never calls the Workspace.
[CONTRACT.md](CONTRACT.md) lists what the Workspace uses.

## What moved where

| Before the split | Now |
|---|---|
| Plant, company, source, document and fact tables, matching, review, quality, export | Data Core |
| Data screens: assets, sources & evidence, review, data quality | Data Core (the Workspace links to them) |
| Permutable responses, saved copies, access decisions and capture logs (in the platform's `sources`, `documents`, `runs`... tables) | Workspace lead store: `lead_source`, `lead_source_access`, `lead_document`, `lead_document_version`, `lead_source_document`, `lead_snapshot`, `lead_run`, `lead_retrieval_attempt` |
| `lead`, `lead_revision`, `lead_headline`, research, investigation, map and old trading tables | Workspace, unchanged |
| Database links from Workspace tables to Core tables | Plain reference fields holding Core IDs |
| PostgreSQL triggers keeping lead search text current, one on the Core's plant table | Application code, plus `python -m app.permutable refresh-search` for Core renames |
| C++ name-matching kernel, export and replay tools, pilot, seed | Data Core |

Permutable data stays in the Workspace because a lead is a hint, never proof ([ADR 0003](adr/0003-permutable-lead-source.md)).

## Existing databases

They are not upgraded in place. `python -m tools.split` copies a platform database at revision `d8317b920a11` into a
new Core database (through the Core's own import tool) and a new Workspace database, reading the source only and
reporting counts, IDs and fingerprints of every table before and after. On the real-source pilot of 2026-10-21 and the
bundled demo every row arrived unchanged, and the pilot comparison (A6) run again on the split Core database gave the
same result (B4). See [the runbook](RUNBOOK.md#split-an-existing-platform-database) and
[the DC1-B status](DC1-B-STATUS.md).

## Older documents

The planning and delivery documents in this folder from before the split (ERD, data dictionary, source taxonomy, review
policy, validation, UAT, requirements matrix, release notes, reports) describe the platform as one system. Their data
parts now belong to the Data Core, whose repository holds the current versions: decision records, data dictionary,
source taxonomy, review policy, quality codes, risks and roadmap, the final demonstration and release notes. Since
2026-10-26 the Core also keeps market data (its `docs/MARKET_DATA.md`); this repository's old `market_observations`
table belongs to the old trading screens and is not that data.
