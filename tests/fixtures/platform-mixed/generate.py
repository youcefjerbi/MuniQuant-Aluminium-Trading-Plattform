"""Make the mixed platform fixture with the platform's own code: run from a checkout at commit 26a0bcd.

Fictional Core data, the licensed lead feed with synthetic vendor responses (no licensed data),
a confirmed lead, research, an investigation and the map, all created through the platform API.

    python generate.py OUTPUT_DIRECTORY
"""
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True)
database = out / 'platform.db'
os.environ['DATABASE_URL'] = 'sqlite:///' + str(database)
os.environ['PERMUTABLE_API_KEY'] = 'synthetic-fixture-credential'
from alembic import command
from alembic.config import Config
command.upgrade(Config('alembic.ini'), 'head')
from fastapi.testclient import TestClient
from app import acquisition
from app.main import create_app

def respond(body):
    def fetch(url, allowed_hosts, headers=None):
        return 200, json.dumps(body).encode(), 'application/json', url
    return fetch

app = create_app(os.environ['DATABASE_URL'], out / 'snapshots', write_token='fixture-token')
client = TestClient(app)
client.headers['Authorization'] = 'Bearer fixture-token'
def call(path, data, status=201):
    response = client.post('/api/' + path, json=data)
    assert response.status_code == status, response.text
    return response.json()

smelter = call('entities', {'name': 'Fjord Aluminium Works', 'country': 'NO', 'facility_type': 'smelter', 'aliases': ['Fjord Works']})
refinery = call('entities', {'name': 'Fjord Alumina Refinery', 'country': 'NO', 'facility_type': 'refinery'})
company = call('entities', {'name': 'Fjord Metals ASA', 'kind': 'company', 'country': 'NO'})
source = call('sources', {'name': 'Fjord Metals releases', 'publisher': 'Fjord Metals ASA (fictional)', 'source_type': 'synthetic',
                          'url': 'https://fjord.example/', 'access_status': 'permitted'})
release = call('documents', {'source_id': source['id'], 'title': 'Operations update', 'original_url': 'https://fjord.example/update', 'published_at': '2026-10-08',
                             'content': 'Fjord Aluminium Works suspended one potline after a power outage.'})
fact = call('observations', {'entity_id': smelter['id'], 'document_id': release['id'], 'attribute': 'status', 'reported_value': 'suspended',
                             'reported_unit': 'status', 'valid_from': '2026-10-08', 'evidence_reference': 'Operations update, sentence 1'})
call('relationships', {'company_id': company['id'], 'facility_id': smelter['id'], 'document_id': release['id'], 'role': 'OWNS', 'percentage': 100,
                       'valid_from': '2020-01-01', 'evidence_reference': 'Operations update, owner line'})

call('permutable/source', {})
event = {'event_id': 'fixture-event-1', 'ticker': 'ALI_COM', 'event_name': 'Fictional smelter curtailment', 'event_date': '2026-10-09T06:00:00',
         'summary': 'Fjord Works curtails a potline after a power outage', 'last_updated': '2026-10-09T08:00:00', 'event_type': 'Asset',
         'direction': 'Bullish', 'impact': '0.5', 'topic_name': 'Supply-Other'}
acquisition.fetch_once = respond([event])
events = call('permutable/capture', {'feed': 'events', 'mode': 'historical', 'start_date': '2026-10-01'}, 200)
acquisition.fetch_once = respond([{'event_id': 'fixture-event-1', 'headline': 'Fjord Works curtails potline', 'source_name': 'Example News',
                                   'link': 'https://news.example/fjord', 'publication_time': '2026-10-09T06:10:00', 'language': 'en'}])
call('permutable/capture', {'feed': 'event_headlines', 'mode': 'historical', 'start_date': '2026-10-01'}, 200)
acquisition.fetch_once = respond({'id': 'ALI_COM', 'name': 'Aluminium (fictional reference)'})
call('permutable/capture', {'feed': 'ticker_info'}, 200)
lead = client.get('/api/leads').json()['leads'][0]
call('leads/' + lead['id'] + '/decision', {'status': 'follow_up', 'reason': 'Check the operator update'}, 200)
call('leads/' + lead['id'] + '/decision', {'status': 'confirmed', 'reason': 'The operator update confirms the suspension',
                                          'primary_document_id': release['id'], 'observation_id': fact['id']}, 200)

call('research/policy', {}, 200)
now = datetime.now(timezone.utc)
call('research/events', {'external_key': 'fixture-owner-news', 'kind': 'corporate', 'title': 'Owner news', 'summary': 'Fictional',
                         'entity_ids': [company['id']], 'occurred_at': (now - timedelta(minutes=10)).isoformat(),
                         'known_at': (now - timedelta(minutes=10)).isoformat(), 'historical': True, 'source_reference': 'synthetic:fixture'})
call('research/events', {'external_key': 'fixture-plant-outage', 'kind': 'supply', 'title': 'Plant outage', 'summary': 'Fictional',
                         'entity_ids': [smelter['id']], 'occurred_at': (now - timedelta(minutes=5)).isoformat(), 'known_at': now.isoformat(),
                         'historical': True, 'source_reference': 'synthetic:fixture'})

case = call('investigations', {'title': 'Fjord curtailment', 'asset_ids': [smelter['id']]})
case = call('investigations/' + case['id'] + '/revisions', {'expected_version': 1, 'entry': {'kind': 'evidence', 'text': 'Operator update', 'document_id': release['id']}})
# The platform accepted any registered document here, including a vendor response.
call('investigations/' + case['id'] + '/revisions', {'expected_version': 2, 'entry': {'kind': 'note', 'text': 'Vendor event', 'document_id': events['document_ids'][0]}})

call('asset-map/locations', {'entity_id': smelter['id'], 'latitude': 60.1, 'longitude': 6.5, 'document_id': release['id'], 'precision': 'approximate', 'synthetic': True})
call('asset-map/dependencies', {'from_entity_id': refinery['id'], 'to_entity_id': smelter['id'], 'product': 'alumina', 'kind': 'material_supply',
                                'document_id': release['id'], 'valid_from': '2026-01-01', 'note': 'Fictional supply link', 'synthetic': True})
client.close()
app.state.engine.dispose()

with sqlite3.connect(database) as connection:
    (out / 'database.sql').write_text('\n'.join(connection.iterdump()) + '\n')
database.unlink()
print(json.dumps({'output': str(out), 'snapshots': sorted(p.name for p in (out / 'snapshots').iterdir())}))
