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


def stream_frames(response):
    return [(frame.split('\n')[0][7:], json.loads(frame.split('\ndata: ')[1]))
            for frame in response.text.strip().split('\n\n')]


def test_local_stream_transport_and_private_auth(client):
    client.app.state.require_read_auth=True
    client.app.state.read_token='reader'
    client.headers.clear()
    body={'message':'hello'}
    assert client.post('/api/chat/stream',json=body).status_code==401
    headers={'Authorization':'Bearer reader'}
    response=client.post('/api/chat/stream',json=body,headers=headers)
    assert response.headers['content-type'].startswith('text/event-stream')
    assert response.headers['cache-control']=='no-store'
    frames=stream_frames(response)
    assert frames[0][0]=='meta' and frames[-1][0]=='done'
    assert len([f for f in frames if f[0]=='delta'])>5
    assert ''.join(p['text'] for k,p in frames if k=='delta')==frames[-1][1]['answer']
    assert client.post('/api/chat/stream',json={**body,'use_ai':True},headers=headers).status_code==401


def test_ai_stream_incremental_and_bad_citation_reset(client,example,monkeypatch):
    configure(monkeypatch)
    async def deltas(*args):
        yield '[S1] '
        yield 'Test Smelter.'
    monkeypatch.setattr(chatbot,'provider_deltas',deltas)
    body={'message':'Test Smelter','scope':'assets','use_ai':True}
    frames=stream_frames(client.post('/api/chat/stream',json=body))
    assert [p['text'] for k,p in frames if k=='delta']==['[S1] ','Test Smelter.']
    assert 'pending' in next(p['warning'] for k,p in frames if k=='state')
    assert frames[-1][1]['mode']=='ai'
    async def invalid(*args):
        yield '[S999] invented'
    monkeypatch.setattr(chatbot,'provider_deltas',invalid)
    frames=stream_frames(client.post('/api/chat/stream',json=body))
    assert any(k=='reset' for k,p in frames)
    assert frames[-1][1]['mode']=='local' and '[S999]' not in frames[-1][1]['answer']


def test_provider_stream_protocol_and_cancellation(monkeypatch):
    import asyncio
    configure(monkeypatch)
    closed=[]
    class Response:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):closed.append('response')
        def raise_for_status(self):pass
        async def aiter_lines(self):
            yield 'event: response.output_text.delta'
            yield 'data: '+json.dumps({'type':'response.output_text.delta','delta':'[S1] '})
            yield 'data: '+json.dumps({'type':'response.output_text.delta','delta':'asset'})
            yield 'data: '+json.dumps({'type':'response.completed','response':{'status':'completed'}})
    class Client:
        def __init__(self,**kwargs):assert kwargs['timeout']==20
        async def __aenter__(self):return self
        async def __aexit__(self,*args):closed.append('client')
        def stream(self,method,url,**kwargs):
            assert method=='POST' and url=='https://api.openai.com/v1/responses'
            assert kwargs['json']['stream'] and kwargs['json']['store'] is False
            return Response()
    monkeypatch.setattr(chatbot.httpx,'AsyncClient',Client)
    async def run():
        generator=chatbot.provider_deltas(chatbot.ChatIn(message='asset'),'assets',[])
        assert await anext(generator)=='[S1] '
        await generator.aclose()
        assert closed==['response','client']
        assert [x async for x in chatbot.provider_deltas(chatbot.ChatIn(message='asset'),'assets',[])]==['[S1] ','asset']
    asyncio.run(run())


def test_provider_failure_and_cancel_release_slots(monkeypatch):
    import asyncio
    async def failure(*args):
        yield '[S1] partial'
        raise ValueError('incomplete')
    monkeypatch.setattr(chatbot,'provider_deltas',failure)
    source={'citation':'S1','title':'asset','as_of':None,'excerpt':'stored'}
    async def run():
        data=chatbot.ChatIn(message='asset',use_ai=True)
        frames=[x async for x in chatbot.stream_answer(data,'assets',[source])]
        assert any('event: reset' in x for x in frames)
        iterator=chatbot.stream_answer(data,'assets',[source])
        await anext(iterator) # metadata
        await anext(iterator) # draft state after acquiring slot
        await iterator.aclose()
        assert chatbot.SLOTS.acquire(blocking=False)
        assert chatbot.SLOTS.acquire(blocking=False)
        chatbot.SLOTS.release();chatbot.SLOTS.release()
    asyncio.run(run())


def test_stream_ui_uses_safe_text_and_cancellation(client):
    script=client.get('/static/chatbot.js').text
    assert 'getReader()' in script and 'TextDecoder' in script
    assert 'body.textContent+=payload.text' in script and 'innerHTML' not in script
    assert 'Stop response' in script and 'controller.abort()' in script
    assert 'Partial draft discarded' in script


def test_disconnect_cancels_provider_and_releases_slot(monkeypatch):
    import asyncio
    entered=asyncio.Event()
    stopped=[]
    async def waiting(*args):
        try:
            entered.set()
            await asyncio.Event().wait()
            yield 'unreachable'
        finally:
            stopped.append(True)
    monkeypatch.setattr(chatbot,'provider_deltas',waiting)
    async def run():
        source={'citation':'S1','title':'asset','as_of':None,'excerpt':'stored'}
        async def consume():
            async for _ in chatbot.stream_answer(chatbot.ChatIn(message='asset',use_ai=True),'assets',[source]):
                pass
        task=asyncio.create_task(consume())
        await entered.wait()
        task.cancel()
        try:await task
        except asyncio.CancelledError:pass
        assert stopped==[True]
        assert chatbot.SLOTS.acquire(blocking=False)
        assert chatbot.SLOTS.acquire(blocking=False)
        chatbot.SLOTS.release();chatbot.SLOTS.release()
    asyncio.run(run())


def test_stop_while_delta_is_displayed_closes_provider_immediately(monkeypatch):
    import asyncio
    stopped=[]
    async def paused(*args):
        try:
            yield '[S1] first'
            yield ' second'
        finally:
            stopped.append(True)
    monkeypatch.setattr(chatbot,'provider_deltas',paused)
    async def run():
        source={'citation':'S1','title':'asset','as_of':None,'excerpt':'stored'}
        iterator=chatbot.stream_answer(chatbot.ChatIn(message='asset',use_ai=True),'assets',[source])
        await anext(iterator)
        await anext(iterator)
        assert 'event: delta' in await anext(iterator)
        await iterator.aclose()
        assert stopped==[True]
    asyncio.run(run())
