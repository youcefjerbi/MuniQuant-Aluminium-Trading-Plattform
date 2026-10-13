"""The production search path runs in PostgreSQL; fallback stays portable."""
import pytest
from sqlalchemy import text
from test_permutable import lead_source, capture, FakeAPI, event, headline


def test_search_pagination_and_headlines(client, example, lead_source, monkeypatch):
    capture(client, monkeypatch, FakeAPI((200, [event('one', summary='power outage'),
                                               event('two', summary='power outage')])))
    capture(client, monkeypatch, FakeAPI((200, [headline('one', title='Rareword shutdown')])), feed='event_headlines')
    first = client.get('/api/leads', params={'search':'power','limit':1}).json()
    second = client.get('/api/leads', params={'search':'power','limit':1,'offset':1}).json()
    assert first['total'] == second['total'] == 2
    assert first['leads'][0]['id'] != second['leads'][0]['id']
    assert client.get('/api/leads', params={'search':'Rareword'}).json()['total'] == 1
    assert client.get('/api/leads', params={'search':'!!!'}).json()['total'] == 0
    assert client.get('/api/leads', params={'search':'power','topic':'missing'}).json()['total'] == 0
    if client.app.state.engine.dialect.name == 'postgresql':
        assert first['ranking'] == 'postgres-fts-v1'


def test_postgres_projection_updates_and_index_plan(client, example, lead_source, monkeypatch):
    if client.app.state.engine.dialect.name != 'postgresql':
        pytest.skip('requires TEST_DATABASE_URL')
    capture(client, monkeypatch, FakeAPI((200, [event(summary='Test Smelter power outage')])))
    assert client.get('/api/leads', params={'search':'power'}).json()['total'] == 1
    capture(client, monkeypatch, FakeAPI((200, [event(summary='Test Smelter restart',
                     last_updated='2026-10-10T16:08:53')])))
    assert client.get('/api/leads', params={'search':'power'}).json()['total'] == 0
    assert client.get('/api/leads', params={'search':'restart'}).json()['total'] == 1
    with client.app.state.engine.begin() as connection:
        connection.execute(text("UPDATE entities SET name='Renamedasset' WHERE id=:id"), {'id':example[0]['id']})
        connection.execute(text('SET LOCAL enable_seqscan=off'))
        plan = connection.execute(text("""EXPLAIN SELECT id FROM lead WHERE
            to_tsvector('simple'::regconfig, search_text) @@ to_tsquery('simple','restart')""")).all()
        assert 'ix_lead_search_gin' in str(plan)
    assert client.get('/api/leads', params={'search':'Renamedasset'}).json()['total'] == 1
