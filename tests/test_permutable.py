"""Permutable lead feed. Fixtures are synthetic records shaped like the vendor API; no licensed data."""
import json
import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app import acquisition, permutable
from app.models import Base, Lead, LeadRevision, EntityEvidence, Run, RetrievalAttempt
from app.schemas import PermutableCaptureIn

SECRET = 'pk_test_synthetic_secret_value'

def event(event_id='evt-1', summary='Test Works smelter cuts output after a power outage', **extra):
    # Vendor analytics (direction, impact) are included to prove they are never stored.
    return {'event_id': event_id, 'ticker': 'ALI_COM', 'event_name': 'Synthetic smelter curtailment', 'event_date': '2026-10-09T06:03:42',
            'summary': summary, 'last_updated': '2026-10-09T16:08:53', 'event_type': 'Asset', 'direction': 'Bullish', 'impact': '0.8',
            'topic_id': 'topic-1', 'topic_name': 'Supply-Other', **extra}

def headline(event_id='evt-1', link='https://news.example/story', title='Test Works curtails potlines'):
    return {'event_id': event_id, 'event_type': 'Asset', 'link': link, 'created_at': '2026-10-09T06:20:00', 'source_name': 'Example News',
            'source_location': 'NO', 'publication_time': '2026-10-09T06:03:42', 'headline': title, 'language': 'en', 'image_url': 'https://news.example/i.jpg'}

class FakeAPI:
    """Stands in for fetch_once: records each URL and header set, serves queued responses."""
    def __init__(self, *responses):
        self.responses = list(responses); self.calls = []
    def __call__(self, url, allowed_hosts, headers=None):
        self.calls.append((url, headers))
        status, body = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        return (200, json.dumps(body).encode(), 'application/json', url) if status == 200 else (status, b'', None, url)

@pytest.fixture
def lead_source(client, monkeypatch):
    monkeypatch.setenv('PERMUTABLE_API_KEY', SECRET)
    response = client.post('/api/permutable/source', json={})
    assert response.status_code == 201, response.text
    return response.json()

def capture(client, monkeypatch, fake, **params):
    monkeypatch.setattr(acquisition, 'fetch_once', fake)
    response = client.post('/api/permutable/capture', json={'feed': 'events', **params})
    assert response.status_code == 200, response.text
    return response.json()

def assert_secret_absent(client):
    with client.app.state.engine.connect() as connection:
        for table in Base.metadata.sorted_tables:
            for row in connection.execute(table.select()):
                assert SECRET not in json.dumps([str(value) for value in row]), table.name
    for path in client.app.state.storage.glob('*'):
        assert SECRET.encode() not in path.read_bytes()

def test_source_registration_is_lead_only_idempotent_and_keeps_no_secret(client, lead_source):
    assert lead_source['access']['usage_scope'] == 'leads_only' and lead_source['access']['credential_ref'] == 'PERMUTABLE_API_KEY'
    assert lead_source['access']['allowed_hosts'] == [permutable.HOST] and lead_source['source']['source_type'] == 'commercial'
    assert client.post('/api/permutable/source', json={}).json()['access']['id'] == lead_source['access']['id']
    assert client.post('/api/permutable/source', json={'credential_ref': 'lower-case'}).status_code == 422
    assert_secret_absent(client)

def test_capture_preserves_response_and_derives_factual_matched_lead(client, example, lead_source, monkeypatch):
    entity, _, _, _ = example
    fake = FakeAPI((200, [event()]))
    summary = capture(client, monkeypatch, fake)
    assert (summary['new_documents'], summary['leads_created'], summary['revisions_added']) == (1, 1, 1)
    url, headers = fake.calls[0]
    assert url.startswith(permutable.BASE + '/events/feed/live/ticker/ALI_COM?') and 'event_type=Asset' in url and SECRET not in url
    assert headers == {'x-api-key': SECRET}
    lead = client.get('/api/leads').json()['leads'][0]
    assert lead['status'] == 'new' and lead['external_id'] == 'evt-1' and lead['ticker'] == 'ALI_COM'
    assert lead['latest_revision']['summary'] == event()['summary'] and lead['latest_revision']['topic_name'] == 'Supply-Other'
    assert [m['id'] for m in lead['matched_entities']] == [entity['id']]
    stored = json.dumps(lead)
    assert 'Bullish' not in stored and '"impact"' not in stored and '"direction"' not in stored
    assert not {'direction', 'impact'} & set(LeadRevision.__table__.columns.keys())
    raw = client.get('/api/documents/' + summary['document_ids'][0] + '/content').content
    assert json.loads(raw)[0]['impact'] == '0.8'  # vendor scores survive only in the exact preserved bytes
    assert client.get('/api/records/leads').json()['total'] == 1
    assert_secret_absent(client)

