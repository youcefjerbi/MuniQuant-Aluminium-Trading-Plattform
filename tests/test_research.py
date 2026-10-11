from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
import pytest
from app import research
from app.research_demo import populate
from app.research_models import ResearchEvent, ResearchQuote, ResearchOutcome, PaperAccount, PaperDecision
from app.research_schemas import PolicyIn


def clock():
    return datetime.now(timezone.utc)


def event_body(key='incoming', **extra):
    return {'external_key': key, 'kind': 'supply', 'occurred_at': clock().isoformat(),
            'title': 'Fictional smelter outage reduces aluminium supply', 'summary': 'Fictional demonstration only',
            'tags': ['fictional-demo', 'aluminium'], 'countries': ['NO'], 'source_reference': 'synthetic:test', **extra}


def demo(client):
    with Session(client.app.state.engine) as s:
        return populate(s)


def test_full_demo_builds_chain_matches_and_automatic_fill(client):
    result = demo(client)
    decision = result['decision']
    assert result['event']['chain']['sequence'] == ['sanction', 'energy', 'supply']
    assert all(not e['causal'] for e in result['event']['chain']['edges'])
    assert decision['action'] == 'BUY'
    assert decision['details']['sample_count'] == 5
    assert Decimal(decision['details']['fill']['notional']) <= 1000
    assert Decimal(decision['details']['fill']['fee']) > 0
    workspace = client.get('/api/research').json()
    assert workspace['live_trading_available'] is False
    assert Decimal(workspace['account']['quantity']) > 0
    assert Decimal(workspace['account']['cash']) < 100000
    assert len(workspace['decisions']) == 3
    assert decision['details']['policy_snapshot']['enabled']
    assert client.get('/api/research/events/' + result['event']['id'] + '/analogues').json()['sample_count'] == 5
    with Session(client.app.state.engine) as s:
        with pytest.raises(ValueError, match='empty'):
            populate(s)


def test_mutations_require_authorization(client):
    client.headers.pop('Authorization')
    assert client.post('/api/research/events', json=event_body()).status_code == 401
    assert client.post('/api/research/policy', json={}).status_code == 401
    assert client.post('/api/research/quotes', json={'external_key':'q','price':'100','occurred_at':clock().isoformat(),'source_reference':'test'}).status_code == 401
    assert client.post('/api/research/import-leads').status_code == 401


def test_idempotency_and_immutable_events(client):
    client.post('/api/research/policy', json={})
    body = event_body()
    first = client.post('/api/research/events', json=body)
    assert first.status_code == 201
    second = client.post('/api/research/events', json=body).json()
    assert second['duplicate'] and second['event']['id'] == first.json()['event']['id']
    assert second['decision']['id'] == first.json()['decision']['id']
    assert client.post('/api/research/events', json={**body,'summary':'changed'}).status_code == 409
    assert len(client.get('/api/research').json()['decisions']) == 1


@pytest.mark.parametrize('extra', [
    {'occurred_at':'2025-01-01T00:00:00'},
    {'occurred_at':(clock()+timedelta(days=1)).isoformat()},
    {'known_at':(clock()-timedelta(days=1)).isoformat()},
    {'kind':'bullish'}, {'countries':['NOR']}, {'tags':['x'*101]}, {'entity_ids':['missing']},
])
def test_invalid_event_inputs(client, extra):
    assert client.post('/api/research/events', json=event_body(**extra)).status_code in (422,404)


def test_historical_import_never_orders_and_paused_policy_holds(client):
    client.post('/api/research/policy',json={'enabled':True})
    old=(clock()-timedelta(days=10)).isoformat()
    r=client.post('/api/research/events',json=event_body('historical',occurred_at=old,known_at=old,historical=True)).json()
    assert r['decision'] is None
    client.post('/api/research/policy',json={'enabled':False})
    r=client.post('/api/research/events',json=event_body()).json()
    assert r['decision']['action']=='HOLD' and 'paused' in r['decision']['reason']


def test_missing_quotes_and_no_matching_cases_hold(client):
    client.post('/api/research/policy',json={'enabled':True})
    r=client.post('/api/research/events',json=event_body()).json()
    assert r['decision']['action']=='HOLD' and 'quote' in r['decision']['reason']


def test_duplicate_new_event_cannot_double_fill_and_cooldown_blocks(client):
    demo(client)
    body=event_body()
    r=client.post('/api/research/events',json=body).json()
    assert r['decision']['action']=='HOLD' and 'cooldown' in r['decision']['reason']
    before=client.get('/api/research').json()['account']
    client.post('/api/research/events',json=body)
    assert client.get('/api/research').json()['account']==before


