# The Workspace and the Data Core

The export contract, **CommodityEvidencePackage 1.0.0**, belongs to the Data Core and is unchanged: its schema, the
closed field list and the ten forbidden analytical fields are documented in the Core repository (`docs/CONTRACT.md`,
`GET /api/export/schema`). Leads, research, investigations, map records and paper trades never enter it.

This note is the Workspace's side of the connection: what it asks the Core for, what it sends, and what it stores.

## What the Workspace asks the Core for

All through [app/core_client.py](../app/core_client.py), never the Core database. Lists are read page by page
(1,000 per request) and each list at most once per Workspace request.

| Need | Core API | Used by |
|---|---|---|
| Plants and companies, with their names and aliases | `GET /api/records/entities`, `GET /api/records/entities/{id}` | leads (matching news to plants, search), research, investigations, map, assistant |
| Which plant replaced which | `GET /api/records/supersessions` | lead matching (a replaced plant points to the one that replaced it) |
| Documents (each ID is one exact version) and their saved bytes | `GET /api/records/documents[/{id}]`, `GET /api/documents/{id}/content` | lead confirmation, investigations, map, screens |
| Sources | `GET /api/records/sources` | screens, assistant |
| Facts | `GET /api/records/observations[/{id}]`, `?document_id=`, `?entity_id=` | lead confirmation, assistant, screens |
| Ownership and operator links, and when the Core recorded them | `GET /api/records/relationships`, `GET /api/records/audit?record_id=` | research event chains |
| Health | `GET /api/health` | Workspace health |

## What the Workspace sends

Only **candidate facts**: `POST /api/documents/{id}/extract` on a Core document, with the plant name as written, the
country, the dates, the attribute and unit and the exact words around the value. The Core treats it like any other
fact: source check, matching (unclear names go to its human review), quality checks; only then is a fact recorded. The
Workspace records each proposal and the Core's answer in its own history. It never writes plants, sources, documents,
links or reviews; curators do that in the Core's screens.

The Workspace authenticates with its own credential (`CORE_TOKEN`), best registered in the Core's
`WRITE_IDENTITIES_JSON` as the identity `workspace`, so the Core's history names the Workspace.

## What the Workspace stores

Core IDs, never copies of Core records. A reference keeps its meaning next year, even when newer facts arrive:

| Workspace record | Core references |
|---|---|
| Confirmed lead | primary-source document version (`primary_document_id`) and, optionally, the fact it supports (`observation_id`) |
| Lead revision | plants the event text mentions (`matched_entity_ids`) |
| Research event | plants (`entity_ids`); its chain keeps every ownership or operator link it used, with the link's document version (`core_relationships`) |
| Investigation | affected plants (`asset_ids`); evidence entries keep the document version (`document_id`) |
| Map location and dependency | plants and the supporting document version |

These are plain fields, not database links: the Core's database is not the Workspace's. The Workspace checks them
through the API when a record is written. The lead search text is the one derived value: it includes the current Core
names of matched plants and is recomputed by `python -m app.permutable refresh-search`.

## When the Core is unavailable

The Workspace still starts and its own records stay readable. Its health check reports the Core as unavailable, and
anything that needs the Core answers 503 with "Data Core unavailable" instead of guessing.
