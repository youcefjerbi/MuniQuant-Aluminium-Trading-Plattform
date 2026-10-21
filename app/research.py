"""Experimental, deterministic event chains and a cash-only paper broker.

No broker SDK, live orders, external LLM, or assertion of predictive validity. Plants and the
ownership and operator links between them are read from the Data Core; an event stores Core plant
IDs, and a chain stores the Core links (fact and document IDs) it used.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_DOWN
from math import sqrt
import re
import unicodedata
from sqlalchemy import select, update
from .models import Audit, Lead, LeadRevision, uid, now
from .research_models import ResearchEvent, ResearchQuote, ResearchOutcome, PaperPolicy, PaperAccount, PaperDecision
from .research_schemas import PolicyIn, EventIn, KINDS
from .services import record

VERSION = 'event-chain-paper-0.1.0'
WINDOW = timedelta(hours=72)
HORIZON = timedelta(hours=24)
D = Decimal


class Conflict(ValueError):
    pass


def stamp(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return value.astimezone(timezone.utc)


def iso(value):
    return stamp(value).isoformat()


def required(s, model, identifier):
    value = s.get(model, identifier)
    if not value:
        raise LookupError('Record not found')
    return value


def audit(s, actor, action, obj, detail=None):
    s.add(Audit(actor=actor, action=action, record_id=obj.id, detail=detail or {'version': VERSION}))


def configure(s, data, actor):
    account = s.scalar(select(PaperAccount).where(PaperAccount.id == 'paper').with_for_update())
    if account and account.instrument != data.instrument and D(account.quantity) != 0:
        raise Conflict('Close the paper position before changing instruments')
    policy = PaperPolicy(id=uid(), settings=data.model_dump(mode='json'), actor=actor)
    s.add(policy); s.flush()
    if not account:
        account = PaperAccount(id='paper', policy_id=policy.id, instrument=data.instrument,
                               cash='100000', quantity='0', peak_equity='100000', version=0)
        s.add(account)
    else:
        changed = s.execute(update(PaperAccount).where(PaperAccount.id == account.id, PaperAccount.version == account.version)
                            .values(policy_id=policy.id, instrument=data.instrument, version=account.version + 1))
        if changed.rowcount != 1:
            raise Conflict('Account changed concurrently; retry')
    audit(s, actor, 'paper_policy', policy)
    s.commit()
    return record(policy)


def relations(a, b, linked_pairs):
    left, right = set(a['entity_ids']), set(b['entity_ids'])
    reasons = []
    if left & right:
        reasons.append('shared_entity')
    if any(frozenset((x, y)) in linked_pairs for x in left for y in right):
        reasons.append('registered_relationship')
    if set(a['tags']) & set(b['tags']):
        reasons.append('shared_tag')
    if set(a['countries']) & set(b['countries']) and a['kind'] != b['kind']:
        reasons.append('shared_country_cross_kind')
    return reasons


def build_chain(s, data, known, core):
    occurred = stamp(data['occurred_at'])
    candidates = s.scalars(select(ResearchEvent).where(
        ResearchEvent.instrument == data['instrument'], ResearchEvent.known_at <= known,
        ResearchEvent.occurred_at >= iso(occurred - WINDOW), ResearchEvent.occurred_at <= iso(occurred)
    ).order_by(ResearchEvent.occurred_at, ResearchEvent.id).limit(501)).all()
    if len(candidates) > 500:
        raise ValueError('More than 500 events in the chain window; partition the instrument stream')
    # Ownership/operator facts have no availability history suitable for replay;
    # only use relationships the Core had recorded by the anchor's availability time.
    day = data['occurred_at'][:10]
    links = {}
    for r in core.relationships():
        recorded = core.first_audited(r['id'])
        if recorded is not None and recorded <= known and r['valid_from'] <= day and (not r['valid_to'] or r['valid_to'] >= day):
            links.setdefault(frozenset((r['company_id'], r['facility_id'])), []).append(r)
    linked_pairs = set(links)
    selected = [{'id': data['id'], **data}]
    remaining = list(candidates)
    edges = []
    while remaining:
        added = False
        for candidate in list(remaining):
            payload = {**candidate.payload, 'id': candidate.id}
            connections = [(node, relations(payload, node, linked_pairs)) for node in selected]
            connections = [(node, why) for node, why in connections if why]
            if not connections:
                continue
            if len(selected) >= 50:
                raise ValueError('Chain exceeds 50 related events; narrow the stream')
            for node, why in connections:
                first, second = sorted((payload, node), key=lambda e: (e['occurred_at'], e['id']))
                edge = {'from': first['id'], 'to': second['id'], 'reasons': why, 'causal': False}
                if 'registered_relationship' in why:
                    # Versioned Core references: the link facts and their document versions.
                    used = {frozenset((x, y)) for x in payload['entity_ids'] for y in node['entity_ids']} & linked_pairs
                    edge['core_relationships'] = sorted(({'relationship_id': r['id'], 'company_id': r['company_id'], 'facility_id': r['facility_id'], 'document_id': r['document_id']}
                                                         for pair in used for r in links[pair]), key=lambda item: item['relationship_id'])
                edges.append(edge)
            selected.append(payload); remaining.remove(candidate); added = True
        if not added:
            break
    selected.sort(key=lambda e: (e['occurred_at'], e['id']))
    features = Counter()
    for node in selected:
        features['kind:' + node['kind']] += 3
        for tag in node['tags']:
            features['tag:' + tag] += 2
        for country in node['countries']:
            features['country:' + country] += 1
        for word in set(re.findall(r'\w+', unicodedata.normalize('NFKC', node['title'] + ' ' + node['summary']).casefold())):
            if len(word) > 2:
                features['word:' + word] += 1
    for left, right in zip(selected, selected[1:]):
        features['transition:' + left['kind'] + '>' + right['kind']] += 4
    return {'version': VERSION, 'window_hours': 72, 'event_ids': [e['id'] for e in selected],
            'sequence': [e['kind'] for e in selected], 'edges': edges}, dict(features)


def ingest_event(s, data, actor, core):
    payload = data.model_dump(mode='json')
    payload['occurred_at'] = iso(data.occurred_at)
    payload['known_at'] = iso(data.known_at) if data.known_at else now()
    existing = s.scalar(select(ResearchEvent).where(ResearchEvent.external_key == data.external_key))
    if existing:
        # Live retries cannot specify known_at; retain the original server arrival time.
        comparable = dict(payload)
        if data.known_at is None:
            comparable['known_at'] = existing.known_at
        if comparable != existing.payload:
            raise Conflict('external_key already exists with different content; use a revision key')
        decision = s.scalar(select(PaperDecision).where(PaperDecision.event_id == existing.id))
        return {'event': record(existing), 'decision': record(decision) if decision else None, 'duplicate': True}
    for identifier in data.entity_ids:
        if not core.entity(identifier):
            raise LookupError('Record not found')
    if data.lead_id:
        required(s, Lead, data.lead_id)
    identifier = uid()
    chain, features = build_chain(s, {**payload, 'id': identifier}, payload['known_at'], core)
    event = ResearchEvent(id=identifier, external_key=data.external_key, instrument=data.instrument, kind=data.kind,
                          occurred_at=payload['occurred_at'], known_at=payload['known_at'], historical=int(data.historical),
                          payload=payload, chain=chain, features=features)
    s.add(event); s.flush()
    audit(s, actor, 'research_event', event)
    decision = None
    account = s.get(PaperAccount, 'paper')
    if not data.historical and account and account.instrument == data.instrument:
        decision = evaluate(s, event, actor)
    s.commit()
    return {'event': record(event), 'decision': record(decision) if decision else None, 'duplicate': False}


def ingest_quote(s, data, actor):
    observed = iso(data.occurred_at)
    known = iso(data.known_at) if data.known_at else now()
    existing = s.scalar(select(ResearchQuote).where(ResearchQuote.external_key == data.external_key))
    if existing:
        if (existing.instrument != data.instrument or D(existing.price) != data.price or existing.observed_at != observed
                or existing.source_reference != data.source_reference or bool(existing.historical) != data.historical
                or (data.known_at is not None and existing.known_at != known)):
            raise Conflict('Quote key already exists with different content')
        return record(existing)
    quote = ResearchQuote(id=uid(), external_key=data.external_key, instrument=data.instrument, price=str(data.price),
                          observed_at=observed, known_at=known, historical=int(data.historical), source_reference=data.source_reference)
    s.add(quote); s.flush(); audit(s, actor, 'research_quote', quote); s.commit()
    return record(quote)


def label_outcome(s, data, actor):
    event = required(s, ResearchEvent, data.event_id)
    entry = required(s, ResearchQuote, data.entry_quote_id)
    exit = required(s, ResearchQuote, data.exit_quote_id)
    if not entry.instrument == exit.instrument == event.instrument:
        raise ValueError('Outcome quotes must use the event instrument')
    # One fixed horizon. Arbitrary hand-selected holding periods are not comparable.
    start = stamp(event.known_at)
    if not start <= stamp(entry.observed_at) <= start + timedelta(minutes=5):
        raise ValueError('Entry quote must be observed within 5 minutes after event availability')
    if not start + HORIZON <= stamp(exit.observed_at) <= start + HORIZON + timedelta(minutes=5):
        raise ValueError('Exit quote must be observed 24 hours after event availability (5 minute tolerance)')
    existing = s.scalar(select(ResearchOutcome).where(ResearchOutcome.event_id == event.id))
    if existing:
        if existing.entry_quote_id != entry.id or existing.exit_quote_id != exit.id:
            raise Conflict('Outcome is immutable')
        return record(existing)
    outcome = ResearchOutcome(id=uid(), event_id=event.id, entry_quote_id=entry.id, exit_quote_id=exit.id,
                             return_fraction=str(D(exit.price) / D(entry.price) - 1), available_at=max(entry.known_at, exit.known_at))
    s.add(outcome); s.flush(); audit(s, actor, 'research_outcome', outcome); s.commit()
    return record(outcome)


def cosine(a, b):
    dot = sum(value * b.get(key, 0) for key, value in a.items())
    denominator = sqrt(sum(v * v for v in a.values()) * sum(v * v for v in b.values()))
    return dot / denominator if denominator else 0.0


def analogues(s, event, policy):
    candidates = s.execute(select(ResearchEvent, ResearchOutcome).join(ResearchOutcome, ResearchOutcome.event_id == ResearchEvent.id).where(
        ResearchEvent.instrument == event.instrument, ResearchOutcome.available_at < event.known_at,
        ResearchEvent.known_at < iso(stamp(event.known_at) - WINDOW - HORIZON)
    ).limit(10001)).all()
    if len(candidates) > 10000:
        raise ValueError('Research corpus exceeds 10,000 labeled anchors; an indexed matcher is required')
    ranked = sorted(((cosine(event.features, old.features), old, outcome) for old, outcome in candidates),
                    key=lambda row: (-row[0], row[1].known_at, row[1].id))
    matches, used_events, intervals = [], set(event.chain['event_ids']), []
    for similarity, old, outcome in ranked:
        if old.kind != event.kind or similarity < policy.min_similarity:
            continue
        ids = set(old.chain['event_ids'])
        interval = (stamp(old.known_at) - WINDOW, stamp(old.known_at) + HORIZON)
        if ids & used_events or any(interval[0] <= end and interval[1] >= start for start, end in intervals):
            continue
        matches.append({'event_id': old.id, 'chain': old.chain, 'similarity': similarity,
                        'outcome_id': outcome.id, 'return_fraction': outcome.return_fraction, 'available_at': outcome.available_at})
        used_events.update(ids); intervals.append(interval)
        if len(matches) == 100:
            break
    weighted = sum(D(str(m['similarity'])) * D(m['return_fraction']) for m in matches)
    weights = sum((D(str(m['similarity'])) for m in matches), D(0))
    mean = weighted / weights if weights else D(0)
    direction = 1 if mean > 0 else -1
    agreement = sum(1 for m in matches if D(m['return_fraction']) * direction > 0) / len(matches) if matches else 0
    return {'version': VERSION, 'as_of': event.known_at, 'matches': matches, 'sample_count': len(matches),
            'weighted_return_fraction': str(mean), 'direction_agreement': agreement,
            'round_trip_cost_bps': 2 * (policy.fee_bps + policy.slippage_bps),
            'interpretation': 'Historical analogues; unvalidated experimental rule, not a forecast or causal conclusion'}


def latest_quote(s, instrument, as_of):
    return s.scalar(select(ResearchQuote).where(ResearchQuote.instrument == instrument, ResearchQuote.known_at <= as_of,
                    ResearchQuote.observed_at <= as_of, ResearchQuote.historical == 0)
                    .order_by(ResearchQuote.observed_at.desc(), ResearchQuote.known_at.desc(), ResearchQuote.id).limit(1))


def evaluate(s, event, actor):
    existing = s.scalar(select(PaperDecision).where(PaperDecision.event_id == event.id))
    if existing:
        return existing
    account = s.scalar(select(PaperAccount).where(PaperAccount.id == 'paper').with_for_update())
    if not account:
        raise ValueError('Configure the paper account first')
    policy_row = required(s, PaperPolicy, account.policy_id)
    policy = PolicyIn(**policy_row.settings)
    details = analogues(s, event, policy)
    clock = now()
    quote = latest_quote(s, event.instrument, clock)
    cash, quantity, peak = D(account.cash), D(account.quantity), D(account.peak_equity)
    action, reason = 'HOLD', 'Insufficient independent historical analogues'
    mean = D(details['weighted_return_fraction'])
    edge = D(policy.edge_threshold_bps + details['round_trip_cost_bps']) / 10000
    if details['sample_count'] >= policy.min_cases and details['direction_agreement'] >= policy.min_agreement:
        if mean > edge:
            action, reason = 'BUY', 'Positive historical analogue rule after assumed costs'
        elif mean < -edge:
            action, reason = 'SELL', 'Negative historical analogue rule after assumed costs'
        else:
            reason = 'Historical effect does not exceed the configured threshold and costs'
    if not policy.enabled:
        action, reason = 'HOLD', 'Paper automation is paused'
    elif event.historical:
        action, reason = 'HOLD', 'Historical imports cannot trigger orders'
    elif account.instrument != event.instrument:
        action, reason = 'HOLD', 'Instrument is outside the configured paper account'
    elif (stamp(clock) - stamp(event.occurred_at)).total_seconds() > policy.max_event_age_seconds:
        action, reason = 'HOLD', 'Incoming event is stale'
    elif not quote or (stamp(clock) - stamp(quote.observed_at)).total_seconds() > policy.max_quote_age_seconds:
        action, reason = 'HOLD', 'Missing or stale nonhistorical price quote'
    equity = cash + quantity * D(quote.price) if quote else cash
    if quote:
        peak = max(peak, equity)
        if equity < peak * (1 - policy.max_drawdown_fraction):
            action, reason = 'HOLD', 'Drawdown limit reached; automation blocked'
    recent = s.scalars(select(PaperDecision).where(PaperDecision.action != 'HOLD').order_by(PaperDecision.created_at.desc()).limit(100)).all()
    if recent and (stamp(clock) - stamp(recent[0].created_at)).total_seconds() < policy.cooldown_seconds:
        action, reason = 'HOLD', 'Paper order cooldown is active'
    if sum(d.created_at[:10] == clock[:10] for d in recent) >= policy.max_daily_trades:
        action, reason = 'HOLD', 'Daily paper order limit reached'
    fill = None
    if action == 'BUY':
        price = D(quote.price) * (1 + D(policy.slippage_bps) / 10000)
        budget = min(policy.max_trade_notional, cash / (1 + D(policy.fee_bps) / 10000),
                     max(D(0), equity * policy.max_exposure_fraction - quantity * price))
        units = (budget / price).quantize(D('0.00000001'), rounding=ROUND_DOWN)
        notional = units * price
        fee = notional * D(policy.fee_bps) / 10000
        if units <= 0:
            action, reason = 'HOLD', 'Cash or position exposure limit prevents purchase'
        else:
            cash -= notional + fee; quantity += units
            fill = {'quantity': str(units), 'price': str(price), 'fee': str(fee), 'notional': str(notional), 'mode': 'paper'}
    elif action == 'SELL':
        price = D(quote.price) * (1 - D(policy.slippage_bps) / 10000)
        units = min(quantity, (policy.max_trade_notional / price).quantize(D('0.00000001'), rounding=ROUND_DOWN))
        if units <= 0:
            action, reason = 'HOLD', 'No long paper position to reduce; short selling is disabled'
        else:
            notional = units * price; fee = notional * D(policy.fee_bps) / 10000
            cash += notional - fee; quantity -= units
            fill = {'quantity': str(units), 'price': str(price), 'fee': str(fee), 'notional': str(notional), 'mode': 'paper'}
    details.update({'fill': fill, 'cash_after': str(cash), 'quantity_after': str(quantity), 'equity_before': str(equity),
                    'chain_snapshot': event.chain, 'policy_snapshot': policy_row.settings, 'mode': 'paper'})
    decision = PaperDecision(id=uid(), event_id=event.id, policy_id=policy_row.id, quote_id=quote.id if quote else None,
                             action=action, reason=reason, details=details, actor=actor, created_at=clock)
    # CAS plus row locks serialize decisions and policy changes across workers.
    changed = s.execute(update(PaperAccount).where(PaperAccount.id == account.id, PaperAccount.version == account.version)
                        .values(cash=str(cash), quantity=str(quantity), peak_equity=str(peak), version=account.version + 1))
    if changed.rowcount != 1:
        raise Conflict('Paper account changed concurrently; retry the event')
    s.add(decision); audit(s, actor, 'paper_decision', decision)
    return decision


def dashboard(s):
    account = s.get(PaperAccount, 'paper')
    policy = required(s, PaperPolicy, account.policy_id) if account else None
    return {'mode': 'paper', 'version': VERSION, 'live_trading_available': False,
            'account': record(account) if account else None, 'policy': record(policy) if policy else None,
            'events': [record(e) for e in s.scalars(select(ResearchEvent).order_by(ResearchEvent.known_at.desc(), ResearchEvent.id).limit(100))],
            'decisions': [record(d) for d in s.scalars(select(PaperDecision).order_by(PaperDecision.created_at.desc()).limit(100))],
            'quotes': [record(q) for q in s.scalars(select(ResearchQuote).order_by(ResearchQuote.known_at.desc()).limit(20))],
            'event_kinds': list(KINDS)}


def import_leads(s, actor, core, document_ids=None, live=False):
    """Bridge factual vendor revisions, using revision availability, never vendor analytics."""
    imported = []
    query = select(Lead).join(LeadRevision, (LeadRevision.lead_id == Lead.id) & (LeadRevision.content_hash == Lead.current_revision_hash))
    if document_ids is not None:
        query = query.where(LeadRevision.document_id.in_(document_ids))
    leads = s.scalars(query.order_by(Lead.id).limit(501)).all()
    if len(leads) > 500:
        raise ValueError('Lead bridge batch exceeds 500 revisions; a paginated worker is required')
    for lead in leads:
        revision = s.scalar(select(LeadRevision).where(LeadRevision.lead_id == lead.id,
                                                    LeadRevision.content_hash == lead.current_revision_hash))
        if not revision or (document_ids is not None and revision.document_id not in document_ids):
            continue
        when = revision.event_date or revision.recorded_at
        if datetime.fromisoformat(when).tzinfo is None:
            when += '+00:00'
        title = revision.event_name
        raw = (title + ' ' + revision.summary).casefold()
        kind = next((kind for kind, words in [('sanction', ['sanction', 'embargo']), ('conflict', ['war', 'attack']),
                    ('energy', ['power', 'electricity']), ('logistics', ['port', 'shipping']), ('weather', ['flood', 'storm']),
                    ('corporate', ['acquisition', 'ownership']), ('supply', ['curtail', 'outage', 'restart'])]
                     if any(re.search(r'\b' + re.escape(word) + r'\w*\b', raw) for word in words)), 'other')
        result = ingest_event(s, EventIn(external_key='lead:' + lead.id + ':' + revision.content_hash,
            kind=kind, occurred_at=when, known_at=None if live else max(iso(when), iso(revision.recorded_at)), historical=not live,
            title=title, summary=revision.summary, source_reference='document:' + revision.document_id,
            entity_ids=revision.matched_entity_ids, tags=[lead.ticker.casefold(), (lead.topic_name or 'unclassified')[:100]], lead_id=lead.id), actor, core)
        if not result['duplicate']:
            imported.append(result['event']['id'])
    return {'imported': imported, 'mode': 'incoming' if live else 'historical',
            'note': 'Classifications are heuristic; only incoming events may trigger paper decisions'}
