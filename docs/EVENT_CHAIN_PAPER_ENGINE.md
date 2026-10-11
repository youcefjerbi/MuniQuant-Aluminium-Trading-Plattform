# Event chains and automatic paper decisions — experimental v0.1

This branch implements the sponsor's new downstream research request. It is a scope amendment to the original upstream-only project, not completion of a requirement in the old PDF. It does not change the closed industrial evidence export contract. The existing weekly reports remain records of the upstream baseline.

## What works

An authenticated incoming event is stored immutably with occurrence time, availability time, kind, instrument, title, summary, source reference, optional registered entities, countries and relationship tags. Supported kinds are sanction, conflict, policy, weather, energy, logistics, supply, demand, corporate and other. External keys make retries idempotent; revised content needs a new key.

The engine builds an immutable 72-hour chain using shared entities, audited company/facility relationships, shared tags, or shared countries across different event kinds. Edges explain the association and explicitly set `causal: false`. The chain includes ordered event kinds and transition features. It is a heuristic association graph, not an automatic determination of geopolitical causality.

Historical chains of the same instrument and final event kind are compared using weighted cosine similarity of event kinds, ordered transitions, tags, countries and words. Historical returns use prices observed within five minutes after event availability and 24 hours later (five-minute tolerance). Outcomes must have become available before the incoming event. Current and historical windows are separated by four days; selected examples cannot share events or overlap their 72-hour feature/24-hour outcome windows.

An opt-in rule evaluates each new nonhistorical event automatically. It uses a similarity-weighted historical mean and sign agreement, minimum independent sample count, and a threshold including assumed round-trip fees and slippage. It produces BUY, SELL or HOLD. SELL only reduces an existing long position. This is an unvalidated experimental rule; a similarity score is not a probability, and a successful synthetic demonstration is not evidence of predictive value.

The paper ledger starts with 100,000 simulated cash units, uses decimal arithmetic, versions every policy, and stores the event chain, selected examples, quote, reason, policy, fee, assumed fill, cash and position for every decision. Duplicate incoming events cannot trade twice. PostgreSQL row locks and conditional account-version updates serialize changes. Pausing blocks new orders; it does not liquidate positions. Drawdown blocking is checked on incoming events with fresh quotes, not continuously between events.

New live Permutable captures bridge captured event revisions into the research stream. Classification is keyword-based and should be reviewed; the bridge defaults to `ALUMINIUM_DEMO` and does not establish an exchange-instrument mapping. Historical captures and the manual **Import event leads** button import historical records and cannot trigger orders. Capture responses expose bridge failures separately; research failure does not erase an already captured vendor snapshot. Existing imported revision keys are not retroactively traded.

## Run the fictional end-to-end demonstration

After installing the application using the README's Python guide, use a separate database:

