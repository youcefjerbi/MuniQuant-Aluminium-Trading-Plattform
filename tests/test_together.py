"""DC1 step B5: the Data Core and the Workspace running together, as deployed with compose.together.yaml.

Runs against a running pair; skipped unless these are set:
    TOGETHER_CORE_URL, TOGETHER_CORE_WRITE_TOKEN        the Core and a Core curator's token
    TOGETHER_WORKSPACE_URL, TOGETHER_WRITE_TOKEN        the Workspace and its write token
Every run creates its own uniquely named records, so it can run again on the same pair.
"""
import os
from datetime import datetime, timezone
from uuid import uuid4
import httpx
import pytest

NAMES = ('TOGETHER_CORE_URL', 'TOGETHER_CORE_WRITE_TOKEN', 'TOGETHER_WORKSPACE_URL', 'TOGETHER_WRITE_TOKEN')
MISSING = [name for name in NAMES if not os.getenv(name)]
# CI sets TOGETHER_REQUIRED so a missing pair fails instead of passing as skipped.
if MISSING and os.getenv('TOGETHER_REQUIRED'): raise RuntimeError('The together test needs ' + ', '.join(MISSING))
pytestmark = pytest.mark.skipif(bool(MISSING), reason='needs a running pair: ' + ', '.join(NAMES))

def client(url, token):
    return httpx.Client(base_url=url.rstrip('/') + '/api', headers={'Authorization': 'Bearer ' + token}, timeout=60)

def created(response):
    assert response.status_code == 201, response.text
    return response.json()

def test_leads_research_investigations_and_map_work_against_the_running_core():
    core = client(os.environ['TOGETHER_CORE_URL'], os.environ['TOGETHER_CORE_WRITE_TOKEN'])
    workspace = client(os.environ['TOGETHER_WORKSPACE_URL'], os.environ['TOGETHER_WRITE_TOKEN'])
    run = uuid4().hex[:8]
    health = workspace.get('/health').json()
    assert health['scope'] == 'workspace' and health['core']['status'] == 'ok'
    # A curator records a plant, an owner and a primary source in the Core.
    plant = created(core.post('/entities', json={'name': f'Together Works {run}', 'country': 'NO', 'facility_type': 'smelter'}))
    owner = created(core.post('/entities', json={'name': f'Together Owner {run}', 'kind': 'company', 'country': 'NO'}))
    source = created(core.post('/sources', json={'name': f'Together source {run}', 'publisher': 'Fictional', 'source_type': 'synthetic',
                                                 'url': 'https://together.example/', 'access_status': 'permitted'}))
    page = created(core.post('/documents', json={'source_id': source['id'], 'title': 'Operations', 'original_url': f'https://together.example/{run}',
                                                 'media_type': 'text/html', 'content': f'<p>Together Works {run} has an annual capacity of 250 kilotonnes</p>'}))
    created(core.post('/relationships', json={'company_id': owner['id'], 'facility_id': plant['id'], 'document_id': page['id'], 'role': 'OWNS',
                                              'valid_from': '2020-01-01', 'evidence_reference': 'Operations page'}))
    # The Workspace reads them through the Core API ...
    catalog = workspace.get('/core/catalog').json()
    assert plant['id'] in {e['id'] for e in catalog['entities']} and page['id'] in {d['id'] for d in catalog['documents']}
    # ... proposes a candidate fact, which the Core checks and records under the Workspace's own identity ...
    proposal = created(workspace.post('/core/proposals', json={'document_id': page['id'], 'extraction': {
        'adapter': 'html-v1', 'facility_name': f'Together Works {run}', 'country': 'NO', 'valid_from': '2026-01-01', 'unit': 'kt/year',
        'prefix': 'annual capacity of', 'suffix': 'kilotonnes'}}))
    [candidate] = proposal['candidates']
    assert candidate['status'] == 'resolved' and candidate['entity_id'] == plant['id']
    history = core.get('/records/audit', params={'record_id': candidate['observation_id']}).json()['records']
    assert [entry['actor'] for entry in history] == ['workspace']
    # ... and keeps Core IDs in its own records: investigations, the map and research.
    case = created(workspace.post('/investigations', json={'title': f'Together case {run}', 'asset_ids': [plant['id']]}))
    assert created(workspace.post(f"/investigations/{case['id']}/revisions", json={'expected_version': 1,
                   'entry': {'kind': 'evidence', 'text': 'Operations page', 'document_id': page['id']}}))['version'] == 2
    created(workspace.post('/asset-map/locations', json={'entity_id': plant['id'], 'latitude': 60, 'longitude': 6, 'document_id': page['id'], 'synthetic': True}))
    node = next(n for n in workspace.get('/asset-map').json()['nodes'] if n['entity']['id'] == plant['id'])
    assert node['location']['document_id'] == page['id']
    now = datetime.now(timezone.utc).isoformat()
    for key, entity in (('owner', owner), ('plant', plant)):
        created(workspace.post('/research/events', json={'external_key': f'together-{run}-{key}', 'kind': 'corporate' if key == 'owner' else 'supply',
                                                         'title': key, 'summary': 'Fictional', 'source_reference': 'synthetic:together', 'entity_ids': [entity['id']],
                                                         'occurred_at': now, 'known_at': now, 'historical': True}))
    event = next(e for e in workspace.get('/research').json()['events'] if e['external_key'] == f'together-{run}-plant')
    assert any(link['facility_id'] == plant['id'] for edge in event['chain']['edges'] for link in edge.get('core_relationships', []))
    assert workspace.get('/leads').status_code == 200
    # The Core knows nothing of the Workspace records.
    assert all(case['id'] != row['record_id'] for row in core.get('/records/audit', params={'limit': 1000}).json()['records'])
