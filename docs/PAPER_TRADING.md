# Charts and paper trading

Added at the user's request on 3 October 2026. This extends the original data-only scope with an isolated, simulated trading workspace. No broker is connected and no real orders can be placed.

## Use it

Open **Charts & trading**. The default watchlist contains AA, CENX, SPY and QQQ. Ticker/company names identify the examples; every price and volume is fictional. Choose candlesticks or closing-price charts and 20, 60 or all available sessions. Hover the chart, or focus it and use the left/right arrow keys, to inspect OHLC and volume.

Use **Workspace access** with the server's write token. Choose **Trade stock**, **Trade call** or **Trade put**, select side/type/quantity, inspect the estimated debit/proceeds, and submit the simulated order. Options quantities are contracts; premiums are quoted per share and each contract has multiplier 100.

The shared account starts with USD 100,000. Cash, orders, pending reservations and positions survive restarts. All authorized curators share one account; this is not a per-user brokerage account. The initial replay has 61 observed sessions and 59 remaining sessions. Advance one session to reveal the next generated close and evaluate open limits. This does not query a live feed. The session calendar skips weekends but is not an exchange-holiday calendar.

## Execution and accounting rules

- Stock buys and sales of owned shares; option buys and sales of owned contracts only. No shorts, margin, uncovered option writing, multi-leg orders or real-money execution.
- Market orders fill at the current simulated closing quote. Limits fill at that close when the buy price is at/below the limit or the sell price is at/above the limit. Pending limits are reconsidered at the next replay close, not intraday highs/lows.
- Open buy limits reserve quantity × limit × multiplier in cash. Open sells reserve owned units. Cancellation releases the reservation.
- Fees, spreads, slippage and liquidity limits are zero/absent. Displayed results are simulator results, not evidence of executable performance.
- Cash and fill prices use integer cents. Realized P/L uses average cost with half-up cent rounding for partial disposals. Portfolio equity equals cash plus positions marked at simulated quotes.
- Mutations use an optimistic account version check. Conflicting requests must refresh and retry. Client order UUIDs prevent accidental duplicate submission; conflicting reuse is rejected.
- Advancing requires the displayed session cursor. Retrying a stale advance cannot silently advance twice.
- The six synthetic option contracts per underlying cover calls/puts at three strikes and a common expiry. The toy premium is intrinsic value plus a declining artificial time-value component. It is not a calibrated pricing model; no Greeks or implied-volatility estimates are represented.
- At the final replay session, outstanding option orders expire and owned options are automatically cash-settled at intrinsic value (zero for out-of-the-money positions). This is an explicit simulator convention, not the exercise/assignment rules of actual equity options. Stock positions remain open.

## Architecture boundary

`app/trading.py` owns a deterministic versioned dataset, quotes, routes and paper accounting. `paper_accounts` and `paper_orders` are separate from evidence-domain records. The industrial `CommodityEvidencePackage` does not include paper balances or orders. Paper mutations do append ordinary audit events. Database migration creates the initial shared account; no request silently seeds it.

Endpoints: `GET /api/paper/workspace`, `GET /api/paper/history/{instrument}`, `POST /api/paper/orders`, `POST /api/paper/orders/{id}/cancel`, `POST /api/paper/advance`.

## Future improvements

Real licensed stock/option market data, per-user accounts, configurable fees/slippage, additional expiries, Greeks, strategy views and an explicit replay-reset workflow can be added separately. A real broker integration is not included or authorized by the paper-trading feature.