```sh
source .venv/bin/activate
export DATABASE_URL=sqlite:///data/paper-research-demo.db
export SNAPSHOT_DIR=data/paper-research-demo-snapshots
alembic upgrade head
python -m app.research_demo
export WRITE_TOKEN="$(python -c 'import secrets; print(secrets.token_hex(24))')"
printf '%s\n' "$WRITE_TOKEN"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/#research> and enter the printed token in **Workspace access** to edit. The demo intentionally enables paper automation, imports five fictional weekly sanction → energy → supply chains and price outcomes, then adds a fresh quote and a current chain. The first two incoming events HOLD; the final event produces an automatic simulated BUY. The demo refuses an existing research workspace. This is not a geopolitical forecast or profitable-trading demonstration.

For an existing installation, run `alembic upgrade head` before starting this branch. PostgreSQL deployments receive the same tables through the Docker migration service. No new Python dependencies or C++ components are introduced. The prior event-similarity-search PR is independent and is not bundled into this branch.

## Ingest new data

All POST endpoints require `Authorization: Bearer <WRITE_TOKEN>`. Do not put credentials into source references. JSON rejects unknown fields. Supply timestamp timezones explicitly.

1. `POST /api/research/policy` with `{"enabled": false}` creates a paused paper account. Other fields can set instrument, sample threshold, similarity threshold, directional agreement, edge threshold, order notional, exposure, drawdown, fees, slippage, cooldown, daily order count and freshness. Read active configuration at `GET /api/research`. Explicitly save `enabled: true` to enable simulated orders.
2. `POST /api/research/quotes` with `external_key`, `instrument`, `price`, `occurred_at` (price observation timestamp), and `source_reference`. A current event needs a fresh nonhistorical quote beforehand. Quote arrival alone never creates a trade.
3. `POST /api/research/events` with the event fields below. The response includes the chain and automatic decision when a matching paper account exists. A live event's availability time is assigned by the server.
4. `GET /api/research/events/{id}/analogues` retrieves historical matches as of that event's availability time. This exploratory endpoint uses the currently configured policy; original decisions retain their own policy snapshots.
5. `POST /api/research/outcomes` with `event_id`, `entry_quote_id`, `exit_quote_id` creates the immutable, computed historical outcome. This is the only label mechanism; arbitrary hand-entered returns are not accepted.
6. `POST /api/research/import-leads` bridges existing lead revisions for historical research.

Example event body (replace the timestamp with the actual occurrence time):

```json
{
  "external_key": "publisher:event-id:revision-1",
  "instrument": "ALUMINIUM_DEMO",
  "kind": "energy",
  "occurred_at": "2026-10-11T12:00:00Z",
  "title": "Power interruption at a registered smelter",
  "summary": "Factual source summary without a vendor impact score",
  "source_reference": "document:captured-document-id",
  "entity_ids": [],
  "countries": ["NO"],
  "tags": ["regional-grid-interruption"]
}
```

For historical imports only, add `historical: true` and `known_at` to events and quotes. These timestamps are curator assertions and require a trustworthy point-in-time source. The software validates chronology but cannot prove when an external publisher first made information public. Import historical events in chronological availability order: chain snapshots are immutable and do not rebuild themselves when older records arrive later. Synthetic quotes cannot be used for actual portfolio valuation.

Default paper limits: five independent examples, similarity ≥ 0.65, agreement ≥ 0.8, 50 basis-point edge plus assumed costs, 1,000 cash units per order, 20% long exposure, 10% drawdown, five daily orders, one-hour cooldown, five-minute quote age and one-hour event age. Policy validation caps order notional at 10,000, exposure at 50% and forbids fewer than three independent examples. These are demonstration settings, not calibrated financial risk advice.

## Honest limits and next gates

Implemented: database migration, generic ingestion, availability-aware relationship snapshots, pattern retrieval, fixed-horizon outcome labels, deterministic opt-in rule, idempotent audited simulation, API access control, browser workflow, fictional demo, and tests.

Not implemented: broad world-event collection, a verified global geopolitical knowledge graph, semantic multilingual entity/relation extraction, economically comparable regime classification, licensed exchange price ingestion, futures contracts/multipliers/rolls, FX conversion, shorting/margin, execution order books, partial fills, continuous stop-loss or liquidation, a background message queue, broker connections or real-money orders.

The current matcher is an in-memory prototype: candidate chain windows are capped at 500 events, connected chains at 50 events, and labeled comparison candidates at 10,000. The lead bridge caps each selected batch at 500 revisions and reports oversized batches explicitly. The dashboard displays only the latest 100 events/decisions. Multiple instruments require separate portfolio accounts; this version has one cash-only account. Generic countries and tags can create false associations. Price feeds are authenticated curator inputs, not externally verified market prices.

Before treating the rule as a strategy, collect licensed point-in-time event and price histories, evaluate on chronological held-out periods with purge/embargo for overlapping horizons, compare to cash and simple baselines, include realistic costs, and report failures, uncertainty, drawdown and regime stability. Chronological evaluation avoids training on future observations, as described in [scikit-learn's time-series split documentation](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html). A statistical validation/backtest report is still a required future gate; none is claimed here.

Live execution is a separate integration gate requiring a named broker, tradable instruments, capital limits, contract specifications, reconciliation, and approved validated policies. This branch contains no live execution path.

## Market charts and paper performance

Open **Patterns & paper trades** to view the embedded TradingView candlestick chart. Enter an exchange-qualified symbol (for example `NYSE:AA`, `NASDAQ:CENX` or `NASDAQ:AAPL`), select an interval, and press **Show chart**. The full-chart link opens TradingView separately. Internet access is required, and availability or delays depend on the market and provider.

Below it, stored-price charts show simulated BUY/SELL markers, portfolio returns and recorded fees. **Refresh paper data** reloads the ledger. `/api/research/performance` reconstructs cash and positions from immutable paper decisions and quotes available at each timestamp. Historical imports are excluded from valuation; delayed older observations cannot overwrite newer marks. Reports cover the current instrument segment and cap history at 10,000 quotes and 10,000 decisions.

TradingView is market context, not a price feed for the engine. Changing its symbol does not change the paper account. Only the public symbol and display settings are sent to the isolated provider frame; account balances, decisions and access tokens are not included. The application retains its own-script-only policy and permits only the provider frame host. No new migration or API key is needed.

Paper trades do not affect actual market prices. The local return comparison shows portfolio performance against the underlying stored-price change, which has different exposure and excludes costs; it does not establish causality. The fictional demo uses `ALUMINIUM_DEMO`, so its stored quotes are independent of the displayed Alcoa chart. Custom simulated-order markers appear on the local chart: the free embedded TradingView widget does not expose custom strategy execution, as explained in the [provider FAQ](https://www.tradingview.com/widget-docs/faq/general/).

## Event influence and evidence watchlist

The research page now ranks events with a versioned 0–100 **attention** score. Every event in the supported workspace receives a score; the UI displays the top 100. `/api/research/influence` returns the complete report, or accepts an ISO timezone-aware `as_of` parameter for replay. Events and outcomes must both have been known and recorded by that time, so historical backfills cannot leak into prior reports.

Version `event-attention-v1` uses explicit, uncalibrated heuristic weights: recency up to 20 points with seven-day exponential decay; unique same-instrument relationships up to 30 points (five per neighbour); absolute completed 24-hour price response up to 30 points (1000 times fractional return); and paper-decision attention up to 20 points. Each non-HOLD decision distributes a single 20-point budget across its chain, decays over seven days, and records the decision ID, anchor, reason and sample count. Multiple decisions can contribute but the component is capped at 20. There is no recursive propagation, automatic policy modification, or retrospective alteration of decisions.

Expand an event to inspect the component breakdown, observed outcome, relationship count, decision adjustments, source reference and evidence gaps. Fictional records are explicitly flagged. Current source references are curator assertions, not independent source-quality ratings. Price response is association; there is no counterfactual market-impact attribution. A high score is not a buy/sell direction, calibrated probability, or demonstrated predictive advantage. The score is read-only and is never fed into the execution rule. This separation prevents a simulated BUY from becoming its own corroborating market evidence.

The report is reconstructed from immutable event/decision/outcome records with a fixed model version; no migration is needed. Maximum workspace size is 1,000 events and 10,000 outcomes/decisions. Future gates include verified source corroboration, duplicate-story clustering, benchmark-adjusted response studies, chronological held-out score calibration, and monitoring of model drift. Those capabilities are not claimed as implemented.
