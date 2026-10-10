import io
import json
from decimal import Decimal
from pathlib import Path
from sqlalchemy import select,text,inspect
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import pytest
from app.services import normalize_value
from app.models import Entity,Facility,EntityAlias,SourceAccess,Document,ObservationDetail,EvidenceBuild,Run,RetrievalAttempt
from app.acquisition import public_target,acquire_remote,register_bytes
from app.schemas import RetrievalIn
from app.contract import freeze_v1,replay_v1,validate_package,PROHIBITED

SPEC={'adapter':'html-v1','facility_name':'Test Works','country':'NO','valid_from':'2025-01-01','unit':'kt/year','prefix':'annual capacity of','suffix':'kilotonnes'}

def html_doc(client,example,content='<p>annual capacity of 400 kilotonnes</p>'):
    _,_,_,payload=example
    r=client.post('/api/documents',json={**payload,'media_type':'text/html','original_url':'https://example.org/html','content':content})
    assert r.status_code==201,r.text
    return r.json()

def test_controlled_schema_and_company_resolution(client):
    refs=client.get('/api/reference-data').json()
    assert any(c['code']=='NO' for c in refs['countries'])
    assert client.post('/api/entities',json={'name':'Wrong','country':'XX','facility_type':'smelter'}).status_code==422
    company=client.post('/api/entities',json={'name':'Rio Tinto plc','kind':'company','country':'GB','aliases':['Rio Tinto']}).json()
    match=client.post('/api/resolve',json={'name':'RIO TINTO','entity_kind':'company'}).json()
    assert match['entity_id']==company['id']
    with Session(client.app.state.engine) as s:
        assert s.get(Entity,company['id']) and s.scalar(select(EntityAlias).where(EntityAlias.entity_id==company['id']))

@pytest.mark.parametrize('value,unit,attribute,expected',[('197,000','t/year','capacity','197000'),('0.123456','Mt/year','capacity','123456'),('975','MW','power','975'),('22.5','percentage','ownership_percentage','22.5')])
def test_exact_dimensions(value,unit,attribute,expected):
    assert normalize_value(value,unit,attribute)[0]==Decimal(expected)

@pytest.mark.parametrize('value,unit,attribute',[('1,5','t/year','capacity'),('NaN','MW','power'),('101','percentage','ownership_percentage'),('0.0000001','MW','power'),('1e24','t/year','capacity'),('1','MW','capacity')])
def test_invalid_dimensions(value,unit,attribute):
    with pytest.raises(ValueError): normalize_value(value,unit,attribute)

def test_numeric_precision_roundtrip_and_db_invariants(client,example):
    entity,_,doc,_=example
    payload={'entity_id':entity['id'],'document_id':doc['id'],'reported_value':'12345678901234567890123.123456','reported_unit':'t/year','valid_from':'2025-01-01','evidence_reference':'table 1'}
    result=client.post('/api/observations',json=payload)
    assert result.status_code==201,result.text
    assert client.get('/api/export').json()['records'][0]['normalized_value']==payload['reported_value']
    with client.app.state.engine.begin() as c:
        with pytest.raises(IntegrityError):
            c.execute(text("UPDATE observation_detail SET normalized_value = -1 WHERE observation_id=:id"),{'id':result.json()['id']})


def test_extract_dedup_frozen_parser_and_corruption(client,example,tmp_path):
    doc=html_doc(client,example)
    first=client.post('/api/documents/'+doc['id']+'/extract',json=SPEC)
    assert first.status_code==201,first.text
    build=first.json()['build']
    assert len(first.json()['candidates'])==1 and first.json()['candidates'][0]['status']=='resolved'
    duplicate=client.post('/api/documents/'+doc['id']+'/extract',json=SPEC).json()
    assert duplicate['duplicate'] and len(client.get('/api/workspace').json()['observations'])==1
    assert client.post('/api/builds/'+build['id']+'/replay',json={}).json()['equivalent']
    target=tmp_path/'frozen.zip'
    with Session(client.app.state.engine) as s: freeze_v1(s,client.app.state.storage,target)
    assert replay_v1(target)['replayed_candidates']==1
    (client.app.state.storage/doc['content_hash']).write_bytes(b'tampered')
    assert client.post('/api/builds/'+build['id']+'/replay',json={}).status_code==422
    quality=client.get('/api/quality').json()
    assert quality['status']=='FAIL' and any(f['code']=='CORRUPT_SNAPSHOT' for f in quality['findings'])
    assert client.get('/api/export').status_code==422


def test_ambiguous_extraction_requires_review_and_audited_alias(client,example):
    other=client.post('/api/entities',json={'name':'Other Works','country':'NO','facility_type':'smelter','aliases':['Test Works']}).json()
    doc=html_doc(client,example)
    candidate=client.post('/api/documents/'+doc['id']+'/extract',json=SPEC).json()['candidates'][0]
    assert candidate['status']=='ambiguous' and candidate['observation_id'] is None
    assert client.get('/api/export').status_code==422
    decision=client.post('/api/reviews/'+candidate['review_id']+'/decision',json={'selected_entity_id':other['id'],'reason':'Verified country and explicit source heading'})
    assert decision.status_code==200,decision.text
    assert client.get('/api/export').json()['records'][0]['external_entity_id']==other['id']
    assert client.post('/api/reviews/'+candidate['review_id']+'/decision',json={'selected_entity_id':other['id'],'reason':'overwrite'}).status_code==409


