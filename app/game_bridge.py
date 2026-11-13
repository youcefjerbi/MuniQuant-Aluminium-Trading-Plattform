# Copyright 2026 muniQuant. Licensed under the Apache License, Version 2.0.
"""Practice bot: the Workspace's paper engine on the championship simulator's practice rounds.

The bridge reads the game's live feed and turns each headline into a research event under the research instrument
LME_AL_GAME, with the game type mapped to a research kind as docs/EVENT_SCHEMA.md says. It posts the game price as
quotes, lets the paper engine decide (app/research.py) and sends each BUY or SELL as a market order through the
game's participant API (service/API.md in the simulator repository). A finished round becomes labelled history on a
synthetic timeline, one game day per 24 hours, so later rounds have analogues to match.

Practice rounds only: research bots never trade finals scenarios. Nothing runs unless started by hand:

    python -m app.game_bridge setup
    GAME_API_KEY=... python -m app.game_bridge run --server http://127.0.0.1:8002
    python -m app.game_bridge learn data/game-rounds/<round>.json

See docs/GAME_BRIDGE.md.
"""
import argparse
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import httpx
from sqlalchemy import func, select
from . import research
from .models import Audit
from .research_models import PaperAccount, ResearchOutcome, ResearchQuote
from .research_schemas import EventIn, OutcomeIn, PolicyIn, QuoteIn

INSTRUMENT = 'LME_AL_GAME'
# docs/EVENT_SCHEMA.md, "Game type → research kind". Types the table does not name become 'other'.
GAME_KINDS = {'lme_stocks': 'other', 'china_output': 'supply', 'china_policy': 'policy', 'trade_policy': 'policy',
              'energy_europe': 'energy', 'smelter_outage': 'supply', 'bauxite_disruption': 'supply', 'alumina': 'supply',
              'macro_usd': 'other', 'demand': 'demand', 'new_supply': 'supply', 'geopolitics': 'conflict'}
GAME_TAGS = {'new_supply': ['new_capacity']}
DAY_US = 86_400_000_000
# Rounds learned one after another sit in separate blocks this far apart: more than the chain window plus the
# outcome horizon (72 h + 24 h), so no chain or analogue interval spans two rounds.
HISTORY_GAP = timedelta(days=7)
# Paper settings for the game's pace (by default one game day passes in about a minute). The research defaults
# assume real days: a one-hour cooldown would allow one trade every 60 game days.
GAME_POLICY = {'min_cases': 3, 'edge_threshold_bps': 10, 'fee_bps': 0, 'slippage_bps': 2, 'cooldown_seconds': 60,
               'max_daily_trades': 20, 'max_quote_age_seconds': 60, 'max_event_age_seconds': 60}


class NotPractice(RuntimeError):
    """The server names a final; research bots trade practice rounds only."""


class NotReady(RuntimeError):
    """The paper account does not trade LME_AL_GAME yet."""


class GameRejected(RuntimeError):
    """The game server refused a request."""


class NoCore:
    """Game events carry no Core plant IDs, so the chain builder gets no Core links and the Core need not run.

    Game headlines are fictional: linking them through real ownership facts would mix practice with real data."""
    def relationships(self):
        return []

    def entity(self, identifier):
        return None

    def first_audited(self, record_id):
        return None


def game_event(round_id, step, index, news, label, at=None):
    """A game headline as a research event. at=None: live, known now; otherwise historical at that time."""
    category = str(news.get('category') or 'unknown')
    when = at or datetime.now(timezone.utc)
    return EventIn(external_key=f"{'game-history' if at else 'game'}:{round_id}:{step}:{index}", instrument=INSTRUMENT,
                   kind=GAME_KINDS.get(category, 'other'), occurred_at=when, known_at=at, historical=at is not None,
                   title=str(news.get('headline') or category)[:500],
                   # Type, direction and scheduling as words, so similar headlines match on them. Not tags: a tag
                   # every game event shares would chain them all together.
                   summary=', '.join(str(v) for v in (category, news.get('direction'), news.get('kind')) if v),
                   source_reference=f'game:{label or "practice"}:round {round_id}:step {step}',
                   tags=GAME_TAGS.get(category, []))


def game_quote(round_id, step, mid, at=None):
    when = at or datetime.now(timezone.utc)
    return QuoteIn(external_key=f"{'game-history' if at else 'game'}:{round_id}:q{step}", instrument=INSTRUMENT,
                   price=Decimal(str(mid)), occurred_at=when, known_at=at, historical=at is not None,
                   source_reference=f'game:round {round_id}:step {step}')


