"""Reconstruct simulated portfolio marks from the immutable local ledger.

TradingView prices are not imported or used to value the paper account.
"""
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select
from .research_models import PaperAccount, PaperPolicy, PaperDecision, ResearchQuote

D = Decimal


def performance(s):
    account = s.get(PaperAccount, 'paper')
    if not account:
        return {'instrument': None, 'points': [], 'trades': [], 'summary': None, 'mode': 'paper'}
    decisions = s.scalars(select(PaperDecision).order_by(PaperDecision.created_at, PaperDecision.id).limit(10001)).all()
    quotes = s.scalars(select(ResearchQuote).where(ResearchQuote.instrument == account.instrument,
                    ResearchQuote.historical == 0).order_by(ResearchQuote.known_at, ResearchQuote.id).limit(10001)).all()
    if len(decisions) > 10000 or len(quotes) > 10000:
        raise ValueError('Performance history exceeds 10,000 rows; an indexed reporting worker is required')
    last_other = max((i for i, d in enumerate(decisions) if d.details['policy_snapshot']['instrument'] != account.instrument), default=-1)
    decisions = decisions[last_other + 1:]
    # Report the current instrument segment; a flat-account instrument switch may
    # carry previous realized cash into the next segment, which is its baseline.
    if decisions:
        start = decisions[0].created_at
        first = decisions[0]
        cash, quantity = D(first.details['cash_after']), D(first.details['quantity_after'])
        fill = first.details.get('fill')
        if fill:
            units, notional, fee = D(fill['quantity']), D(fill['notional']), D(fill['fee'])
            if first.action == 'BUY':
                cash += notional + fee; quantity -= units
            else:
                cash -= notional - fee; quantity += units
    else:
        start = s.get(PaperPolicy, account.policy_id).created_at
        cash, quantity = D(account.cash), D(account.quantity)
    latest = None
    points, trades = [], []
    baseline, baseline_price = None, None

    def accept_quote(quote):
        nonlocal latest
        if latest is None or (quote.observed_at, quote.known_at, quote.id) > (latest.observed_at, latest.known_at, latest.id):
            latest = quote

    def point(at, trade=None):
        nonlocal baseline, baseline_price
        price = D(latest.price) if latest else None
        equity = cash + quantity * price if price is not None else cash if quantity == 0 else None
        if baseline is None and equity is not None:
            baseline = equity
        if baseline_price is None and price is not None:
            baseline_price = price
        points.append({'at': at, 'quote_id': latest.id if latest else None, 'price': str(price) if price is not None else None,
                       'quote_observed_at': latest.observed_at if latest else None,
                       'cash': str(cash), 'quantity': str(quantity), 'equity': str(equity) if equity is not None else None,
                       'paper_return_percent': str((equity / baseline - 1) * 100) if equity is not None and baseline else None,
                       'market_return_percent': str((price / baseline_price - 1) * 100) if price is not None and baseline_price else None,
                       'trade_id': trade.id if trade else None})

    if start:
        for quote in quotes:
            if quote.known_at <= start:
                accept_quote(quote)
        point(start)
        timeline = [(q.known_at, 0, q.id, q) for q in quotes if q.known_at > start]
        timeline += [(d.created_at, 1, d.id, d) for d in decisions]
        for at, kind, _, item in sorted(timeline, key=lambda row: row[:3]):
            if kind == 0:
                accept_quote(item)
                point(at)
            else:
                cash, quantity = D(item.details['cash_after']), D(item.details['quantity_after'])
                fill = item.details.get('fill')
                if fill:
                    trades.append({'id': item.id, 'at': at, 'action': item.action, 'event_id': item.event_id,
                                   'price': fill['price'], 'quantity': fill['quantity'], 'fee': fill['fee'], 'reason': item.reason})
                    point(at, item)
    last = points[-1] if points else None
    quote_age = (datetime.now(timezone.utc) - datetime.fromisoformat(latest.observed_at)).total_seconds() if latest else None
    summary = {'baseline_equity': str(baseline) if baseline is not None else None,
               'equity': last['equity'] if last else str(cash) if quantity == 0 else None,
               'pnl': str(D(last['equity']) - baseline) if last and last['equity'] is not None and baseline is not None else None,
               'paper_return_percent': last['paper_return_percent'] if last else None,
               'market_return_percent': last['market_return_percent'] if last else None,
               'fees': str(sum((D(t['fee']) for t in trades), D(0))), 'trade_count': len(trades),
               'latest_quote_observed_at': latest.observed_at if latest else None,
               'quote_age_seconds': max(0, quote_age) if quote_age is not None else None,
               'valuation_basis': 'Latest stored nonhistorical quote; not a live TradingView price',
               'benchmark': 'Underlying price change since the first report mark; excludes costs and differs in exposure'}
    return {'instrument': account.instrument, 'points': points, 'trades': trades, 'summary': summary, 'mode': 'paper'}