def test_unchanged_poll_deduplicates_and_revisions_keep_point_in_time_history(client, lead_source, monkeypatch):
    first = capture(client, monkeypatch, FakeAPI((200, [event()])))
    repeat = capture(client, monkeypatch, FakeAPI((200, [event()])))
    assert repeat['duplicate_documents'] == 1 and repeat['revisions_added'] == 0
    revised = capture(client, monkeypatch, FakeAPI((200, [event(summary='Test Works smelter restarts the curtailed potline', last_updated='2026-10-10T08:00:00')])))
    assert revised['new_documents'] == 1 and revised['revisions_added'] == 1 and revised['leads_created'] == 0
    with Session(client.app.state.engine) as s:
        revisions = s.scalars(select(LeadRevision).order_by(LeadRevision.vendor_updated_at)).all()
        assert [r.document_id for r in revisions] == [first['document_ids'][0], revised['document_ids'][0]]
        assert 'cuts output' in revisions[0].summary
    versions = sorted(d['version'] for d in client.get('/api/records/documents').json()['records'] if d['source_id'] == permutable.SOURCE_ID)
    assert versions == [1, 2]

def test_headlines_attach_to_leads_and_unsafe_links_are_dropped(client, lead_source, monkeypatch):
    capture(client, monkeypatch, FakeAPI((200, [event()])))
    result = capture(client, monkeypatch, FakeAPI((200, [headline(), headline(link='javascript:alert(1)', title='Unsafe link'), headline('evt-2', title='Headline arrives before its event')])), feed='event_headlines')
    assert result['headlines_added'] == 3 and result['leads_created'] == 1
    leads = {lead['external_id']: lead for lead in client.get('/api/leads').json()['leads']}
    links = {h['headline']: h['link'] for h in leads['evt-1']['headlines']}
    assert links == {'Test Works curtails potlines': 'https://news.example/story', 'Unsafe link': None}
    assert leads['evt-2']['latest_revision'] is None and leads['evt-2']['headlines'][0]['source_name'] == 'Example News'

def test_historical_capture_follows_next_token(client, lead_source, monkeypatch):
    fake = FakeAPI((200, {'data': [event('e1')], 'limit': 500, 'next_token': 'cursor-2', 'has_more': True}),
                   (200, {'data': [event('e2')], 'limit': 500, 'next_token': None, 'has_more': False}))
    summary = capture(client, monkeypatch, fake, mode='historical', start_date='2026-09-01', max_pages=5)
    assert summary['pages'] == 2 and summary['leads_created'] == 2
    assert 'start_date=2026-09-01' in fake.calls[0][0] and 'next_token=cursor-2' in fake.calls[1][0]
    assert client.post('/api/permutable/capture', json={'feed': 'events', 'start_date': '2026-09-01'}).status_code == 422

def test_missing_credential_blocks_capture_and_is_logged(client, lead_source, monkeypatch):
    monkeypatch.delenv('PERMUTABLE_API_KEY')
    monkeypatch.setattr(acquisition, 'fetch_once', FakeAPI((200, [event()])))
    response = client.post('/api/permutable/capture', json={'feed': 'events'})
    assert response.status_code == 422 and 'PERMUTABLE_API_KEY' in response.json()['detail']
    with Session(client.app.state.engine) as s:
        assert 'PERMUTABLE_API_KEY' in s.scalar(select(Run).where(Run.status == 'failed')).manifest['error']
        assert s.scalar(select(RetrievalAttempt).where(RetrievalAttempt.status == 'blocked'))
        assert not s.scalars(select(Lead)).all()

