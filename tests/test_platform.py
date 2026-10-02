import hashlib
import json
from pathlib import Path
import pytest
import muniquant_core as core
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.models import Review
from sqlalchemy.orm import Session

def observation(e,d,**kw):
    return dict(entity_id=e['id'],document_id=d['id'],reported_value='400',reported_unit='kt/year',valid_from='2025-01-01',evidence_reference='page 4',**kw)

def test_native_conversion_and_unicode_distance():
    assert core.normalize_capacity(.5,'Mt/year')==500000
    assert core.normalize_capacity(400,'kt/year')==400000
    assert core.name_distance('café','cafe')==1
    for value,unit in [(-1,'kt/year'),(float('nan'),'kt/year'),(1,'MW'),(float('inf'),'t/year'),(1e308,'Mt/year')]:
        with pytest.raises(ValueError): core.normalize_capacity(value,unit)

def test_auth_and_health(client):
    assert client.get('/api/health').json()['native_core']=='0.1.0'
    client.headers.clear()
    assert client.post('/api/entities',json={'name':'No','country':'NO','facility_type':'smelter'}).status_code==401

def test_evidence_dedup_and_version(client,example):
    e,s,d,payload=example
    same=client.post('/api/documents',json=payload).json()
    assert same['id']==d['id'] and same['duplicate']
    payload['content']='Revised capacity: 420 kt/year'
    revised=client.post('/api/documents',json=payload).json()
    assert revised['version']==2 and revised['content_hash']!=d['content_hash']
    assert client.get('/api/documents/'+d['id']+'/content').content==b'Capacity: 400 kt/year'
    assert len(client.get('/api/workspace').json()['documents'])==2

def test_historical_observations_and_quality(client,example):
    e,s,d,_=example
    first=observation(e,d)
    assert client.post('/api/observations',json=first).json()['normalized_value']==400000
    second={**first,'reported_value':'800','valid_from':'2026-01-01'}
    response=client.post('/api/observations',json=second)
    assert response.status_code==201 and response.json()['quality_status']=='WARN'
    assert len(client.get('/api/workspace').json()['observations'])==2

@pytest.mark.parametrize('change',[{'reported_value':'-3'},{'reported_value':'NaN'},{'reported_unit':'MW'},{'document_id':'missing'},{'valid_to':'2020-01-01'},{'entity_id':'missing'}])
def test_reject_bad_observations(client,example,change):
    e,s,d,_=example
    r=client.post('/api/observations',json={**observation(e,d),**change})
    assert r.status_code==422,r.text
    assert not client.get('/api/workspace').json()['observations']

def test_resolution_ambiguity_and_review_audit(client,example):
    e,_,_,_=example
    assert client.post('/api/resolve',json={'name':' TEST works '}).json()['entity_id']==e['id']
    e2=client.post('/api/entities',json={'name':'Second Smelter','country':'NO','facility_type':'smelter','aliases':['Test Works']}).json()
    result=client.post('/api/resolve',json={'name':'Test Works'}).json()
    assert result['status']=='ambiguous' and result['entity_id'] is None
    url='/api/reviews/'+result['review_id']+'/decision'
    assert client.post(url,json={'selected_entity_id':'not-a-candidate','reason':'test'}).status_code==422
    assert client.post(url,json={'selected_entity_id':e2['id'],'reason':'Verified report and country'}).status_code==200
    assert client.post(url,json={'selected_entity_id':e['id'],'reason':'overwrite'}).status_code==409
    workspace=client.get('/api/workspace').json()
    assert workspace['reviews'][0]['reviewer']=='local-curator'
    assert any(a['action']=='review_decision' for a in workspace['audit'])