def test_outcomes_are_fixed_horizon_and_immutable(client):
    result=demo(client)
    with Session(client.app.state.engine) as s:
        outcome=s.scalar(select(ResearchOutcome))
        payload={'event_id':outcome.event_id,'entry_quote_id':outcome.entry_quote_id,'exit_quote_id':outcome.exit_quote_id}
    assert client.post('/api/research/outcomes',json=payload).status_code==201
    assert client.post('/api/research/outcomes',json={**payload,'exit_quote_id':payload['entry_quote_id']}).status_code==422
    assert client.post('/api/research/outcomes',json={**payload,'event_id':result['event']['id']}).status_code==422


def test_future_outcomes_and_overlapping_cases_are_excluded(client):
    result=demo(client)
    with Session(client.app.state.engine) as s:
        current=s.get(ResearchEvent,result['event']['id'])
        outcomes=s.scalars(select(ResearchOutcome)).all()
        outcomes[0].available_at=research.iso(clock()+timedelta(days=1))
        s.commit()
        assert research.analogues(s,current,PolicyIn())['sample_count']==4
        # Duplicate chain snapshots cannot inflate the independent example count.
        old=s.get(ResearchEvent,outcomes[1].event_id)
        another=s.get(ResearchEvent,outcomes[2].event_id)
        another.chain=old.chain
        s.commit()
        assert research.analogues(s,current,PolicyIn())['sample_count']==3


def test_chain_excludes_unavailable_future_and_unrelated_events(client):
    old=clock()-timedelta(days=1)
    future=clock()-timedelta(hours=1)
    client.post('/api/research/events',json=event_body('hidden',kind='sanction',occurred_at=old.isoformat(),known_at=future.isoformat(),historical=True))
    client.post('/api/research/events',json=event_body('unrelated',kind='energy',occurred_at=old.isoformat(),known_at=old.isoformat(),historical=True,tags=['different'],countries=['BR']))
    anchor=old+timedelta(minutes=5)
    r=client.post('/api/research/events',json=event_body('anchor',occurred_at=anchor.isoformat(),known_at=anchor.isoformat(),historical=True)).json()
    assert r['event']['chain']['sequence']==['supply']


def test_negative_analogues_reduce_position_not_short(client):
    demo(client)
    with Session(client.app.state.engine) as s:
        for row in s.scalars(select(ResearchOutcome)):
            row.return_fraction='-0.04'
        for row in s.scalars(select(PaperDecision)):
            row.created_at=research.iso(clock()-timedelta(hours=2))
        s.commit()
    r=client.post('/api/research/events',json=event_body('sell')).json()
    assert r['decision']['action']=='SELL'
    assert Decimal(r['decision']['details']['quantity_after'])>=0
    with Session(client.app.state.engine) as s:
        account=s.get(PaperAccount,'paper'); account.quantity='0'
        for row in s.scalars(select(PaperDecision)):
            row.created_at=research.iso(clock()-timedelta(hours=2))
        s.commit()
    r=client.post('/api/research/events',json=event_body('no-short')).json()
    assert r['decision']['action']=='HOLD' and 'short' in r['decision']['reason']


def test_stale_price_and_event_drawdown_exposure_and_daily_limits(client):
    demo(client)
    with Session(client.app.state.engine) as s:
        for row in s.scalars(select(PaperDecision)):
            row.created_at=research.iso(clock()-timedelta(hours=2))
        quote=s.scalar(select(ResearchQuote).where(ResearchQuote.historical==0))
        quote.observed_at=research.iso(clock()-timedelta(hours=1));s.commit()
    r=client.post('/api/research/events',json=event_body('stale-price')).json()
    assert r['decision']['action']=='HOLD' and 'stale' in r['decision']['reason']
    with Session(client.app.state.engine) as s:
        quote=s.scalar(select(ResearchQuote).where(ResearchQuote.historical==0));quote.observed_at=research.iso(clock());s.commit()
    r=client.post('/api/research/events',json=event_body('stale-event',occurred_at=research.iso(clock()-timedelta(hours=2)))).json()
    assert 'stale' in r['decision']['reason']
    with Session(client.app.state.engine) as s:
        account=s.get(PaperAccount,'paper');account.peak_equity='200000';s.commit()
    r=client.post('/api/research/events',json=event_body('drawdown')).json()
    assert 'Drawdown' in r['decision']['reason'] and not r['decision']['details']['fill']
    with Session(client.app.state.engine) as s:
        account=s.get(PaperAccount,'paper');account.peak_equity='100000';account.quantity='250';account.cash='75000';s.commit()
    r=client.post('/api/research/events',json=event_body('exposure')).json()
    assert 'exposure' in r['decision']['reason']
    client.post('/api/research/policy',json={'enabled':True,'max_daily_trades':1})
    r=client.post('/api/research/events',json=event_body('daily')).json()
    assert 'Daily' in r['decision']['reason']


def test_policy_limits_and_instrument_switch_with_position(client):
    assert client.post('/api/research/policy',json={'min_cases':1}).status_code==422
    assert client.post('/api/research/policy',json={'max_trade_notional':100000}).status_code==422
    demo(client)
    assert client.post('/api/research/policy',json={'instrument':'OTHER'}).status_code==409
