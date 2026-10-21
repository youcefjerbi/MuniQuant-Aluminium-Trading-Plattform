# Scalable event storage

## Choice

Keep PostgreSQL as the transactional system of record. Existing unique
(source_id, external_id) and (lead_id, content_hash) constraints deduplicate
polling and preserve immutable vendor revisions. Raw responses remain exact,
content-addressed snapshots for provenance and replay.

Add a search projection on each lead, a PostgreSQL GIN full-text index, and
composite indexes for status/topic/date queries.
Search now filters, counts, ranks and paginates inside PostgreSQL; only the
selected page is loaded into application memory. Asset hydration is restricted
to IDs in that page. The local SQLite fallback retains TF-IDF search.

PostgreSQL search uses the simple language configuration and OR between
normalized query words. It searches current event title/summary/topic,
canonical matched asset names, and every linked headline. Scores are normalized
lexical relevance, not TF-IDF cosine or market probabilities. The response's
ranking field identifies the algorithm. Older event revisions do not
contaminate the current event search, while historical headlines remain
searchable.

Since the split (DC1 step B), plant names live in the Data Core, so the
Workspace maintains the projection itself (`app.permutable.refresh_search`)
instead of database triggers: every capture refreshes the leads it touched,
with the current Core names. The Core cannot call the Workspace, so a plant
renamed in the Core reaches the projection on the next
`python -m app.permutable refresh-search`; schedule it, for example hourly.
The text equals what the former trigger function produced
(`tests/test_event_storage.py` compares them on PostgreSQL).

## Apply and verify

Set DATABASE_URL to PostgreSQL, then run `alembic upgrade head`; the Workspace
baseline creates the indexes. A database split from the platform keeps the
projection values it had; run `python -m app.permutable refresh-search` once to
recompute them with the Core's current names.

```sh
TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost/testdb pytest -q tests/test_event_storage.py tests/test_permutable.py
```

Tests create and drop unique schemas. Use a database role allowed to create
schemas. PostgreSQL coverage checks projection updates, current revision
selection, Core plant renames, equality with the former trigger function and an
EXPLAIN plan using the GIN index. The tests need a Data Core (see the README).

## Growth plan and practical limits

Use the existing paged poller with one scheduled poll worker initially; retain
its idempotent retries. Multiple API workers can share PostgreSQL without
duplicating search state. Configure a bounded connection pool per worker,
pgBouncer when connections become limiting, and measure query latency,
ingestion latency, database size and snapshot growth. Exact counts and deep
offset pages still cost work; introduce cursor pagination if measured usage
requires it. Do not treat this as a benchmarked throughput guarantee.

Keep snapshots on persistent storage today; move to licensed, access-controlled
object storage with a storage adapter when multiple hosts are needed.
Database backups must be coordinated with snapshot backups. Search replicas
can serve read-heavy workloads with an explicitly accepted lag. Partition
append-only revision history by capture time only when measured history size
justifies the extra deduplication and foreign-key complexity. Kafka/ClickHouse
are later options for sustained ingestion/analytical workloads, not required
for today's lead queue.

Sources: https://www.postgresql.org/docs/16/textsearch-indexes.html and
https://www.postgresql.org/docs/16/textsearch-tables.html