def test_csv_atomicity_and_idempotency(client,example):
    e,s,d,payload=example
    header='facility_name,country,reported_value,reported_unit,valid_from,evidence_reference\n'
    row='Test Works,NO,400,kt/year,2025-01-01,row 2\n'
    data={**payload,'media_type':'text/csv','content':header+row+'Unknown,NO,10,kt/year,2025-01-01,row 3\n'}
    bad=client.post('/api/documents',json=data).json()
    assert client.post('/api/import/csv',json={'document_id':bad['id']}).status_code==422
    assert not client.get('/api/workspace').json()['observations']
    data['content']=header+row
    good=client.post('/api/documents',json=data).json()
    assert client.post('/api/import/csv',json={'document_id':good['id']}).json()['inserted']==1
    assert client.post('/api/import/csv',json={'document_id':good['id']}).json()['inserted']==0
    assert client.get('/api/workspace').json()['observations'][0]['parser_version']=='capacity-csv-v1'

def test_export_determinism_and_corruption_detection(client,example):
    e,s,d,_=example
    client.post('/api/observations',json=observation(e,d))
    first=client.get('/api/export')
    assert first.status_code==200,first.text
    assert first.json()==client.get('/api/export').json()
    package=first.json();expected=package.pop('build_hash')
    assert hashlib.sha256(json.dumps(package,sort_keys=True,separators=(',',':')).encode()).hexdigest()==expected
    (client.app.state.storage/d['content_hash']).write_text('tampered')
    assert client.get('/api/export').status_code==422
    assert client.get('/api/documents/'+d['id']+'/content').status_code==409

def test_market_contract_identity_and_currency(client,example):
    _,_,d,_=example
    payload={'instrument':'SHFE_AL_ACTIVE','exchange':'SHFE','market':'futures','region':'China','price_type':'settlement','value':'20500.25','currency':'CNY','unit':'tonne','effective_at':'2025-10-02T16:00:00+08:00','data_status':'reported','document_id':d['id'],'evidence_reference':'table 1'}
    assert client.post('/api/market',json=payload).status_code==422
    payload.update(contract_code='AL2512',prompt_date='2025-12-15')
    r=client.post('/api/market',json=payload)
    assert r.status_code==201,r.text
    assert r.json()['value']=='20500.25' and r.json()['currency']=='CNY'
    assert client.post('/api/market',json={**payload,'effective_at':'2025-10-02T16:00:00'}).status_code==422

def test_access_restriction_and_failed_run(client,example):
    _,_,_,payload=example
    s=client.post('/api/sources',json={'name':'Restricted','publisher':'Exchange','source_type':'exchange','url':'https://example.org','access_status':'restricted'}).json()
    assert client.post('/api/documents',json={**payload,'source_id':s['id']}).status_code==422
    assert any(r['status']=='failed' for r in client.get('/api/workspace').json()['runs'])

def test_database_foreign_keys(client):
    with pytest.raises(IntegrityError):
        with client.app.state.engine.begin() as conn:
            conn.execute(text("INSERT INTO relationships (id,company_id,facility_id,role,valid_from,document_id) VALUES ('x','none','none','OWNS','2025-01-01','none')"))

def test_static_ui_and_no_inline_scripts(client):
    r=client.get('/')
    assert r.status_code==200 and 'Aluminium workspace' in r.text
    assert "script-src 'self'" in r.headers['Content-Security-Policy']
    assert client.get('/static/app.js').status_code==200

def test_frozen_bundle_restore(client,example,tmp_path):
    from app.bundle import freeze,restore,load_verified
    from app.db import make_engine
    from app.models import Base
    from app.services import export_package
    e,_,d,_=example
    client.post('/api/observations',json=observation(e,d))
    target=tmp_path/'frozen.zip'
    with Session(client.app.state.engine) as s:
        original=export_package(s,client.app.state.storage)
        freeze(s,client.app.state.storage,target)
    assert load_verified(target)[0]==original
    engine=make_engine('sqlite:///'+str(tmp_path/'restored.db'))
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        restore(s,tmp_path/'restored-snapshots',target)
        assert export_package(s,tmp_path/'restored-snapshots')==original
        with pytest.raises(ValueError): restore(s,tmp_path/'restored-snapshots',target)
    engine.dispose()
