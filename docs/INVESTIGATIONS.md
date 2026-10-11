# Manual disruption investigations

This is an analyst-led workspace separate from Permutable leads, event research and paper trading. A case can be created without any API event. Vendor captures never create, update or confirm cases. Manual findings never place trades or modify influence scores. This PR branches directly from main and does not require the experimental paper-engine PR.

Run the README startup instructions, including `alembic upgrade head`, then open **Investigations**. Create a case with its title, description, region, investigator, next review timestamp and affected registered assets. Add research entries as evidence, hypotheses, contradictions, questions, notes or conclusions. Evidence requires a registered document or HTTP(S) source URL. URLs are references only; the server does not retrieve them. To preserve content, capture a document in Sources & evidence and reference that snapshot.

Open a case to inspect the notebook and complete revision history. Update status to investigating, confirmed, disproven, resolved or inconclusive. Every finding status requires a notebook conclusion; confirmed also requires sourced evidence. These checks ensure documentation, not independent factual verification. Cases can be reopened. Correct an earlier entry by appending a correction note; previous versions are retained. Each revision records the authenticated workspace actor, timestamp and snapshot. Writes use existing Workspace access credentials; read authorization follows existing server configuration.

API: `GET /api/investigations` supports status, offset and limit (maximum 100). `POST /api/investigations` creates a case. `GET /api/investigations/{id}` returns the case and revisions. `POST /api/investigations/{id}/revisions` accepts `expected_version`, optional `status`, `owner`, `review_at`, and an optional `entry` with `kind`, `text`, `document_id` and `source_url`. A stale version returns 409; refresh and reconsider the edit. Entries are append-only through the API, with a maximum of 1,000 per case. API write access is workspace-wide, not case-owner-specific.

Migration `b8e21ad4c902` adds investigation and investigation_revision tables. Existing industrial exports and Permutable contracts do not include these analyst judgments. No new package, vendor credential or network service is needed.

Implemented: separate navigation, case creation, registered asset associations, categorized notebook, evidence references, owner/review schedule, status findings, append-only revision trail, optimistic concurrency, pagination API and existing authorization. Not implemented: automatic corroboration, file uploads inside cases, reminders, per-case permissions, assignment notifications, automatic API links or market-impact inference.

## Tasks and evidence comparison

Open a case and select **Add investigation task**. Record a question, assignee, optional timezone-aware deadline, and status (open, in progress, answered, cancelled). Active tasks past their deadline show OVERDUE. Use **Update task** to record progress, cancel, or reopen. Answered tasks require both an answer and references to evidence entries in the same case. Assignments are labels, not permissions or notifications. Every task change preserves a case revision, with creation and update actors. Existing cases without a tasks field remain supported; no additional migration is needed. Maximum 200 tasks per case.

When adding evidence, choose a related hypothesis and classify its position as supports, contradicts or context. Optionally enter an exact source passage and publication timestamp. **Compare evidence** displays supporting and contradictory entries side by side, with context separately. Source titles, publication/recording times, related hypotheses and source passages are visible. Passages are analyst transcriptions, not automatically verified extractions; registered document inspection remains available. Classification never proves source independence, factual accuracy or causality.

API revisions additionally accept `task` with optional existing `id`, `question`, `assignee`, `due_at`, `status`, `answer` and `evidence_entry_ids`. Existing tasks are updated by ID; omissions use the documented schema defaults, so send all fields to retain current values. Entry schema adds `hypothesis_id`, `stance`, `passage` and `published_at`. Cross-case task/evidence/hypothesis references are rejected. Case-level optimistic concurrency applies to every update.

## Relational storage model

`investigation` retains the current versioned case snapshot and metadata. `investigation_revision` retains full historical snapshots for reproducible review. Current notebook records additionally live in dedicated relational tables:

- `investigation_entry`: append-only entry ID, case foreign key, entry kind/text, registered-document foreign key, hypothesis self-reference, evidence position, source URL/passage, publication time, recorded time and actor.
- `investigation_task`: task ID, case foreign key, question, assignee, deadline, status/answer, and creation/update actors and timestamps.
- `investigation_task_evidence`: a many-to-many association with a composite primary key preventing duplicate task/evidence links.

Indexes support case notebook lookup, entry-kind filtering, assignee, deadline and task-status queries. Database foreign keys prevent dangling case, document, hypothesis, task and evidence references. Same-case association and evidence-kind rules are enforced by the service. All normalized writes and case revision changes occur in one transaction after optimistic version checks; a failed request rolls back both. The current case snapshot remains the UI read contract, with normalized records maintained as a queryable projection; `/api/investigations/{id}/notebook` reads the relational entries and tasks directly. Historical snapshots are not rewritten when a task changes.

Migration `c9f302be1147` backfills existing case snapshots without changing notebook IDs, recorded times or revisions. Downgrade removes only the normalized projections; snapshots remain, so re-upgrade rebuilds the current records. Run `alembic upgrade head` before starting the updated backend. Source files remain in the existing content-addressed document store; notebook entries reference document metadata rather than duplicate binary contents. PostgreSQL is the deployment database; SQLite remains supported for local tests/previews. Normalized projections and snapshots should be backed up together with the existing document store.
