"""DC1 step B2: the Workspace works end to end against a running Data Core, through its API only."""
from datetime import datetime, timedelta, timezone
import time
from test_permutable import lead_source, capture, FakeAPI, event

SPEC = {'adapter': 'html-v1', 'facility_name': 'Test Works', 'country': 'NO', 'valid_from': '2025-01-01', 'unit': 'kt/year',
        'prefix': 'annual capacity of', 'suffix': 'kilotonnes'}

def html_document(core, example, content='<p>Test Works has an annual capacity of 400 kilotonnes</p>', url='https://example.org/html'):
    *_, payload = example
    return core.post('documents', {**payload, 'media_type': 'text/html', 'original_url': url, 'content': content})

def test_catalog_lists_core_plants_documents_and_sources(client, core, example):
    entity, source, document, _ = example
    catalog = client.get('/api/core/catalog').json()
    assert catalog['core_url'] == core.url
    assert [e['id'] for e in catalog['entities']] == [entity['id']] and catalog['entities'][0]['aliases'] == ['Test Works']
    assert [d['id'] for d in catalog['documents']] == [document['id']] and [s['id'] for s in catalog['sources']] == [source['id']]
    assert catalog['observations'] == []
    assert client.get('/api/core/documents/' + document['id'] + '/content').content == b'Capacity: 400 kt/year'
    assert client.get('/api/core/documents/missing/content').status_code == 422
    health = client.get('/api/health').json()
    assert health['scope'] == 'workspace' and health['core'] == {'url': core.url, 'status': 'ok'}

def test_lead_confirmed_with_a_candidate_fact_the_core_accepted(client, core, example, lead_source, monkeypatch):
    entity, *_ = example
    capture(client, monkeypatch, FakeAPI((200, [event()])))
    lead = client.get('/api/leads').json()['leads'][0]
    primary = html_document(core, example)
    # The Workspace proposes; the Core checks the source, matches the plant name and checks quality.
    proposal = client.post('/api/core/proposals', json={'document_id': primary['id'], 'extraction': SPEC})
    assert proposal.status_code == 201, proposal.text
    candidate = proposal.json()['candidates'][0]
    assert candidate['status'] == 'resolved' and candidate['entity_id'] == entity['id']
    fact = core.get('records/observations/' + candidate['observation_id'])
    assert fact['document_id'] == primary['id'] and fact['reported_value'] == '400'
    observations = client.get('/api/core/observations', params={'document_id': primary['id']}).json()
    assert [o['id'] for o in observations] == [fact['id']]
    decision = client.post('/api/leads/' + lead['id'] + '/decision', json={'status': 'follow_up', 'reason': 'Check the operator page'})
    assert decision.status_code == 200
    confirmed = client.post('/api/leads/' + lead['id'] + '/decision', json={'status': 'confirmed', 'reason': 'Operator page states the capacity',
                                                                          'primary_document_id': primary['id'], 'observation_id': fact['id']}).json()
    assert (confirmed['primary_document_id'], confirmed['observation_id']) == (primary['id'], fact['id'])
    audit = client.get('/api/records/audit', params={'limit': 1000}).json()['records']
    assert any(a['action'] == 'core_proposal' and a['detail']['candidates'][0]['observation_id'] == fact['id'] for a in audit)

def test_unclear_names_go_to_the_cores_human_review(client, core, example):
    core.post('entities', {'name': 'Test Works North', 'country': 'NO', 'facility_type': 'smelter'})
    primary = html_document(core, example, '<p>Test Work has an annual capacity of 400 kilotonnes</p>')
    result = client.post('/api/core/proposals', json={'document_id': primary['id'], 'extraction': {**SPEC, 'facility_name': 'Test Work'}}).json()
    candidate = result['candidates'][0]
    assert candidate['status'] != 'resolved' and candidate['observation_id'] is None and candidate['review_id']
    assert core.get('records/reviews/' + candidate['review_id'])['status'] == 'pending'
    assert core.get('records/observations')['total'] == 0

def test_the_core_refuses_proposals_it_cannot_check(client, core, example):
    primary = html_document(core, example)
    for document_id, extraction in [('missing', SPEC), (primary['id'], {**SPEC, 'prefix': 'not in the page'}), (primary['id'], {**SPEC, 'unit': 'tonnes'})]:
        response = client.post('/api/core/proposals', json={'document_id': document_id, 'extraction': extraction})
        assert response.status_code == 422, response.text
    assert core.get('records/observations')['total'] == 0
    assert not [a for a in client.get('/api/records/audit').json()['records'] if a['action'] == 'core_proposal']
    client.headers.pop('Authorization')
    assert client.post('/api/core/proposals', json={'document_id': primary['id'], 'extraction': SPEC}).status_code == 401

def test_research_chain_uses_core_links_recorded_in_time(client, core, example):
    facility, _, document, _ = example
    company = core.post('entities', {'name': 'Owner Co', 'kind': 'company', 'country': 'NO'})
    link = core.post('relationships', {'company_id': company['id'], 'facility_id': facility['id'], 'document_id': document['id'], 'role': 'OWNS',
                                       'percentage': 100, 'valid_from': '2020-01-01', 'evidence_reference': 'Register entry'})
    time.sleep(0.01)
    now = datetime.now(timezone.utc)
    base = {'summary': 'Fictional', 'source_reference': 'synthetic:test', 'historical': True}
    def post(key, kind, entity, occurred, known):
        body = {**base, 'external_key': key, 'kind': kind, 'title': key, 'entity_ids': [entity], 'occurred_at': occurred.isoformat(), 'known_at': known.isoformat()}
        response = client.post('/api/research/events', json=body)
        assert response.status_code == 201, response.text
        return response.json()['event']
    post('owner-news', 'corporate', company['id'], now - timedelta(minutes=10), now - timedelta(minutes=10))
    # Known after the Core recorded the link: the chain connects the two events through it.
    anchor = post('plant-outage', 'supply', facility['id'], now - timedelta(minutes=5), now)
    edge = next(e for e in anchor['chain']['edges'] if 'registered_relationship' in e['reasons'])
    # The chain keeps versioned Core references: the link fact and its document version.
    assert edge['core_relationships'] == [{'relationship_id': link['id'], 'company_id': company['id'], 'facility_id': facility['id'], 'document_id': document['id']}]
    # Known before the Core recorded the link: the link is not used.
    earlier = post('plant-outage-earlier', 'supply', facility['id'], now - timedelta(minutes=5), now - timedelta(minutes=4))
    assert earlier['chain']['sequence'] == ['supply'] and not earlier['chain']['edges']
    unknown = client.post('/api/research/events', json={**base, 'external_key': 'unknown', 'kind': 'supply', 'title': 'Unknown', 'entity_ids': ['missing'],
                                                         'occurred_at': now.isoformat(), 'known_at': now.isoformat()})
    assert unknown.status_code == 404

def test_unreachable_core_is_reported_not_guessed(client, core, example):
    entity, _, document, _ = example
    client.app.state.core.http.base_url = 'http://127.0.0.1:9/api'
    assert client.get('/api/health').json()['core']['status'] == 'unavailable'
    response = client.post('/api/asset-map/locations', json={'entity_id': entity['id'], 'latitude': 1, 'longitude': 1, 'document_id': document['id']})
    assert response.status_code == 503 and 'Data Core unavailable' in response.json()['detail']
    assert client.get('/api/asset-map').status_code == 503
    assert client.get('/api/research').status_code == 200  # parts that need no Core keep working
