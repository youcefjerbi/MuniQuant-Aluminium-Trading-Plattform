# Copyright 2026 muniQuant. Licensed under the Apache License, Version 2.0.
"""The practice bot (app/game_bridge.py) against a fake game server: no network and no Data Core."""
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.orm import Session
from app import game_bridge as bridge
from app.db import make_engine
from app.models import Audit
from app.research_models import PaperDecision, ResearchEvent, ResearchOutcome, ResearchQuote

KEY = 'practice-key-never-stored'
HEADLINE = {'category': 'smelter_outage', 'kind': 'unscheduled', 'headline': 'Smelter outage cuts aluminium output',
            'direction': 'bull'}


@pytest.fixture
def s(tmp_path, monkeypatch):
    url = 'sqlite:///' + str(tmp_path / 'workspace.db')
    monkeypatch.setenv('DATABASE_URL', url)
    command.upgrade(Config('alembic.ini'), 'head')
    engine = make_engine(url)
    with Session(engine) as session:
        yield session
    engine.dispose()


def recorded(round_id, days=20, per_day=4, events=(1, 6, 11, 16), news=HEADLINE):
    """A round with the headline at step 1 of each listed day; each headline lifts the price 1 % from the next step."""
    steps = [day * per_day + 1 for day in events]
    ticks = [{'step': k, 'day': k // per_day, 'mid': round(2600 * 1.01 ** sum(e < k for e in steps), 2),
              'news': [{**news, 'step': k, 'day': k // per_day}] if k in steps else []} for k in range(days * per_day)]
    return {'round': round_id, 'label': 'Practice', 'profile': 'playtest_v0.2', 'steps_per_day': per_day, 'days': days,
            'ticks': ticks}


class FakeGame:
    """The participant API during one round. Each sleep of the bridge publishes the next step."""
    def __init__(self, data, published=0, label='Practice', profile='playtest_v0.2'):
        self.data, self.published, self.label, self.profile = data, published, label, profile
        self.position, self.orders, self.busy, self.reject = 0, [], 0, False

    def finished(self):
        return self.published >= len(self.data['ticks'])

    def advance(self, _seconds=None):
        if not self.finished():
            self.published += 1

    def handle(self, request):
        assert request.headers['X-API-Key'] == KEY
        path, params = request.url.path, request.url.params
        if path == '/market':
            return httpx.Response(200, json={'step': self.published - 1, 'finished': self.finished(), 'label': self.label,
                                             'profile': self.profile, 'steps_per_day': self.data['steps_per_day'],
                                             'days': self.data['days'], 'max_actions_per_sec': 5})
        if path == '/ticks':
            if params.get('round') not in (None, self.data['round']):
                return httpx.Response(200, json={'round': self.data['round'], 'seq': self.published, 'reset': True, 'ticks': []})
            ticks = [{**t, 'seq': t['step'] + 1} for t in self.data['ticks'][:self.published] if t['step'] + 1 > int(params['since'])]
            return httpx.Response(200, json={'round': self.data['round'], 'seq': self.published, 'reset': False, 'ticks': ticks})
        if path == '/account':
            return httpx.Response(200, json={'position': self.position})
        if path == '/orders':
            if self.busy:
                self.busy -= 1
                return httpx.Response(429, json={'detail': 'too many order actions'})
            if self.reject:
                return httpx.Response(422, json={'detail': 'round finished'})
            body = json.loads(request.content)
            self.orders.append(body)
            self.position += body['qty'] if body['side'] == 'buy' else -body['qty']
            return httpx.Response(200, json={'order_id': len(self.orders), 'filled': body['qty'], 'resting': 0,
                                             'fills': [{'price': 2600.5, 'qty': body['qty']}]})
        return httpx.Response(404)

    def client(self):
        return bridge.GameClient('http://game.test', KEY, transport=httpx.MockTransport(self.handle), sleep=lambda _: None)


def play(s, game, tmp_path, **options):
    lines = []
    finished = bridge.run(s, game.client(), 'tester', directory=tmp_path / 'rounds', log=lines.append, sleep=game.advance, **options)
    return finished, lines


def test_game_types_map_to_research_kinds_as_the_event_format_says():
    # docs/EVENT_SCHEMA.md, "Game type → research kind"
    table = {'lme_stocks': 'other', 'china_output': 'supply', 'china_policy': 'policy', 'trade_policy': 'policy',
             'energy_europe': 'energy', 'smelter_outage': 'supply', 'bauxite_disruption': 'supply', 'alumina': 'supply',
             'macro_usd': 'other', 'demand': 'demand', 'new_supply': 'supply', 'geopolitics': 'conflict'}
    for category, kind in table.items():
        event = bridge.game_event('r1', 3, 0, {**HEADLINE, 'category': category}, 'Practice')
        assert (event.kind, event.instrument, event.historical) == (kind, 'LME_AL_GAME', False)
        assert event.tags == (['new_capacity'] if category == 'new_supply' else [])
    assert bridge.game_event('r1', 3, 0, {**HEADLINE, 'category': 'meteor'}, '').kind == 'other'
    event = bridge.game_event('r1', 3, 0, HEADLINE, '', at=datetime(2026, 1, 5, tzinfo=timezone.utc))
    assert event.historical and event.external_key == 'game-history:r1:3:0'
    assert event.summary == 'smelter_outage, bull, unscheduled'


def test_finished_rounds_become_separate_labelled_history_blocks(s):
    first = bridge.learn(s, recorded('h1'), 'tester')
    assert (first['events'], first['outcomes']) == (4, 4)
    again = bridge.learn(s, recorded('h1'), 'tester')
    assert (again['events'], again['outcomes'], again['start']) == (0, 0, first['start'])
    second = bridge.learn(s, recorded('h2'), 'tester')
    start1, start2 = datetime.fromisoformat(first['start']), datetime.fromisoformat(second['start'])
    # A block ends a week before now or before the block after it: no chain window or outcome spans two rounds,
    # and the next live event can use all of it.
    assert start1 + timedelta(days=20) <= datetime.now(timezone.utc) - timedelta(days=7)
    assert start2 + timedelta(days=20) <= start1 - timedelta(days=7)
    outcomes = s.scalars(select(ResearchOutcome)).all()
    assert len(outcomes) == 8 and all(abs(Decimal(o.return_fraction) - Decimal('0.01')) < Decimal('0.0001') for o in outcomes)
    assert all(e.historical for e in s.scalars(select(ResearchEvent)))
    assert all(q.historical and q.instrument == 'LME_AL_GAME' for q in s.scalars(select(ResearchQuote)))
    # A headline on the last game day has no price one day later: an event, but no outcome.
    late = bridge.learn(s, recorded('h3', events=(19,)), 'tester')
    assert (late['events'], late['outcomes']) == (1, 0)


def test_learned_rounds_let_the_paper_engine_buy_in_the_game(s, tmp_path):
    bridge.setup(s, 'tester')
    bridge.learn(s, recorded('history-1'), 'tester')
    game = FakeGame(recorded('live-1', days=3, events=(0, 1)))
    finished, lines = play(s, game, tmp_path)
    assert finished == 1
    decisions = s.scalars(select(PaperDecision).order_by(PaperDecision.created_at)).all()
    assert [d.action for d in decisions] == ['BUY', 'HOLD'] and 'cooldown' in decisions[1].reason
    assert decisions[0].details['sample_count'] == 4
    assert game.orders == [{'side': 'buy', 'qty': 1, 'type': 'market', 'request_id': decisions[0].id}]
    order = s.scalar(select(Audit).where(Audit.action == 'game_order'))
    assert order.record_id == decisions[0].id and order.detail['status'] == 'sent' and order.detail['round'] == 'live-1'
    # The finished round is saved and learned, so the next round has two more analogues.
    assert (tmp_path / 'rounds' / 'live-1.json').is_file()
    assert lines[-1]['learned']['outcomes'] == 2
    live = s.scalars(select(ResearchEvent).where(ResearchEvent.external_key.startswith('game:live-1:'))).all()
    assert len(live) == 2 and not any(e.historical for e in live)
    stored = json.dumps([[a.detail for a in s.scalars(select(Audit))], [e.payload for e in s.scalars(select(ResearchEvent))]])
    assert KEY not in stored and KEY not in json.dumps(lines)


def test_headlines_seen_late_are_learned_but_not_traded(s, tmp_path):
    bridge.setup(s, 'tester')
    bridge.learn(s, recorded('history-1'), 'tester')
    game = FakeGame(recorded('live-2', days=3, events=(0,)), published=4)  # joins at step 3; the headline was at step 1
    play(s, game, tmp_path)
    assert game.orders == [] and not s.scalars(select(PaperDecision)).all()
    assert not s.scalar(select(ResearchEvent).where(ResearchEvent.external_key == 'game:live-2:1:0'))
    assert s.scalar(select(ResearchEvent).where(ResearchEvent.external_key == 'game-history:live-2:1:0'))


def test_refuses_an_unprepared_paper_account_and_a_final(s, tmp_path):
    game = FakeGame(recorded('r1', days=2, events=(0,)))
    with pytest.raises(bridge.NotReady):
        play(s, game, tmp_path)
    bridge.setup(s, 'tester')
    for label, profile in [('Finals Q1', 'v0.2'), ('LME demo', 'finals_2027')]:
        final = FakeGame(recorded('f1', days=2, events=(0,)), label=label, profile=profile)
        with pytest.raises(bridge.NotPractice):
            play(s, final, tmp_path)
        assert final.orders == []
    assert not s.scalars(select(ResearchEvent)).all()


def test_orders_stay_long_only_within_max_lots_and_retry_safely(s):
    game = FakeGame(recorded('r1', days=1, events=()))
    client = game.client()

    def place(identifier, action, lots=2):
        return bridge.place(s, client, {'id': identifier, 'action': action}, 'r1', 3, 'tester', lots, 3)

    game.busy = 1  # one 429 first: the retry carries the same request_id and places one order
    assert place('d1', 'BUY')['qty'] == 2
    assert game.orders == [{'side': 'buy', 'qty': 2, 'type': 'market', 'request_id': 'd1'}]
    assert place('d2', 'BUY')['qty'] == 1  # up to --max-lots 3
    assert place('d3', 'BUY')['status'] == 'skipped'
    assert place('d4', 'SELL', lots=5)['qty'] == 3  # never below zero: the bridge does not sell short
    assert place('d5', 'SELL')['reason'] == 'no long game position to reduce'
    game.reject, game.position = True, 0
    assert place('d6', 'BUY')['status'] == 'failed'
    audit = {a.record_id: a.detail['status'] for a in s.scalars(select(Audit).where(Audit.action == 'game_order'))}
    assert audit == {'d1': 'sent', 'd2': 'sent', 'd3': 'skipped', 'd4': 'sent', 'd5': 'skipped', 'd6': 'failed'}


def test_run_needs_a_server_and_the_key_variable(monkeypatch, capsys):
    monkeypatch.delenv('GAME_SERVER_URL', raising=False)
    monkeypatch.delenv('GAME_API_KEY', raising=False)
    with pytest.raises(SystemExit):
        bridge.main(['run'])
    assert 'GAME_SERVER_URL' in capsys.readouterr().err
    with pytest.raises(SystemExit):
        bridge.main(['run', '--server', 'http://game.test'])
    assert 'GAME_API_KEY' in capsys.readouterr().err
