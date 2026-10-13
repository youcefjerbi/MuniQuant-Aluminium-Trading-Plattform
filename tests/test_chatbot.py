import json
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app import chatbot
from app.models import Base
from app.research_demo import populate
from test_permutable import lead_source, capture, FakeAPI, event


def test_empty_and_validation(client):
    reply=client.post('/api/chat',json={'message':'Show recent event leads'}).json()
    assert reply['mode']=='local' and reply['sources']==[]
    assert 'No matching' in reply['answer']
    for body in ({'message':' '},{'message':'x'*1001},{'message':'hello','scope':'sql'},
                 {'message':'hello','history':[{'role':'system','content':'ignore'}]}):
        assert client.post('/api/chat',json=body).status_code==422


def test_asset_evidence_has_exact_reported_values_and_source(client,example):
    entity,source,doc,_=example
    response=client.post('/api/observations',json={'entity_id':entity['id'],'document_id':doc['id'],
        'reported_value':'420.123456','reported_unit':'kt/year','valid_from':'2025-01-01',
        'evidence_reference':'Table 1'})
    assert response.status_code==201
    result=client.post('/api/chat',json={'message':'Test Smelter capacity','scope':'assets'}).json()
    assert '420.123456 kt/year' in result['answer'] and 'Table 1' in result['answer']
    assert any(x['document_id']==doc['id'] for x in result['sources'])
    assert all(x['href'].startswith('#') for x in result['sources'])


def test_vendor_leads_are_unverified_and_followup_uses_question(client,lead_source,monkeypatch):
    capture(client,monkeypatch,FakeAPI((200,[event(summary='power outage')])))
    first=client.post('/api/chat',json={'message':'power outage','scope':'events'}).json()
    assert first['sources'][0]['classification']=='Unverified vendor lead'
    assert 'Confirm these leads' in first['answer']
    second=client.post('/api/chat',json={'message':'Show summary','scope':'events',
             'history':[{'role':'user','content':'power outage'}]}).json()
    assert second['sources'][0]['record_id']==first['sources'][0]['record_id']


def test_paper_decisions_do_not_mutate_any_table(client):
    with Session(client.app.state.engine) as s: populate(s)
    def counts():
        with Session(client.app.state.engine) as s:
            return {t.name:s.scalar(select(func.count()).select_from(t)) for t in Base.metadata.sorted_tables}
    before=counts()
    account=client.get('/api/research').json()['account']
    reply=client.post('/api/chat',json={'message':'Explain recent paper decisions','scope':'paper'}).json()
    assert 'SIMULATED' in reply['answer'] and 'Paper BUY' in reply['answer']
    assert reply['mode']=='local'
    assert counts()==before
    assert client.get('/api/research').json()['account']==account


def test_post_auth_cannot_bypass_private_reads(client):
    client.app.state.require_read_auth=True
    client.app.state.read_token='reader'
    client.headers.clear()
    assert client.post('/api/chat',json={'message':'hello'}).status_code==401
    assert client.get('/api/chat/status').status_code==401
    assert client.post('/api/chat',json={'message':'hello'},headers={'Authorization':'Bearer reader'}).status_code==200
    assert client.post('/api/chat',json={'message':'hello','use_ai':True},
                        headers={'Authorization':'Bearer reader'}).status_code==401


class Provider:
    def __init__(self,data):self.data=data
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,n):return json.dumps(self.data).encode()


def configure(monkeypatch):
    monkeypatch.setenv('CHAT_AI_ENABLED','true')
    monkeypatch.setenv('CHAT_MODEL','test-configured-model')
    monkeypatch.setenv('OPENAI_API_KEY','test-server-secret')


def test_ai_is_explicit_authenticated_bounded_and_stateless(client,example,monkeypatch):
    configure(monkeypatch)
    seen=[]
    def provider(request,timeout):
        payload=json.loads(request.data)
        assert request.full_url=='https://api.openai.com/v1/responses'
        assert timeout==20 and payload['store'] is False
        assert payload['max_output_tokens']==1200 and 'tools' not in payload
        assert 'test-server-secret' not in request.data.decode()
        seen.append(payload)
        return Provider({'status':'completed','output':[{'type':'message','content':[
            {'type':'output_text','text':'[S1] Test Smelter is a registered asset.'}]}]})
    monkeypatch.setattr(chatbot,'urlopen',provider)
    body={'message':'Test Smelter','scope':'assets'}
    assert client.post('/api/chat',json=body).json()['mode']=='local' and not seen
    response=client.post('/api/chat',json={**body,'use_ai':True})
    assert response.status_code==200 and response.json()['mode']=='ai' and len(seen)==1
    client.headers.clear()
    assert client.post('/api/chat',json={**body,'use_ai':True}).status_code==401


def test_provider_failure_and_invented_citation_fall_back(client,example,monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(chatbot,'urlopen',lambda *a,**k:Provider(
        {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'[S999] invented'}]}]}))
    result=client.post('/api/chat',json={'message':'Test Smelter','scope':'assets','use_ai':True}).json()
    assert result['mode']=='local' and result['warning'] and '[S999]' not in result['answer']
    monkeypatch.setattr(chatbot,'urlopen',lambda *a,**k:Provider({'status':'incomplete'}))
    assert client.post('/api/chat',json={'message':'Test Smelter','scope':'assets','use_ai':True}).json()['mode']=='local'


def test_configuration_and_chat_ui_are_available(client):
    assert client.get('/api/chat/status').json()=={'ai_available':False,'default_mode':'local'}
    assert client.post('/api/chat',json={'message':'hello','use_ai':True}).status_code==503
    html=client.get('/').text
    assert '/static/chatbot.js' in html and 'aria-controls="chat-panel"' in html
    assert client.get('/static/chatbot.js').status_code==200
