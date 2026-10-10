"""Requirement-driven UAT, ambiguity, conflict, load and concurrent-write checks."""
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select,text
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from app.models import Entity
from app.domain import sync_entity
from app.services import resolve

def test_fifty_difficult_names_never_trust_ambiguity(client):
    benchmark=json.loads(Path('tests/fixtures/ambiguity-50.json').read_text())
    for entity in benchmark['entities']:
        response=client.post('/api/entities',json=entity)
        assert response.status_code==201,response.text
    with Session(client.app.state.engine) as session:
        for case in benchmark['cases']:
            result=resolve(session,case['raw_name'],case['country'],case['kind'])
            assert result['status']==case['expected_status'],case
            if case['expected_status']=='resolved':
                assert result['candidates'][0]['name']==case['expected_name'],case
            else: assert result['entity_id'] is None,case

def test_larger_dataset_csv_and_pagination(client,example):
    _,_,_,payload=example
    with Session(client.app.state.engine) as session:
        for index in range(500):
            entity=Entity(name=f'Load Fixture {index:03}',kind='facility',country='NO',facility_type='smelter',commodity='aluminium',region='',aliases=[])
            session.add(entity);session.flush();sync_entity(session,entity,'load-fixture')
        session.commit()
    csv='facility_name,country,reported_value,reported_unit,valid_from,evidence_reference\n'+''.join(f'Load Fixture {index:03},NO,{100+index},kt/year,2025-01-01,synthetic row {index+2}\n' for index in range(500))
    doc=client.post('/api/documents',json={**payload,'original_url':'https://example.org/load','media_type':'text/csv','content':csv}).json()
    imported=client.post('/api/import/csv',json={'document_id':doc['id']})
    assert imported.status_code==200,imported.text
    assert imported.json()['inserted']==500
    page=client.get('/api/records/observations?offset=450&limit=50').json()
    assert page['total']==500 and len(page['records'])==50
    assert len(client.get('/api/export').json()['records'])==500

def test_overlapping_capacity_conflicts_and_historical_status(client,example):
    entity,_,doc,_=example
    base={'entity_id':entity['id'],'document_id':doc['id'],'valid_from':'2025-01-01','valid_to':'2025-12-31','evidence_reference':'synthetic conflict fixture'}
    for value,unit in [('400','kt/year'),('0.4','Mt/year'),('410000','t/year')]:
        assert client.post('/api/observations',json={**base,'reported_value':value,'reported_unit':unit}).status_code==201
    assert client.post('/api/observations',json={**base,'attribute':'status','reported_value':'closed','reported_unit':'status'}).status_code==201
    assert client.post('/api/observations',json={**base,'valid_from':'2026-01-01','valid_to':None,'attribute':'status','reported_value':'operating','reported_unit':'status'}).status_code==201
    findings=client.get('/api/quality').json()['findings']
    assert sum(f['code']=='CONFLICTING_OBSERVATIONS' for f in findings)==2
    assert len(client.get('/api/export').json()['records'])==5
    with client.app.state.engine.begin() as connection:
        import pytest
        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            connection.execute(text("UPDATE observations SET reported_unit='MW' WHERE attribute='capacity'"))

def test_failed_parser_manifest_and_new_identity_review(client,example):
    _,_,_,payload=example
    doc=client.post('/api/documents',json={**payload,'content':'no capacity here','media_type':'text/html'}).json()
    spec={'adapter':'html-v1','facility_name':'New Verified Site','country':'AU','valid_from':'2025-01-01','prefix':'capacity','suffix':'tonnes','unit':'t/year'}
    assert client.post('/api/documents/'+doc['id']+'/extract',json=spec).status_code==422
    assert any(r['status']=='failed' and r['manifest'].get('document_id')==doc['id'] for r in client.get('/api/workspace').json()['runs'])
    doc=client.post('/api/documents',json={**payload,'content':'capacity 500 tonnes','media_type':'text/html'}).json()
    candidate=client.post('/api/documents/'+doc['id']+'/extract',json=spec).json()['candidates'][0]
    entity=client.post('/api/entities',json={'name':'New Verified Site','country':'AU','facility_type':'smelter'}).json()
    review='/api/reviews/'+candidate['review_id']
    assert client.post(review+'/candidates',json={'entity_id':entity['id'],'reason':'Registered after checking the original facility source'}).status_code==201
    assert client.post(review+'/decision',json={'selected_entity_id':entity['id'],'reason':'Verified source country and canonical site'}).status_code==200
    assert client.get('/api/export').json()['records'][0]['external_entity_id']==entity['id']