def test_rate_limit_backs_off_exponentially(client, lead_source, monkeypatch):
    sleeps = []
    monkeypatch.setattr(acquisition.time, 'sleep', sleeps.append)
    capture(client, monkeypatch, FakeAPI((429, None), (200, [event()])))
    assert sleeps and sleeps[0] >= 1
    with Session(client.app.state.engine) as s:
        assert [a.status for a in s.scalars(select(RetrievalAttempt).order_by(RetrievalAttempt.recorded_at, RetrievalAttempt.attempt))] == ['failed', 'success']

def test_lead_documents_are_never_evidence(client, example, lead_source, monkeypatch):
    entity, _, primary, _ = example
    lead_doc = capture(client, monkeypatch, FakeAPI((200, [event()])))['document_ids'][0]
    observation = {'entity_id': entity['id'], 'document_id': lead_doc, 'attribute': 'status', 'reported_value': 'suspended', 'reported_unit': 'status', 'valid_from': '2026-10-09', 'evidence_reference': 'event summary'}
    assert 'Lead-only' in client.post('/api/observations', json=observation).json()['detail']
    company = client.post('/api/entities', json={'name': 'Owner Co', 'kind': 'company', 'country': 'NO'}).json()
    relation = {'company_id': company['id'], 'facility_id': entity['id'], 'document_id': lead_doc, 'role': 'OWNS', 'valid_from': '2026-10-09', 'evidence_reference': 'event summary'}
    assert client.post('/api/relationships', json=relation).status_code == 422
    assert client.post('/api/entities/' + entity['id'] + '/evidence', json={'document_id': lead_doc, 'evidence_reference': 'event', 'reason': 'Vendor event names the facility'}).status_code == 422
    quality = client.get('/api/quality').json()
    assert not any(f['record_id'] == lead_doc and f['code'] == 'MISSING_PUBLICATION_DATE' for f in quality['findings'])
    package = client.get('/api/export').json()
    assert permutable.SOURCE_ID not in {s['source_id'] for s in package['sources']} and lead_doc not in {d['document_id'] for d in package['documents']}
    with Session(client.app.state.engine) as s:  # a bypass of the API is still caught before export
        s.add(EntityEvidence(entity_id=entity['id'], document_id=lead_doc, evidence_reference='event', reviewer='bypass', reason='direct insert')); s.commit()
    quality = client.get('/api/quality').json()
    assert quality['status'] == 'FAIL' and any(f['code'] == 'LEAD_SOURCE_CITED' for f in quality['findings'])
    assert client.get('/api/export').status_code == 422
    assert primary['id'] != lead_doc

def test_lead_triage_is_audited_and_final(client, example, lead_source, monkeypatch):
    entity, _, primary, _ = example
    lead_doc = capture(client, monkeypatch, FakeAPI((200, [event()])))['document_ids'][0]
    lead = client.get('/api/leads').json()['leads'][0]
    path = '/api/leads/' + lead['id'] + '/decision'
    assert client.post(path, json={'status': 'follow_up', 'reason': 'Check the operator release'}).json()['status'] == 'follow_up'
    assert client.post(path, json={'status': 'confirmed', 'reason': 'x' * 5}).status_code == 422
    assert 'Lead-only' in client.post(path, json={'status': 'confirmed', 'reason': 'Vendor only', 'primary_document_id': lead_doc}).json()['detail']
    observation = client.post('/api/observations', json={'entity_id': entity['id'], 'document_id': primary['id'], 'attribute': 'status', 'reported_value': 'suspended',
                                                         'reported_unit': 'status', 'valid_from': '2026-10-09', 'evidence_reference': 'Operator release paragraph 2'}).json()
    confirmed = client.post(path, json={'status': 'confirmed', 'reason': 'Operator release confirms the curtailment', 'primary_document_id': primary['id'], 'observation_id': observation['id']})
    assert confirmed.status_code == 200 and confirmed.json()['primary_document_id'] == primary['id']
    assert client.post(path, json={'status': 'dismissed', 'reason': 'Too late'}).status_code == 409
    assert client.post('/api/leads/unknown/decision', json={'status': 'dismissed', 'reason': 'Unknown'}).status_code == 404
    audit = client.get('/api/records/audit?limit=1000').json()['records']
    assert [a['detail']['status'] for a in audit if a['action'] == 'lead_decision' and a['record_id'] == lead['id']].count('confirmed') == 1
    assert client.get('/api/leads?status=confirmed').json()['total'] == 1

