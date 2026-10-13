# Evidence trading agents

The Workspace offers an optional, evidence-only integration with [TauricResearch TradingAgents](https://github.com/TauricResearch/TradingAgents). It uses genuine upstream bull/bear researchers, research manager, trader, risk debaters and portfolio manager. It supplies industrial evidence and stored paper-account context instead of invoking the upstream vendor-data analysts or market-data tools. Results are research proposals; paper execution remains a separate explicit action.

## Install and configure

The extra pins TradingAgents 0.6.0 to commit `1394a3f72aa4393e1a98f51b382434c4b4c2d972`. The adapter checks both the installed distribution version and its Git provenance before running. Install from the project checkout with the optional extra; installing a similarly named wheel without the pinned provenance is insufficient.

```sh
pip install -r requirements.lock
pip install --no-build-isolation -e '.[trading-agents]'
alembic upgrade head
```

Configure these environment variables on the Workspace server:

| Variable | Purpose |
| --- | --- |
| `TRADING_AGENTS_ENABLED=true` | Explicitly enable analysis; disabled by default. |
| `TRADING_AGENTS_PROVIDER` | `openai` or `ollama`. |
| `TRADING_AGENTS_QUICK_MODEL` | Explicit model for researchers, trader and risk debate. |
| `TRADING_AGENTS_DEEP_MODEL` | Explicit model for research and portfolio managers. |
| `OPENAI_API_KEY` | Server-only provider key when using OpenAI. |
| `TRADING_AGENTS_OLLAMA_URL` | Local Ollama endpoint; defaults to `http://localhost:11434/v1`. |
| `CORE_API_URL` | Data Core service base URL, without `/api/export`. |
| `CORE_API_TOKEN` | Optional Core authentication token. |

Use HTTPS for remote Core services. Local HTTP is accepted for localhost, loopback and the local `core` service. The Ollama endpoint must remain local. The browser cannot choose model-provider endpoints or supply provider credentials. Existing Workspace writer authentication applies to analysis, cancellation and paper application. Provider availability and model suitability are operator responsibilities.

## Trader workflow

1. Configure a paper account and policy under **Patterns & paper trades**, using the exact instrument you intend to analyse. Record a nonhistorical quote from the last five minutes.
2. Open **Evidence trading agents**. Select exported Core assets, inspect record identifiers, quality status and synthetic flags, and explain the instrument-to-asset mapping. Industrial capacity, outages and ownership facts are evidence; their effect on a tradable instrument is a hypothesis.
3. Explicitly consent to sending the selected evidence and simulated portfolio information to the configured provider. A run can make multiple model calls and incur provider charges.
4. Review the suggested action, reasoning, exact evidence citations, agent reports and build fingerprint. Cancel an active run if needed. The worker has a four-minute deadline; the page polls for up to five minutes and history can be refreshed afterward.
5. Choose **Apply to paper account** only when permitted. This records a simulated decision and rechecks the current portfolio, policy and quote. There is no real broker connection or live order execution.

## Evidence boundary and safeguards

Core reads use its HTTP `/api/export` contract, `CommodityEvidencePackage` 1.0.0. The Workspace validates schema, build fingerprint, identities and evidence provenance, and bounds package size and selected records. It does not connect to the Core database. The transient model context contains selected exported facts; the stored run retains Core identifiers, version/fingerprint references, mapping rationale, paper inputs and analytical outputs. It does not create a mirrored Core master or industrial fact table.

The adapter treats source text and model output as untrusted data. External model tool calls are rejected. Directional proposals must cite selected evidence identifiers; unrecognised citations or malformed output fail validation. Synthetic facts, unresolved quality warnings, captures older than one year and future-dated captures or publication dates prevent directional paper execution. These checks constrain execution; they do not establish that a model's interpretation or forecast is correct.

Applying a proposal checks account and policy consistency, a current nonhistorical quote, exposure, available cash/position, drawdown, cooldown, daily trade limits, fees and slippage. It uses optimistic concurrency and a run-to-decision link to prevent repeated application. No short position is opened. Cancelled, failed or incomplete runs cannot be applied.

## Verification

The base CI remains responsible for the full Workspace suite and migration checks. The optional TradingAgents workflow installs the pinned extra and exercises the real upstream node factories with fake model responses, alongside the paper-account guard tests. These checks make no paid provider calls and do not verify real-provider latency, model quality or profitability. Validate an enabled deployment separately with an explicitly consented paper analysis and configured provider credentials.

The existing Docker image keeps the integration disabled and omits the optional dependency. Use the optional-extra installation above for an enabled Workspace. This feature branch does not complete or bypass the separate DC1-A/DC1-B extraction gates.

Local verification: 211 tests passed and one PostgreSQL-specific test skipped on SQLite; all 212 passed on PostgreSQL. Migration upgrade/check/downgrade/upgrade passed on SQLite. The new page was checked in light and dark mode against the local fictional evidence export. No live provider request or real-money order was made.
