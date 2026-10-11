# ADR 0003: Permutable AI as a licensed, lead-only source

Status: accepted on 2026-10-11.

Context: MuniQuant holds a Permutable AI licence. Its API delivers news-derived events, headlines, sentiment indices, macro sentiment, trading signals and forecasts. The 12-week plan (p.25) keeps sentiment scores, event-severity models, trading signals and price prediction out of the team's backlog, and the Market Data Scope (section 7) keeps analytical signals out of the market-data layer. The plan also requires every fact to trace to source evidence, preferring company publications, government, regulators and industry bodies.

Decision:

- Register Permutable as one `commercial` source with an audited access policy: approved host `copilot-api.permutable.ai`, a `credential_ref` naming the server environment variable that holds the key (never the key), header `x-api-key`, and `usage_scope = leads_only`. The server binds each credential name to the hosts allowed to receive it (`LICENSED_CREDENTIALS_JSON`), so a writer cannot route platform secrets such as `WRITE_TOKEN` to another host.
- Capture only factual feeds: `/events/feed` and `/event_headlines/feed` with `event_type=Asset`, plus `/ticker/{t}/info` and `/events/topics/ticker/{t}` as reference provenance. Sentiment indices, asset headlines, macro sentiment, signals, insights and forecasts are not captured.
- Preserve every response page byte-for-byte as a document version through the existing acquisition path (approved host, pinned public address, retries, attempt log). An unchanged response deduplicates; a changed one becomes a new version.
- Parse responses with a versioned parser (`permutable-leads-1.0.0`) into leads: one lead per vendor event, each distinct factual state kept once as a revision with the snapshot that first carried it, and headlines with their links. Event text is matched against current entity names and aliases (exact canonical phrases of at least four characters). Direction and impact are not read; they remain only inside the preserved bytes.
- Leads are curator work items. Observations, relationships, identity evidence and extraction builds cannot cite a lead-only document (API rejection plus a `LEAD_SOURCE_CITED` BLOCK quality finding). A lead is confirmed only by linking a citable primary-source document, optionally with the observation recorded from it.
- CommodityEvidencePackage 1.0.0 is unchanged; leads and lead documents never enter it.

Alternatives: citing Permutable as secondary evidence would put vendor-derived claims into the package and weaken the primary-source rule; ingesting the analytics feeds conflicts with the plan's exclusions; overwriting the latest response (as the vendor's example poller does) would lose what was known at each point in time.

Consequences: leads widen discovery of curtailments, restarts, outages and ownership changes without changing the evidence boundary. `ALI_COM` is "Aluminum (COMEX)" in USD per metric ton, not an LME instrument. Polling live events and headlines every 15 minutes uses about 5,800 of the 250,000 monthly requests. Raw responses are licensed data: they stay in the local snapshot store and are never committed to the repository; tests use synthetic records.