def test_lead_replay_proves_equivalence_and_detects_tampering(client, lead_source, monkeypatch):
    document = capture(client, monkeypatch, FakeAPI((200, [event()])))['document_ids'][0]
    replay = client.post('/api/permutable/documents/' + document + '/replay', json={})
    assert replay.status_code == 200 and replay.json()['equivalent'] and replay.json()['verified'] == 1
    with client.app.state.engine.begin() as connection:
        connection.execute(text("UPDATE lead_revision SET summary='edited after capture'"))
    assert 'differ' in client.post('/api/permutable/documents/' + document + '/replay', json={}).json()['detail']

def test_short_names_do_not_create_false_matches(client, lead_source, monkeypatch):
    client.post('/api/entities', json={'name': 'Qatalum', 'country': 'QA', 'facility_type': 'smelter', 'aliases': ['QA']})
    capture(client, monkeypatch, FakeAPI((200, [event(summary='QA team reviews aluminium shipments')])))
    assert client.get('/api/leads').json()['leads'][0]['matched_entities'] == []

def test_capture_parse_failure_is_logged_without_partial_leads(client, lead_source, monkeypatch):
    monkeypatch.setattr(acquisition, 'fetch_once', FakeAPI((200, {'unexpected': True})))
    response = client.post('/api/permutable/capture', json={'feed': 'events'})
    assert response.status_code == 422 and 'shape' in response.json()['detail']
    with Session(client.app.state.engine) as s:
        assert not s.scalars(select(Lead)).all()
        assert any(r.manifest.get('adapter') == 'permutable-leads' and r.status == 'failed' for r in s.scalars(select(Run)))

def test_reference_responses_are_preserved_without_leads(client, lead_source, monkeypatch):
    fake = FakeAPI((200, {'id': 'ALI_COM', 'name': 'Aluminum (COMEX)', 'unit': 'metric ton', 'currency': 'USD'}))
    summary = capture(client, monkeypatch, fake, feed='ticker_info')
    assert fake.calls[0][0] == permutable.BASE + '/ticker/ALI_COM/info' and summary['new_documents'] == 1 and summary['leads_created'] == 0
    assert client.post('/api/permutable/capture', json={'feed': 'event_topics', 'mode': 'historical'}).status_code == 422
    assert 'no derived leads' in client.post('/api/permutable/documents/' + summary['document_ids'][0] + '/replay', json={}).json()['detail']

def test_leads_sort_by_event_date_and_filter_by_match_and_topic(client, example, lead_source, monkeypatch):
    older = event('old', summary='Unrelated aluminium market note', event_date='2026-08-01T00:00:00', topic_name='Price Commentary-Review')
    capture(client, monkeypatch, FakeAPI((200, [older, event('new')])))
    listing = client.get('/api/leads').json()
    assert [l['external_id'] for l in listing['leads']] == ['new', 'old'] and listing['topics'] == ['Price Commentary-Review', 'Supply-Other']
    assert [l['external_id'] for l in client.get('/api/leads', params={'matched': 'true'}).json()['leads']] == ['new']
    assert client.get('/api/leads', params={'topic': 'Price Commentary-Review'}).json()['total'] == 1
    # An older state delivered later by a backfill is kept as history but does not replace the current view.
    backfill = {'data': [event('new', summary='Earlier draft of the curtailment', last_updated='2026-10-01T00:00:00')], 'has_more': False}
    capture(client, monkeypatch, FakeAPI((200, backfill)), mode='historical', start_date='2026-09-01')
    lead = next(l for l in client.get('/api/leads').json()['leads'] if l['external_id'] == 'new')
    assert lead['revision_count'] == 2 and lead['latest_revision']['summary'] == event()['summary'] and lead['vendor_updated_at'] == '2026-10-09T16:08:53'