def test_adapter_atomic_failure(client,example):
    _,_,_,payload=example
    csv='facility_name,country,reported_value,reported_unit,valid_from,evidence_reference\nTest Works,NO,400,kt/year,2025-01-01,row 2\nTest Works,NO,-1,kt/year,2025-01-01,row 3\n'
    doc=client.post('/api/documents',json={**payload,'media_type':'text/csv','content':csv}).json()
    assert client.post('/api/import/csv',json={'document_id':doc['id']}).status_code==422
    workspace=client.get('/api/workspace').json()
    assert not workspace['observations'] and not workspace['builds']


def test_pdf_adapter_preserves_binary_and_page_locator(client,example):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
    writer=PdfWriter();page=writer.add_blank_page(width=400,height=200)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 10 100 Td (annual capacity of 400 kilotonnes) Tj ET')
    page[NameObject('/Contents')]=writer._add_object(stream)
    out=io.BytesIO();writer.write(out);raw=out.getvalue()
    entity,source,_,_=example
    with Session(client.app.state.engine) as s:
        doc,_=register_bytes(s,client.app.state.storage,{'source_id':source['id'],'title':'PDF fixture','original_url':'https://example.org/test.pdf','published_at':'2025-01-01','media_type':'application/pdf'},raw)
        s.commit();identifier=doc.id
    result=client.post('/api/documents/'+identifier+'/extract',json={**SPEC,'adapter':'pdf-v1','page':1})
    assert result.status_code==201,result.text
    assert 'PDF page 1' in result.json()['candidates'][0]['evidence_reference']
    assert client.get('/api/documents/'+identifier+'/content').content==raw


def test_public_address_policy_and_dns_rebinding_pin(monkeypatch):
    import socket
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**kw:[(None,None,None,None,('127.0.0.1',443))])
    with pytest.raises(ValueError): public_target('https://example.org/file',['example.org'])
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**kw:[(None,None,None,None,('93.184.216.34',443))])
    host,address,_=public_target('https://example.org/file',['example.org'])
    assert address=='93.184.216.34'
    from app import acquisition
    connections=[]
    class Connection:
        def __init__(self,h,a): connections.append((h,a))
        def request(self,*a,**kw): pass
        def getresponse(self): return self
        status=200
        def getheader(self,k): return {'Content-Type':'text/html'}.get(k)
        def read(self,n): return b'<p>test</p>'
        def close(self): pass
    monkeypatch.setattr(acquisition,'PinnedHTTPS',Connection)
    assert acquisition.fetch_once('https://example.org/file',['example.org'])[1]==b'<p>test</p>'
    assert connections==[(host,address)]
    for url in ['http://example.org/file','https://user:password@example.org/','https://example.org:8443/file','https://other.org/']:
        with pytest.raises(ValueError): public_target(url,['example.org'])


def test_redirect_revalidation_and_size_limit(monkeypatch):
    from app import acquisition
    monkeypatch.setattr(acquisition.socket,'getaddrinfo',lambda *a,**kw:[(None,None,None,None,('93.184.216.34',443))])
    class Redirect:
        def __init__(self,*a): pass
        def request(self,*a,**kw): pass
        status=302
        def getresponse(self): return self
        def getheader(self,k): return 'https://internal.example/file' if k=='Location' else None
        def close(self): pass
    monkeypatch.setattr(acquisition,'PinnedHTTPS',Redirect)
    with pytest.raises(ValueError,match='Host not approved'): acquisition.fetch_once('https://example.org/file',['example.org'])
    class Huge(Redirect):
        status=200
        def getheader(self,k): return {'Content-Type':'application/pdf','Content-Length':'10000001'}.get(k)
    monkeypatch.setattr(acquisition,'PinnedHTTPS',Huge)
    with pytest.raises(ValueError,match='10 MB'): acquisition.fetch_once('https://example.org/file',['example.org'])