def test_concurrent_import_has_one_build_and_observation(client,example):
    _,_,_,payload=example
    csv='facility_name,country,reported_value,reported_unit,valid_from,evidence_reference\nTest Works,NO,400,kt/year,2025-01-01,row 2\n'
    doc=client.post('/api/documents',json={**payload,'media_type':'text/csv','content':csv}).json()
    def submit(_):
        with TestClient(client.app) as parallel:
            return parallel.post('/api/import/csv',json={'document_id':doc['id']},headers={'Authorization':'Bearer test-token'})
    with ThreadPoolExecutor(max_workers=2) as pool: responses=list(pool.map(submit,range(2)))
    assert all(response.status_code in (200,409) for response in responses),[r.text for r in responses]
    assert any(response.status_code==200 for response in responses)
    workspace=client.get('/api/workspace').json()
    assert len(workspace['builds'])==1 and len(workspace['observations'])==1

def test_legacy_data_migration_preserves_source_and_exact_reported_fact(client,example):
    from alembic import command
    from alembic.config import Config
    entity,_,doc,_=example
    obs=client.post('/api/observations',json={'entity_id':entity['id'],'document_id':doc['id'],'reported_value':'12345678901234567890123.123456','reported_unit':'t/year','valid_from':'2025-01-01','evidence_reference':'synthetic exact precision fixture'}).json()
    command.downgrade(Config('alembic.ini'),'5fa787f9511c')
    command.upgrade(Config('alembic.ini'),'head')
    command.check(Config('alembic.ini'))
    package=client.get('/api/export').json()
    assert package['records'][0]['record_id']==obs['id']
    assert package['records'][0]['normalized_value']=='12345678901234567890123.123456'
    assert package['records'][0]['content_hash']==doc['content_hash']
    assert client.post('/api/resolve',json={'name':'TEST WORKS','country':'NO'}).json()['entity_id']==entity['id']

def test_separate_read_only_authorization(client):
    client.app.state.require_read_auth=True
    client.app.state.read_token='read-only-fixture'
    assert client.get('/api/health',headers={'Authorization':''}).status_code==200
    assert client.get('/api/workspace',headers={'Authorization':''}).status_code==401
    assert client.get('/api/workspace',headers={'Authorization':'Bearer read-only-fixture'}).status_code==200
    assert client.post('/api/entities',json={'name':'Unauthorized','country':'NO','facility_type':'smelter'},headers={'Authorization':'Bearer read-only-fixture'}).status_code==401

def test_independent_consumer_understands_export_without_database(client,example,tmp_path):
    import runpy
    entity,_,doc,_=example
    assert client.post('/api/observations',json={'entity_id':entity['id'],'document_id':doc['id'],'reported_value':'0.4','reported_unit':'Mt/year','valid_from':'2025-01-01','evidence_reference':'source table 1'}).status_code==201
    package=tmp_path/'evidence.json';package.write_text(json.dumps(client.get('/api/export').json()))
    consumer=runpy.run_path('scripts/consume_evidence.py')['consume']
    result=consumer(package,'app/evidence-v1.schema.json')
    assert result['records'][0]['value']=='400000'
    assert result['records'][0]['locator']=='source table 1'
    assert result['records'][0]['content_hash']==doc['content_hash']

def test_status_csv_frozen_replay_and_bad_status_rejection(client,example,tmp_path):
    from app.contract import freeze_v1,replay_v1
    _,_,_,payload=example
    csv='facility_name,country,reported_value,reported_unit,valid_from,valid_to,attribute,evidence_reference\nTest Works,NO,closed,status,2024-01-01,2024-12-31,status,row 2\nTest Works,NO,operating,status,2025-01-01,,status,row 3\n'
    doc=client.post('/api/documents',json={**payload,'media_type':'text/csv','content':csv}).json()
    response=client.post('/api/import/csv',json={'document_id':doc['id']})
    assert response.status_code==200,response.text
    with Session(client.app.state.engine) as session: freeze_v1(session,client.app.state.storage,tmp_path/'statuses.zip')
    assert replay_v1(tmp_path/'statuses.zip')['replayed_candidates']==2
    doc=client.post('/api/documents',json={**payload,'media_type':'text/csv','content':csv.replace('closed,status','invented,status')}).json()
    assert client.post('/api/import/csv',json={'document_id':doc['id']}).status_code==422