def test_access_rereview_keeps_lead_scope_and_credential_unless_changed(client, lead_source):
    path = '/api/sources/' + permutable.SOURCE_ID + '/access'
    policy = {'status': 'permitted', 'allowed_hosts': [permutable.HOST], 'basis': 'Licence renewed for 2027 and terms reviewed', 'retention': 'Local only'}
    renewed = client.post(path, json=policy).json()
    assert renewed['usage_scope'] == 'leads_only' and renewed['credential_ref'] == 'PERMUTABLE_API_KEY' and renewed['auth_header'] == 'x-api-key'
    assert client.post(path, json={**policy, 'credential_ref': 'OTHER_KEY'}).status_code == 422  # header name must accompany it
    assert client.post(path, json={**policy, 'usage_scope': 'evidence'}).json()['usage_scope'] == 'evidence'

def test_credentials_are_bound_to_their_registered_hosts(client, example, lead_source, monkeypatch):
    _, source, _, _ = example
    base = {'status': 'permitted', 'basis': 'Exfiltration attempt by a writer', 'retention': 'Local only', 'auth_header': 'authorization'}
    for ref, hosts in [('WRITE_TOKEN', ['evil.example']), ('DATABASE_URL', ['evil.example']), ('PERMUTABLE_API_KEY', ['evil.example'])]:
        response = client.post('/api/sources/' + source['id'] + '/access', json={**base, 'credential_ref': ref, 'allowed_hosts': hosts})
        assert response.status_code == 422 and 'registered' in response.json()['detail']
    assert client.post('/api/permutable/source', json={'credential_ref': 'WRITE_TOKEN'}).status_code == 422
    monkeypatch.setenv('LICENSED_CREDENTIALS_JSON', json.dumps({'VENDOR_KEY': ['api.vendor.example']}))
    allowed = client.post('/api/sources/' + source['id'] + '/access', json={**base, 'credential_ref': 'VENDOR_KEY', 'allowed_hosts': ['api.vendor.example']})
    assert allowed.status_code == 201, allowed.text

def test_malformed_key_is_rejected_and_secrets_are_redacted(client, lead_source, monkeypatch):
    monkeypatch.setenv('PERMUTABLE_API_KEY', SECRET + '\r\nX-Injected: 1')
    monkeypatch.setattr(acquisition, 'fetch_once', FakeAPI((200, [event()])))
    response = client.post('/api/permutable/capture', json={'feed': 'events'})
    assert response.status_code == 422 and 'invalid characters' in response.json()['detail'] and SECRET not in response.text
    monkeypatch.setenv('PERMUTABLE_API_KEY', SECRET + '\n')  # a trailing newline from a CRLF .env is tolerated
    def leaky(url, hosts, headers=None): raise ValueError('upstream echoed ' + headers['x-api-key'])
    monkeypatch.setattr(acquisition, 'fetch_once', leaky)
    response = client.post('/api/permutable/capture', json={'feed': 'events'})
    assert response.status_code == 422 and '[redacted]' in response.json()['detail'] and SECRET not in response.text
    assert_secret_absent(client)

def test_revoked_licence_neither_blocks_export_nor_is_silently_reopened(client, example, lead_source, monkeypatch):
    capture(client, monkeypatch, FakeAPI((200, [event()])))
    policy = {'status': 'restricted', 'allowed_hosts': [permutable.HOST], 'basis': 'Licence ended; stop capture', 'retention': 'Purge after audit'}
    assert client.post('/api/sources/' + permutable.SOURCE_ID + '/access', json=policy).status_code == 201
    quality = client.get('/api/quality').json()
    assert quality['status'] != 'FAIL' and any(f['code'] == 'ACCESS_REVOKED' and f['severity'] == 'INFO' for f in quality['findings'])
    assert client.get('/api/export').status_code == 200
    assert 'restricted' in client.post('/api/permutable/source', json={}).json()['detail']
    assert client.post('/api/permutable/capture', json={'feed': 'events'}).status_code == 422
    draft = client.get('/api/export/draft').json()
    assert permutable.SOURCE_ID not in {s['id'] for s in draft['sources']} and all(d['source_id'] != permutable.SOURCE_ID for d in draft['documents'])