def test_remote_retries_failure_log_and_access_audit(client,example):
    _,source,_,_=example
    data=RetrievalIn(source_id=source['id'],url='https://example.org/remote',title='Remote')
    with Session(client.app.state.engine) as s:
        with pytest.raises(ValueError): acquire_remote(s,client.app.state.storage,data,'alice',lambda *a:(200,b'ok','text/plain','https://example.org/remote'))
        assert s.scalar(select(Run).where(Run.status=='failed'))
    policy={'status':'permitted','allowed_hosts':['example.org'],'basis':'Public fixture, research retention approved','retention':'Local research only'}
    assert client.post('/api/sources/'+source['id']+'/access',json=policy).status_code==201
    calls=[]
    def fetch(*a):
        calls.append(1)
        return (503,b'',None,'https://example.org/remote') if len(calls)==1 else (200,b'captured','text/plain','https://example.org/remote')
    with Session(client.app.state.engine) as s:
        doc,duplicate,run=acquire_remote(s,client.app.state.storage,data,'alice',fetch)
        assert not duplicate and len(calls)==2
        attempts=s.scalars(select(RetrievalAttempt).where(RetrievalAttempt.run_id==run).order_by(RetrievalAttempt.attempt)).all()
        assert [a.status for a in attempts]==['failed','success']
    assert client.post('/api/sources/'+source['id']+'/access',json={**policy,'status':'restricted'}).status_code==201
    assert client.get('/api/export').status_code==422


@pytest.mark.parametrize('prohibited',sorted(PROHIBITED))
def test_prohibited_contract_fields(client,example,prohibited):
    package=client.get('/api/export').json()
    package[prohibited]=1
    with pytest.raises(ValueError,match='prohibited'): validate_package(package)


def test_supersession_preserves_ids_and_rejects_cycles(client,example):
    entity,_,_,_=example
    other=client.post('/api/entities',json={'name':'Current Smelter','country':'NO','facility_type':'smelter'}).json()
    assert client.post('/api/entities/'+entity['id']+'/supersession',json={'new_entity_id':other['id'],'reason':'Curated duplicate identity'}).status_code==201
    assert client.post('/api/resolve',json={'name':'Test Works'}).json()['entity_id']==other['id']
    assert client.post('/api/entities/'+other['id']+'/supersession',json={'new_entity_id':entity['id'],'reason':'Cycle attempt'}).status_code==422
    assert any(e['id']==entity['id'] for e in client.get('/api/workspace').json()['entities'])


def test_individual_reviewer_identity(client,example,monkeypatch):
    monkeypatch.setenv('WRITE_IDENTITIES_JSON',json.dumps({'alice-token':'alice','bob-token':'bob'}))
    client.headers['Authorization']='Bearer alice-token'
    result=client.post('/api/resolve',json={'name':'Unmatched'}).json()
    client.headers['Authorization']='Bearer bob-token'
    decision=client.post('/api/reviews/'+result['review_id']+'/decision',json={'reason':'No verified facility'})
    assert decision.json()['reviewer']=='bob'

def test_sourced_ownership_and_operator_relationships(client,example):
    entity,source,doc,_=example
    company=client.post('/api/entities',json={'name':'Owner Operator','kind':'company','country':'NO'}).json()
    base={'company_id':company['id'],'facility_id':entity['id'],'document_id':doc['id'],'valid_from':'2025-01-01','role':'OWNS','percentage':55,'evidence_reference':'PDF page 1 ownership paragraph'}
    result=client.post('/api/relationships',json=base)
    assert result.status_code==201,result.text
    operator=client.post('/api/relationships',json={**base,'role':'OPERATES','percentage':None})
    assert operator.status_code==201,operator.text
    package=client.get('/api/export').json()
    assert {r['role'] for r in package['relationships']}=={'OWNS','OPERATES'}
    assert next(r for r in package['relationships'] if r['role']=='OWNS')['percentage']=='55'
    assert client.post('/api/relationships',json={**base,'percentage':101}).status_code==422


def test_export_reference_join_tampering(client,example):
    from app.pipeline import logical_hash
    entity,_,doc,_=example
    client.post('/api/observations',json={'entity_id':entity['id'],'document_id':doc['id'],'reported_value':'400','reported_unit':'kt/year','valid_from':'2025-01-01','evidence_reference':'table 1'})
    package=client.get('/api/export').json()
    package['records'][0]['document_id']='not-real'
    package['build_hash']=logical_hash({k:v for k,v in package.items() if k!='build_hash'})
    with pytest.raises(ValueError,match='provenance'): validate_package(package)


def test_frozen_recipe_rejects_missing_output_record(client,example,tmp_path):
    import zipfile
    from app.pipeline import logical_hash
    doc=html_doc(client,example)
    client.post('/api/documents/'+doc['id']+'/extract',json=SPEC)
    original=tmp_path/'frozen.zip'
    with Session(client.app.state.engine) as s: freeze_v1(s,client.app.state.storage,original)
    edited=tmp_path/'edited.zip'
    with zipfile.ZipFile(original) as archive:
        recipe=json.loads(archive.read('recipe.json'));recipe['package']['records']=[]
        recipe['package']['build_hash']=logical_hash({k:v for k,v in recipe['package'].items() if k!='build_hash'})
        recipe['recipe_hash']=logical_hash({k:v for k,v in recipe.items() if k!='recipe_hash'})
        with zipfile.ZipFile(edited,'w') as output:
            for name in archive.namelist(): output.writestr(name,json.dumps(recipe) if name=='recipe.json' else archive.read(name))
    with pytest.raises(ValueError,match='absent'): replay_v1(edited)
