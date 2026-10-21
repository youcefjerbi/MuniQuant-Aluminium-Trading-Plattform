"""The production search path runs in PostgreSQL; fallback stays portable."""
import sqlite3
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from app import permutable
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


def rename_in_core(core, entity_id, name):
    # The Core has no rename endpoint; a curator renames a plant in the Core database itself.
    with sqlite3.connect(core.directory / 'core.db') as connection:
        connection.execute('UPDATE entities SET name=? WHERE id=?', (name, entity_id))


def search_text(client):
    with client.app.state.engine.connect() as connection:
        return connection.execute(text('SELECT search_text FROM lead')).scalar()


def test_search_projection_follows_core_names_after_refresh(client, core, example, lead_source, monkeypatch):
    capture(client, monkeypatch, FakeAPI((200, [event(summary='Test Works power outage')])))
    capture(client, monkeypatch, FakeAPI((200, [headline(title='Potlines curtailed')])), feed='event_headlines')
    assert search_text(client) == 'Supply-Other Synthetic smelter curtailment Test Works power outage Test Smelter Potlines curtailed'
    rename_in_core(core, example[0]['id'], 'Renamedasset')
    # The Core cannot call the Workspace: a rename reaches the projection on the next refresh.
    assert 'Renamedasset' not in search_text(client)
    with Session(client.app.state.engine) as s:
        assert permutable.refresh_search(s, client.app.state.core.cached()) == 1
        s.commit()
        assert permutable.refresh_search(s, client.app.state.core.cached()) == 0
    assert search_text(client).endswith('Renamedasset Potlines curtailed')
    assert client.get('/api/leads', params={'search': 'Renamedasset'}).json()['total'] == 1


def test_projection_equals_the_former_database_function(client, core, example, lead_source, monkeypatch):
    """The text the PostgreSQL function refresh_lead_search produced before the split, given the same names."""
    if client.app.state.engine.dialect.name != 'postgresql':
        pytest.skip('requires TEST_DATABASE_URL')
    second = core.post('entities', {'name': 'Second Works', 'country': 'NO', 'facility_type': 'smelter'})
    capture(client, monkeypatch, FakeAPI((200, [event('a', summary='Test Works and Second Works power outage'), event('b', summary=''),
                                               event('c', summary='Nothing matched', topic_name=None)])))
    capture(client, monkeypatch, FakeAPI((200, [headline('a', title='One'), headline('a', title='Two'), headline('d', title='Orphan headline')])), feed='event_headlines')
    names = {entity['id']: entity['name'] for entity in core.get('records/entities')['records']}
    assert second['id'] in names
    with client.app.state.engine.begin() as connection:
        connection.execute(text('CREATE TEMP TABLE entities (id text PRIMARY KEY, name text NOT NULL)'))
        for identifier, name in names.items():
            connection.execute(text('INSERT INTO entities VALUES (:id, :name)'), {'id': identifier, 'name': name})
        former = dict(connection.execute(text("""SELECT l.id, concat_ws(' ', l.topic_name,
            (SELECT concat_ws(' ', r.event_name, r.summary,
                 (SELECT string_agg(e.name, ' ' ORDER BY e.id) FROM entities e WHERE r.matched_entity_ids::jsonb ? e.id))
             FROM lead_revision r WHERE r.lead_id=l.id
             ORDER BY (r.content_hash=l.current_revision_hash) DESC, r.recorded_at DESC, r.id LIMIT 1),
            (SELECT string_agg(h.headline, ' ' ORDER BY h.id) FROM lead_headline h WHERE h.lead_id=l.id)) FROM lead l""")).all())
        current = dict(connection.execute(text('SELECT id, search_text FROM lead')).all())
    assert len(current) == 4 and current == former


def test_postgres_projection_updates_and_index_plan(client, core, example, lead_source, monkeypatch):
    if client.app.state.engine.dialect.name != 'postgresql':
        pytest.skip('requires TEST_DATABASE_URL')
    capture(client, monkeypatch, FakeAPI((200, [event(summary='Test Smelter power outage')])))
    assert client.get('/api/leads', params={'search':'power'}).json()['total'] == 1
    capture(client, monkeypatch, FakeAPI((200, [event(summary='Test Smelter restart',
                     last_updated='2026-10-10T16:08:53')])))
    assert client.get('/api/leads', params={'search':'power'}).json()['total'] == 0
    assert client.get('/api/leads', params={'search':'restart'}).json()['total'] == 1
    rename_in_core(core, example[0]['id'], 'Renamedasset')
    with Session(client.app.state.engine) as s:
        permutable.refresh_search(s, client.app.state.core.cached()); s.commit()
    with client.app.state.engine.begin() as connection:
        connection.execute(text('SET LOCAL enable_seqscan=off'))
        plan = connection.execute(text("""EXPLAIN SELECT id FROM lead WHERE
            to_tsvector('simple'::regconfig, search_text) @@ to_tsquery('simple','restart')""")).all()
        assert 'ix_lead_search_gin' in str(plan)
    assert client.get('/api/leads', params={'search':'Renamedasset'}).json()['total'] == 1