def history_start(s, round_id, per_day, last_step):
    """Start of a round's synthetic timeline. A round learned before keeps its start (learning is idempotent); a new
    round goes in front of all game history, at least HISTORY_GAP before now and before the previous block."""
    own = s.scalars(select(ResearchQuote).where(
        ResearchQuote.external_key.startswith(f'game-history:{round_id}:q', autoescape=True)).limit(1)).first()
    if own:
        step = int(own.external_key.rsplit(':q', 1)[1])
        return research.stamp(own.observed_at) - timedelta(microseconds=step * DAY_US // per_day)
    earliest = s.scalar(select(func.min(ResearchQuote.observed_at)).where(
        ResearchQuote.external_key.startswith('game-history:', autoescape=True)))
    end = research.stamp(earliest) if earliest else datetime.now(timezone.utc)
    end = (end - HISTORY_GAP).replace(hour=0, minute=0, second=0, microsecond=0)
    return end - timedelta(days=last_step // per_day + 2)


def learn(s, recording, actor):
    """A recorded round becomes labelled history: every headline a historical event at its synthetic time, and each
    one with a price one game day later an outcome (entry: the price at the headline's step; exit: 24 hours on)."""
    round_id, per_day = str(recording['round']), int(recording['steps_per_day'])
    label = recording.get('label') or 'practice'
    ticks = {int(t['step']): t for t in recording['ticks'] if t.get('mid') is not None}
    if not ticks or per_day < 1:
        return {'round': round_id, 'events': 0, 'outcomes': 0}
    start = history_start(s, round_id, per_day, max(ticks))

    def at(step):  # integer microseconds: step + per_day lands exactly 24 hours after step
        return start + timedelta(microseconds=step * DAY_US // per_day)

    news_steps = [k for k in sorted(ticks) if ticks[k].get('news')]
    quotes = {}
    # Quotes first: a half-finished import is then found again by history_start and keeps its timeline.
    for k in sorted(set(news_steps) | {k + per_day for k in news_steps if k + per_day in ticks}):
        quotes[k] = research.ingest_quote(s, game_quote(round_id, k, ticks[k]['mid'], at(k)), actor)['id']
    events = outcomes = 0
    core = NoCore()
    for k in news_steps:
        for index, news in enumerate(ticks[k]['news']):
            result = research.ingest_event(s, game_event(round_id, k, index, news, label, at(k)), actor, core)
            events += not result['duplicate']
            if k + per_day in quotes:
                event_id = result['event']['id']
                new = s.scalar(select(ResearchOutcome.id).where(ResearchOutcome.event_id == event_id)) is None
                research.label_outcome(s, OutcomeIn(event_id=event_id, entry_quote_id=quotes[k],
                                                    exit_quote_id=quotes[k + per_day]), actor)
                outcomes += new
    return {'round': round_id, 'start': research.iso(start), 'events': events, 'outcomes': outcomes}


def setup(s, actor, **settings):
    """Point the paper account at LME_AL_GAME with settings for the game's pace (refused while it holds another
    instrument's position)."""
    return research.configure(s, PolicyIn(**{**GAME_POLICY, **settings, 'enabled': True, 'instrument': INSTRUMENT}), actor)


class GameClient:
    """The simulator's participant API (service/API.md): market, ticks, account and market orders."""
    def __init__(self, server, key, transport=None, timeout=10.0, sleep=time.sleep):
        if not key:
            raise ValueError('The practice account API key is missing')
        self.http = httpx.Client(base_url=server.rstrip('/'), headers={'X-API-Key': key}, timeout=timeout, transport=transport)
        self.sleep = sleep

    def close(self):
        self.http.close()

    def _json(self, response):
        if response.status_code != 200:
            raise GameRejected(f'{response.request.method} {response.request.url.path}: HTTP {response.status_code} '
                               f'{response.text[:200]}')
        return response.json()

    def market(self):
        return self._json(self.http.get('/market'))

    def ticks(self, since, round_id=None):
        return self._json(self.http.get('/ticks', params={'since': since, **({'round': round_id} if round_id else {})}))

    def account(self):
        return self._json(self.http.get('/account'))

    def order(self, side, qty, request_id):
        body = {'side': side, 'qty': qty, 'type': 'market', 'request_id': request_id}
        for _ in range(3):
            response = self.http.post('/orders', json=body)
            if response.status_code != 429:
                break
            self.sleep(1)  # over the order-action limit nothing changed; the same request_id makes the retry safe
        return self._json(response)


def practice_only(market):
    names = ' / '.join(str(market.get(k) or '') for k in ('label', 'profile'))
    if 'final' in names.casefold():
        raise NotPractice(f'The server names a final ({names}); research bots trade practice rounds only')


def place(s, game, decision, round_id, step, actor, lots, max_lots):
    """A BUY or SELL decision as one market order in the game, recorded in the audit log. The paper engine never
    sells short, so neither does the bridge: SELL only reduces a long game position."""
    side = 'buy' if decision['action'] == 'BUY' else 'sell'
    detail = {'instrument': INSTRUMENT, 'round': round_id, 'step': step, 'side': side, 'request_id': decision['id']}
    try:
        position = int(game.account()['position'])
        qty = min(lots, max_lots - position) if side == 'buy' else min(lots, position)
        if qty <= 0:
            detail.update(status='skipped', position=position,
                          reason='position already at --max-lots' if side == 'buy' else 'no long game position to reduce')
        else:
            response = game.order(side, qty, decision['id'])
            detail.update(status='sent', qty=qty, order_id=response.get('order_id'), filled=response.get('filled'),
                          fills=[{'price': f.get('price'), 'qty': f.get('qty')} for f in response.get('fills', [])[:20]])
    except (GameRejected, httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        detail.update(status='failed', reason=str(exc)[:500])
    s.add(Audit(actor=actor, action='game_order', record_id=decision['id'], detail=detail))
    s.commit()
    return detail


def trade(s, game, recording, tick, actor, lots, max_lots, log):
    """The newest tick: its price as a live quote, each headline as a live event the paper engine decides on."""
    round_id, step = recording['round'], int(tick['step'])
    if tick.get('mid') is not None:
        try:
            research.ingest_quote(s, game_quote(round_id, step, tick['mid']), actor)
        except research.Conflict:
            s.rollback()  # this step's price is stored already (the bridge was restarted)
    for index, news in enumerate(tick.get('news') or []):
        line = {'round': round_id, 'step': step, 'type': news.get('category'), 'headline': news.get('headline')}
        try:
            result = research.ingest_event(s, game_event(round_id, step, index, news, recording['label']), actor, NoCore())
        except ValueError as exc:  # handled before (Conflict), or refused by the chain limits
            s.rollback()
            log({**line, 'skipped': str(exc)})
            continue
        decision = result['decision']
        line.update(kind=result['event']['kind'], action=decision['action'] if decision else None,
                    reason=decision['reason'] if decision else 'no paper decision')
        if decision and decision['action'] != 'HOLD' and not result['duplicate']:
            line['order'] = place(s, game, decision, round_id, step, actor, lots, max_lots)
        log(line)


def close_round(s, recording, actor, directory, learn_rounds, log):
    """Save the finished round (git-ignored data/) and learn it, so the next round has analogues."""
    recording['done'] = True
    data = {k: recording[k] for k in ('round', 'label', 'profile', 'steps_per_day', 'days')}
    data['ticks'] = [recording['ticks'][k] for k in sorted(recording['ticks'])]
    path = Path(directory) / (re.sub(r'[^A-Za-z0-9_.-]', '_', str(recording['round']))[:100] + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1))
    line = {'round': recording['round'], 'finished': True, 'saved': str(path)}
    if learn_rounds:
        try:
            line['learned'] = learn(s, data, actor)
        except ValueError as exc:
            s.rollback()
            line['learn_failed'] = str(exc)
    log(line)


def run(s, game, actor, lots=1, max_lots=5, rounds=1, poll=0.5, directory='data/game-rounds', learn_rounds=True,
        log=print, sleep=time.sleep):
    """Follow the game until `rounds` rounds have finished (0: keep going). Only the newest tick is traded: headlines
    the bridge sees late (it joined mid-round, or fell behind) are recorded for learning but never traded."""
    account = s.get(PaperAccount, 'paper')
    if not account or account.instrument != INSTRUMENT:
        raise NotReady(f'The paper account does not trade {INSTRUMENT}; run "python -m app.game_bridge setup" first')
    round_id, seq, recording, finished = None, -1, None, 0
    while True:
        market = game.market()
        feed = game.ticks(seq, round_id)
        if feed.get('round') != round_id:
            if recording and recording['ticks'] and not recording['done']:
                close_round(s, recording, actor, directory, learn_rounds, log)  # a new round began before we saw the end
                finished += 1
                if rounds and finished >= rounds:
                    return finished
            practice_only(market)
            round_id, seq = feed.get('round'), -1
            recording = {'round': round_id, 'label': market.get('label') or '', 'profile': market.get('profile') or '',
                         'steps_per_day': int(market['steps_per_day']), 'days': market.get('days'), 'ticks': {}, 'done': False}
            log({'round': round_id, 'joined': True, 'label': recording['label'], 'profile': recording['profile'],
                 'step': market.get('step')})
            continue
        if feed.get('reset'):
            seq = int(feed.get('seq', seq))  # the gap no longer fits the server's buffer; carry on from now
            continue
        batch = feed.get('ticks') or []
        for tick in batch:
            recording['ticks'][int(tick['step'])] = {k: tick.get(k) for k in ('step', 'day', 'mid', 'news')}
            seq = max(seq, int(tick['seq']))
        if (batch and not market.get('finished') and not recording['done']
                and int(batch[-1]['step']) >= int(market.get('step', -1))):
            trade(s, game, recording, batch[-1], actor, lots, max_lots, log)
        if market.get('finished') and recording['ticks'] and not recording['done']:
            close_round(s, recording, actor, directory, learn_rounds, log)
            finished += 1
            if rounds and finished >= rounds:
                return finished
        sleep(poll)


def main(argv=None):
    from sqlalchemy.orm import Session
    from .db import make_engine, DATABASE_URL
    parser = argparse.ArgumentParser(prog='python -m app.game_bridge', description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    configure = commands.add_parser('setup', help=f'point the paper account at {INSTRUMENT} with settings for the game pace')
    for name, value in GAME_POLICY.items():
        configure.add_argument('--' + name.replace('_', '-'), type=int, default=value)
    configure.add_argument('--min-similarity', type=float, default=0.65)
    configure.add_argument('--min-agreement', type=float, default=0.8)
    play = commands.add_parser('run', help='trade practice rounds through the participant API')
    play.add_argument('--server', default=os.getenv('GAME_SERVER_URL'), help='game server URL (default GAME_SERVER_URL)')
    play.add_argument('--key-env', default='GAME_API_KEY', help='NAME of the variable holding the practice account key')
    play.add_argument('--lots', type=int, choices=range(1, 6), default=1, metavar='1-5', help='lots per order (default 1)')
    play.add_argument('--max-lots', type=int, choices=range(1, 21), default=5, metavar='1-20',
                      help='largest long position the bridge builds (default 5)')
    play.add_argument('--rounds', type=int, default=1, help='stop after this many finished rounds; 0 = keep going')
    play.add_argument('--poll', type=float, default=0.5, help='seconds between two polls (default 0.5)')
    play.add_argument('--rounds-dir', default=os.getenv('GAME_ROUNDS_DIR', 'data/game-rounds'))
    play.add_argument('--no-learn', action='store_true', help='save finished rounds without learning them')
    study = commands.add_parser('learn', help='turn recorded rounds into labelled history')
    study.add_argument('files', nargs='+')
    args = parser.parse_args(argv)
    actor = os.getenv('WRITE_ACTOR', 'game-bridge')
    if args.command == 'run':
        if not args.server:
            parser.error('--server or GAME_SERVER_URL is required')
        if not os.getenv(args.key_env):
            parser.error(f"set {args.key_env} to the practice account's API key")
    engine = make_engine(DATABASE_URL)
    try:
        with Session(engine) as s:
            if args.command == 'setup':
                settings = {name: getattr(args, name) for name in (*GAME_POLICY, 'min_similarity', 'min_agreement')}
                try:
                    policy = setup(s, actor, **settings)
                except (research.Conflict, ValueError) as exc:
                    parser.exit(1, f'{exc}\n')
                print(json.dumps({'instrument': INSTRUMENT, 'policy_id': policy['id'], 'settings': policy['settings']}, indent=2))
            elif args.command == 'learn':
                for name in args.files:
                    print(json.dumps(learn(s, json.loads(Path(name).read_text()), actor)))
            else:
                game = GameClient(args.server, os.environ[args.key_env])
                try:
                    done = run(s, game, actor, args.lots, args.max_lots, args.rounds, args.poll, args.rounds_dir,
                               not args.no_learn, log=lambda line: print(json.dumps(line), flush=True))
                    print(json.dumps({'rounds_finished': done}))
                except (NotReady, NotPractice, GameRejected, httpx.HTTPError) as exc:
                    parser.exit(1, f'{exc}\n')
                except KeyboardInterrupt:
                    print(json.dumps({'stopped': True}))
                finally:
                    game.close()
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
