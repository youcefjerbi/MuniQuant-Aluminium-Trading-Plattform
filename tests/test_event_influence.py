from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.research_demo import populate
from app.research_models import ResearchEvent, PaperDecision
from app.event_influence import report


def test_decision_attention_is_shared_bounded_and_does_not_mutate_ledger(client):
    with Session(client.app.state.engine) as s:
        populate(s)
        decision = s.query(PaperDecision).filter_by(action='BUY').one()
        original = dict(decision.details)
        result = report(s)
        allocations = [c for e in result['events'] for c in e['decision_adjustments']]
        assert len(allocations) == 3
        assert 19.9 < sum(c['points'] for c in allocations) <= 20
        assert len({c['decision_id'] for c in allocations}) == 1
        assert all(0 <= e['score'] <= 100 for e in result['events'])
        assert all(e['synthetic'] for e in result['events'])
        assert decision.details == original
        assert all(c['action'] != 'HOLD' for c in allocations)
        scored = {e['event_id']: e for e in result['events']}
        for identifier in decision.details['matches'][0]['chain']['event_ids']:
            assert not scored[identifier]['decision_adjustments']


def test_replay_excludes_backfilled_and_future_records_and_invalid_clock(client):
    with Session(client.app.state.engine) as s:
        populate(s)
        past = datetime.now(timezone.utc) - timedelta(days=1)
        assert report(s, past.isoformat())['events'] == [] # historical imports recorded today
    assert client.get('/api/research/influence', params={'as_of':'bad'}).status_code == 422
    assert client.get('/api/research/influence', params={'as_of':'2020-01-01T00:00:00'}).status_code == 422
    future = datetime.now(timezone.utc) + timedelta(days=1)
    assert client.get('/api/research/influence', params={'as_of':future.isoformat()}).status_code == 422


def test_outcome_component_is_observed_not_directional_prediction(client):
    with Session(client.app.state.engine) as s: populate(s)
    result = client.get('/api/research/influence').json()
    assert result['version'] == 'event-attention-v1'
    historical = [e for e in result['events'] if e['outcome']]
    assert len(historical) == 5
    assert all(e['components']['observed_price_response'] == 30 for e in historical)
    assert all('Fictional synthetic data' in e['evidence_gaps'] for e in historical)
