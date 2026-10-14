"""Versioned, non-recursive attention scoring; never an execution input."""
from datetime import datetime, timezone
from math import exp, floor
from sqlalchemy import select
from .research_models import ResearchEvent, ResearchOutcome, PaperDecision
from .research import factual_event_predicate

VERSION = 'event-attention-v1'


def report(s, as_of=None):
    clock = datetime.fromisoformat(as_of.replace('Z', '+00:00')) if as_of else datetime.now(timezone.utc)
    if clock.tzinfo is None:
        raise ValueError('as_of must include a timezone')
    clock = clock.astimezone(timezone.utc)
    if clock > datetime.now(timezone.utc):
        raise ValueError('as_of cannot be in the future')
    stamp = clock.isoformat()
    events = s.scalars(select(ResearchEvent).where(factual_event_predicate(), ResearchEvent.known_at <= stamp, ResearchEvent.recorded_at <= stamp)
                       .order_by(ResearchEvent.known_at.desc(), ResearchEvent.id).limit(1001)).all()
    if len(events) > 1000:
        raise ValueError('Influence reporting exceeds 1,000 events; partition the research workspace')
    by_id = {e.id: e for e in events}
    contributions = {e.id: [] for e in events}
    links = {e.id: set() for e in events}
    for anchor in events:
        for edge in anchor.chain.get('edges', []):
            a, b = edge['from'], edge['to']
            if a in by_id and b in by_id and a != b and by_id[a].instrument == by_id[b].instrument:
                links[a].add(b); links[b].add(a)
    outcomes = s.scalars(select(ResearchOutcome).where(ResearchOutcome.available_at <= stamp, ResearchOutcome.recorded_at <= stamp).limit(10001)).all()
    outcome_by_id = {o.event_id: o for o in outcomes if o.event_id in by_id}
    decisions = s.scalars(select(PaperDecision).where(PaperDecision.created_at <= stamp).limit(10001)).all()
    if len(outcomes) > 10000 or len(decisions) > 10000:
        raise ValueError('Influence reporting exceeds 10,000 outcomes or decisions; an indexed worker is required')
    for d in decisions:
        anchor = by_id.get(d.event_id)
        if not anchor or d.action == 'HOLD':
            continue
        # One bounded allocation per immutable decision; no score feeds another score.
        recipients = sorted({i for i in anchor.chain['event_ids'] if i in by_id and by_id[i].instrument == anchor.instrument})
        if not recipients:
            continue
        age = max(0, (clock - datetime.fromisoformat(d.created_at)).total_seconds()) / 86400
        allocation = 20 * exp(-age / 7) / len(recipients)
        for identifier in recipients:
            contributions[identifier].append({'decision_id': d.id, 'anchor_event_id': anchor.id,
                'at': d.created_at, 'action': d.action, 'points': floor(allocation * 1000000) / 1000000,
                'reason': d.reason, 'sample_count': d.details.get('sample_count', 0),
                'interpretation': 'Paper decision attention allocation, not proof of market influence'})
    rows = []
    for e in events:
        age = max(0, (clock - datetime.fromisoformat(e.known_at)).total_seconds()) / 86400
        freshness = 20 * exp(-age / 7)
        connected = min(30, 5 * len(links[e.id]))
        outcome = outcome_by_id.get(e.id)
        observed = min(30, abs(float(outcome.return_fraction)) * 1000) if outcome else 0
        decision = min(20, sum(c['points'] for c in contributions[e.id]))
        synthetic = e.payload.get('source_reference', '').startswith('synthetic:')
        rows.append({'event_id': e.id, 'title': e.payload['title'], 'kind': e.kind, 'instrument': e.instrument,
            'known_at': e.known_at, 'historical': bool(e.historical), 'synthetic': synthetic,
            'source_reference': e.payload.get('source_reference'), 'score': round(freshness + connected + observed + decision, 2),
            'components': {'freshness': round(freshness, 2), 'relationship_context': connected,
                           'observed_price_response': round(observed, 2), 'paper_decision_attention': round(decision, 2)},
            'related_event_ids': sorted(links[e.id]), 'decision_adjustments': contributions[e.id],
            'outcome': {'id': outcome.id, 'return_fraction': outcome.return_fraction,
                        'available_at': outcome.available_at, 'entry_quote_id': outcome.entry_quote_id,
                        'exit_quote_id': outcome.exit_quote_id} if outcome else None,
            'evidence_gaps': ['Source reference is curator asserted; independent verification is not measured'] +
                (['Fictional synthetic data'] if synthetic else []) +
                ([] if outcome else ['No completed price-response window'])})
    rows.sort(key=lambda row: (-row['score'], row['event_id']))
    return {'version': VERSION, 'as_of': stamp, 'events': rows,
            'meaning': '0–100 research attention score, not causal influence, forecast confidence or trading direction',
            'formula': 'Freshness 20 (7-day exponential decay) + unique relationships 30 (5 each) + absolute observed 24h return 30 (1000 × fraction) + paper decision allocation 20 (shared across chain, 7-day decay)',
            'execution_effect': 'Read-only; never changes historical evidence, paper decisions or trading policy'}
