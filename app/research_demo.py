"""Create fictional historical chains and execute one automatic paper decision.

Run only in a separate migrated demonstration database: python -m app.research_demo
"""
from datetime import datetime, timedelta, timezone
import json
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import make_engine, DATABASE_URL
from . import research
from .research_models import ResearchEvent, PaperAccount
from .research_schemas import EventIn, QuoteIn, OutcomeIn, PolicyIn


def populate(s):
    if s.scalar(select(ResearchEvent.id).limit(1)) or s.get(PaperAccount, 'paper'):
        raise ValueError('Demo requires an empty research workspace; use a separate database')
    actor = 'fictional-paper-demo'
    research.configure(s, PolicyIn(enabled=True), actor)
    clock = datetime.now(timezone.utc)
    for index in range(5):
        anchor = clock - timedelta(days=7 * (index + 1))
        for step, (kind, title) in enumerate([
            ('sanction', 'Fictional sanction restricts aluminium energy supply'),
            ('energy', 'Fictional power disruption affects aluminium smelter'),
            ('supply', 'Fictional smelter outage reduces aluminium supply')
        ]):
            when = anchor - timedelta(minutes=(2 - step) * 10)
            result = research.ingest_event(s, EventIn(external_key=f'demo-history-{index}-{step}', kind=kind,
                occurred_at=when, known_at=when, historical=True, title=title, summary='Fictional demonstration only',
                countries=['NO'], tags=['fictional-demo', 'aluminium'], source_reference='synthetic:paper-demo'), actor)
        event_id = result['event']['id']
        quotes = []
        for suffix, delta, price in [('entry', timedelta(minutes=1), '100'), ('exit', timedelta(hours=24, minutes=1), '104')]:
            when = anchor + delta
            quotes.append(research.ingest_quote(s, QuoteIn(external_key=f'demo-{index}-{suffix}', price=price,
                occurred_at=when, known_at=when, historical=True, source_reference='synthetic:paper-demo'), actor)['id'])
        research.label_outcome(s, OutcomeIn(event_id=event_id, entry_quote_id=quotes[0], exit_quote_id=quotes[1]), actor)
    research.ingest_quote(s, QuoteIn(external_key='demo-current-price', price='100', occurred_at=datetime.now(timezone.utc),
                                    source_reference='synthetic:paper-demo'), actor)
    for step, (kind, title) in enumerate([
        ('sanction', 'Fictional sanction restricts aluminium energy supply'),
        ('energy', 'Fictional power disruption affects aluminium smelter'),
        ('supply', 'Fictional smelter outage reduces aluminium supply')
    ]):
        result = research.ingest_event(s, EventIn(external_key=f'demo-live-{step}', kind=kind,
            occurred_at=clock - timedelta(minutes=(2 - step) * 10), title=title, summary='Fictional demonstration only',
            countries=['NO'], tags=['fictional-demo', 'aluminium'], source_reference='synthetic:paper-demo'), actor)
    return result


if __name__ == '__main__':
    engine = make_engine(DATABASE_URL)
    with Session(engine) as session:
        result = populate(session)
        print(json.dumps({'mode': 'fictional paper demo', 'event_id': result['event']['id'], 'decision': result['decision']}, indent=2))
