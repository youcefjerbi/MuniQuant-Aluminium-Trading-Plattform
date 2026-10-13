# Trader assistant

The floating **Trader assistant** is available throughout the workspace.
It searches stored event leads, asset identities and source-linked observations,
manual investigations, and the current paper account, latest stored quote and
decisions under its active policy. Choose a scope or use Automatic. Example:
choose Assets & evidence and ask "Test Smelter capacity"; choose Paper decisions
and ask "Explain recent paper decisions".

Local mode needs no AI credential and returns exact stored excerpts with numbered
references, dates, classifications and workspace links. Asset, investigation and
evidence buttons open their records. Conversations stay in browser memory, survive
navigation between screens, and clear on reload or Clear chat. It does not create
investigations, edit records, execute orders or change paper settings.

## Optional AI summaries

Local mode remains the default even if AI is configured. To enable the optional
OpenAI Responses integration, set these **server-side** environment variables:

- CHAT_AI_ENABLED=true
- OPENAI_API_KEY=your server credential
- CHAT_MODEL=a Responses-compatible model available to your account

Docker Compose passes these variables from the local .env file. Do not commit
credentials. Restart the application after configuration changes. The user must
enter a write identity through Workspace access and select **Use AI summary**.
The interface discloses that this sends the question, recent conversation and
retrieved excerpts to OpenAI. Only enable it when your data/feed licenses permit
that processing. No raw snapshots, API credentials or complete corpus are sent.
The request uses store=false; provider processing policies still apply.

AI receives at most eight conversation turns and bounded record excerpts. It has
no tools or SQL access. The server checks citation IDs, sets a 20 second request
timeout and output cap, and limits concurrent AI requests to two per process.
Provider failures/incomplete responses fall back to local excerpts with an
explicit notice. Deploy ingress rate limits and spend limits before offering
paid AI broadly; the per-process concurrency guard is not a distributed quota.

## Retrieval and limits

POST /api/chat/stream accepts the same payload and returns server-sent events.
The browser renders streamed text through textContent. Local excerpts are computed
first and displayed word by word; this is paced display, not model generation.
Configured AI uses stream=true and relays response.output_text.delta as it arrives.
AI text is labeled an unchecked draft until completion and citation-ID validation.
Validation checks identifiers, not whether each claim follows from its source.
Failed or invalid drafts are removed and replaced by local source excerpts.
Stop response or Clear chat cancels the fetch; partial drafts are discarded and
never enter chat history. Browser disconnect cancellation closes the asynchronous
provider connection and releases its concurrency slot. The network read timeout
is 20 seconds and the entire provider stream is bounded to 45 seconds. Ingress
proxies must permit streaming and honor X-Accel-Buffering: no.

POST /api/chat accepts message (1–1000 characters), scope, up to eight history
turns (user/assistant only) and use_ai=false. GET /api/chat/status reports whether
AI is configured, never the secret or model configuration. Private-read
deployments authenticate the POST endpoint as well as GET reads. AI always
requires a write identity, even on public-read deployments.

Retrieval limits each scope to a small page; it does not load the entire event
collection. Alone, this branch uses parameterized lexical database filters.
Merged with codex/scalable-event-storage, PostgreSQL event retrieval automatically
uses its GIN search projection. Independent deployment does not require that
migration. Asset/investigation substring search can still scan many rows;
add measured workload-specific indexes before large-scale search in those scopes.

Local mode is a source lookup assistant rather than a generative model. AI mode
can summarize and explain factors but is not guaranteed factual merely because
citations are valid: inspect the supplied sources. Neither mode fetches live
prices, predicts returns or supplies personalized trading instructions.
Unverified vendor leads and hypotheses remain distinct from sourced observations.
Paper decisions and account values remain simulations. Source date and quote
freshness matter; missing records produce an explicit no-match response.

## Validation

Run pytest -q tests/test_chatbot.py on SQLite and with TEST_DATABASE_URL on
PostgreSQL. Coverage includes no-match behavior, exact reported values, unverified
lead labels, follow-up retrieval, no database mutation, POST read authentication,
explicit/authenticated AI selection, bounded stateless provider payloads and
failure/invalid-citation fallback. Provider tests use synthetic mocked responses;
a paid live-provider request is not part of the tests.

Integration references:
https://developers.openai.com/api/docs/guides/text
https://developers.openai.com/api/docs/guides/streaming-responses
https://developers.openai.com/api/reference/resources/responses/streaming-events