def test_builds_on_a_source_later_limited_to_leads_block_export(client, example):
    from tests.test_evidence import SPEC, html_doc
    _, source, _, _ = example
    doc = html_doc(client, example)
    assert client.post('/api/documents/' + doc['id'] + '/extract', json=SPEC).status_code == 201
    policy = {'status': 'permitted', 'allowed_hosts': ['example.org'], 'basis': 'Reclassified as a news lead feed', 'retention': 'Local only', 'usage_scope': 'leads_only'}
    assert client.post('/api/sources/' + source['id'] + '/access', json=policy).status_code == 201
    codes = {(f['code'], f['record_type']) for f in client.get('/api/quality').json()['findings']}
    assert ('LEAD_SOURCE_CITED', 'build') in codes and ('LEAD_SOURCE_CITED', 'observation') in codes
    assert client.get('/api/export').status_code == 422

def test_current_view_uses_real_timestamps_and_follows_reverts(client, lead_source, monkeypatch):
    capture(client, monkeypatch, FakeAPI((200, [event(summary='state A', last_updated='2026-10-09T10:00:00.500000Z')])))
    capture(client, monkeypatch, FakeAPI((200, [event(summary='state B', last_updated='2026-10-09T10:00:00Z')])))
    lead = client.get('/api/leads').json()['leads'][0]
    assert lead['latest_revision']['summary'] == 'state A' and lead['revision_count'] == 2  # .5 s later wins, not the longer string
    capture(client, monkeypatch, FakeAPI((200, [event('evt-2', summary='A', last_updated=None)])))
    capture(client, monkeypatch, FakeAPI((200, [event('evt-2', summary='B', last_updated=None)])))
    capture(client, monkeypatch, FakeAPI((200, [event('evt-2', summary='A', last_updated=None)])))
    lead = next(l for l in client.get('/api/leads').json()['leads'] if l['external_id'] == 'evt-2')
    assert lead['revision_count'] == 2 and lead['latest_revision']['summary'] == 'A'

def test_numeric_event_ids_are_accepted(client, lead_source, monkeypatch):
    assert capture(client, monkeypatch, FakeAPI((200, [event(12345)])))['leads_created'] == 1
    assert client.get('/api/leads').json()['leads'][0]['external_id'] == '12345'

def test_concurrent_capture_race_is_retried(client, lead_source, monkeypatch):
    original = permutable._lead
    raced = []
    def racing(s, event_id, ticker, seen_at):
        if not raced:  # another poller commits the same new lead first
            raced.append(1)
            with Session(client.app.state.engine) as other:
                original(other, event_id, ticker, seen_at); other.commit()
        return original(s, event_id, ticker, seen_at)
    monkeypatch.setattr(permutable, '_lead', racing)
    summary = capture(client, monkeypatch, FakeAPI((200, [event()])))
    assert raced and summary['revisions_added'] == 1 and client.get('/api/leads').json()['total'] == 1

def test_network_wait_does_not_hold_a_database_write_lock(client, lead_source, monkeypatch):
    from sqlalchemy import create_engine
    url = client.app.state.engine.url
    probe = create_engine(url.render_as_string(hide_password=False), connect_args={'timeout': 1} if url.get_backend_name() == 'sqlite' else {})
    def slow_fetch(target, hosts, headers=None):
        # Another writer must get through while the download is in flight.
        with probe.begin() as connection:
            connection.execute(text("INSERT INTO audit (id, created_at, actor, action, record_id, detail) VALUES ('probe', '2026-10-11', 'probe', 'probe', 'probe', '{}')"))
        return 200, json.dumps([event()]).encode(), 'application/json', target
    monkeypatch.setattr(acquisition, 'fetch_once', slow_fetch)
    assert client.post('/api/permutable/capture', json={'feed': 'events'}).status_code == 200
    probe.dispose()
