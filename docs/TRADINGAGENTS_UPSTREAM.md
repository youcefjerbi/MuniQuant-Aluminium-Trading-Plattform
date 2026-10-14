# TradingAgents evidence adapter

Uses the genuine TauricResearch/TradingAgents package, Apache-2.0, version 0.6.0,
pinned to commit `1394a3f72aa4393e1a98f51b382434c4b4c2d972`.
Upstream: https://github.com/TauricResearch/TradingAgents
License: https://github.com/TauricResearch/TradingAgents/blob/1394a3f72aa4393e1a98f51b382434c4b4c2d972/LICENSE
The adapter links to upstream agent implementations; it does not modify or copy their source.

The worker composes upstream bull/bear researchers, research manager, trader,
three risk debaters and portfolio manager with their own state and routing.
It injects only authorized Core evidence, stored quotes and simulated portfolio.
The fixed vendor analysts, high-level TradingAgentsGraph wrapper, ticker resolver,
memory settlement, checkpoints and filesystem reports are excluded. No data tools
are attached. Evidence/source text and instrument mapping remain untrusted data.

Worker imports disable dotenv loading and telemetry configuration. Server models
and provider credentials are explicit; OpenAI and local Ollama are supported.
Only the exact typed upstream PortfolioDecision rating maps to a PAPER proposal;
free-text fallback cannot authorize an action. Evidence citations are mandatory
and their IDs are checked. Identifier checks do not prove factual entailment;
the application must apply evidence, freshness and deterministic paper-policy guards.
Raw Core records remain transient model context; the returned evidence report
contains only package version, build fingerprint and citation identifiers. It
must not become a shadow Core fact store. The adapter never writes a database,
places an order, or executes a paper trade.

One round costs eight normal model calls; the three structured agents may each
make one free-text fallback. Provider retries are zero, request timeout at most
30 seconds, model output at most 1600 tokens, graph recursion limit 20. Parent
process controls total timeout and cancellation, terminates the worker, preserves
versioned run evidence and authenticates paid requests. Missing dependencies or
unparseable results produce a sanitized error without provider logs or details.

Tests execute actual pinned upstream factories with fake models and blocked sockets.
They cover typed rating mapping, unsupported free-text decisions, citation rejection,
provider limits, input requirements and worker error sanitization. These tests do
not establish profitability or live-provider behavior.
