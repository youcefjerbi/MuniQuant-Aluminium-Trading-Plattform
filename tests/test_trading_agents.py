"""API boundary and orchestration regression tests with a mocked provider only."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
import httpx
import pytest
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app import trading_agents as agents
from app.trading_agent_models import TradingAgentRun
from app.research_models import PaperAccount,PaperDecision

@pytest.fixture
def accepted_package(client,example):
    entity,source,document,_=example
    assert client.post('/api/sources/'+source['id']+'/access',json={'status':'permitted','allowed_hosts':['example.org'],'basis':'Synthetic software test source approval','retention':'Software test permitted retention'}).status_code==201
    assert client.post('/api/entities/'+entity['id']+'/evidence',json={'document_id':document['id'],'evidence_reference':'Synthetic software test identity locator','reason':'Software test identity supported by selected document'}).status_code==201
    response=client.post('/api/observations',json={'entity_id':entity['id'],'document_id':document['id'],'reported_value':'400','reported_unit':'kt/year','valid_from':'2025-01-01','evidence_reference':'Synthetic software-test source table'})
    assert response.status_code==201,response.text
    package=client.get('/api/export').json()
    agents.validate_package(package)
    assert package['records'][0]['quality_status']=='PASS'
    return package

@pytest.fixture
def configured(client,accepted_package,monkeypatch):
    monkeypatch.setattr(agents,'fetch_package',lambda:deepcopy(accepted_package))
    monkeypatch.setattr(agents,'status',lambda:{'enabled':True,'configured':True,'core_configured':True,'dependency_available':True,'reason':''})
    monkeypatch.setenv('TRADING_AGENTS_QUICK_MODEL','test-model');monkeypatch.setenv('TRADING_AGENTS_DEEP_MODEL','test-model')
    assert client.post('/api/research/policy',json={'enabled':True}).status_code==200
    assert client.post('/api/research/quotes',json={'external_key':'agent-test-price','price':'100','occurred_at':datetime.now(timezone.utc).isoformat(),'source_reference':'Synthetic software-test quote'}).status_code==201
    return {'request_key':'test-agent-key','instrument':'ALUMINIUM_DEMO','entity_ids':[accepted_package['entities'][0]['external_entity_id']],'mapping_rationale':'Explicit test mapping to aluminium capacity evidence','consent':True}


def result(action='BUY'):
    return {'action':action,'reasoning':'Stored accepted capacity supports this paper proposal [E1].','citations':['E1'],'reports':{'evidence':'Review accepted capacity [E1].'},'upstream_commit':agents.UPSTREAM_COMMIT}


def rehash(package):
    package['build_hash']=agents.logical_hash({k:v for k,v in package.items() if k!='build_hash'});return package


def test_core_api_fetch_authenticated_bounded_and_schema_validated(accepted_package,monkeypatch):
    monkeypatch.setenv('CORE_API_URL','https://core.example.invalid');monkeypatch.setenv('CORE_API_TOKEN','test-core-token')
    original=httpx.Client;seen=[]
    def handle(request):
        seen.append(request)
        return httpx.Response(200,json=accepted_package)
    monkeypatch.setattr(agents.httpx,'Client',lambda **kwargs:original(transport=httpx.MockTransport(handle),**kwargs))
    assert agents.fetch_package()==accepted_package
    assert str(seen[0].url)=='https://core.example.invalid/api/export'
    assert seen[0].headers['authorization']=='Bearer test-core-token'
    assert seen[0].headers['accept']=='application/json'

@pytest.mark.parametrize('url',['http://remote.example.org','https://name:secret@core.example.org','https://core.example.org?query=secret','https://core.example.org/#fragment'])
def test_unsafe_core_connection_rejected(monkeypatch,url):
    monkeypatch.setenv('CORE_API_URL',url)
    with pytest.raises(ValueError):agents.fetch_package()

@pytest.mark.parametrize('failure',['hash','duplicate','document','source','synthetic'])
def test_package_identity_hash_and_provenance_rejection(accepted_package,failure):
    package=deepcopy(accepted_package)
    if failure=='hash':package['records'][0]['reported_value']='999'
    elif failure=='duplicate':package['records'].append(deepcopy(package['records'][0]))
    elif failure=='document':package['documents'][0]['content_hash']='f'*64
    elif failure=='source':package['documents'][0]['source_id']='unknown-source'
    elif failure=='synthetic':package['records'][0]['synthetic']=True
    if failure!='hash':rehash(package)
    with pytest.raises(ValueError):agents.validate_package(package)


def test_provider_failure_creates_failed_run_without_paper_trade(client,configured,monkeypatch):
    def failed(*args):raise RuntimeError('Sensitive provider diagnostic must not appear in persisted public error')
    monkeypatch.setattr(agents,'execute_worker',failed)
    response=client.post('/api/trading-agents/runs',json=configured)
    assert response.status_code==202,response.text
    run=client.get('/api/trading-agents/runs/'+response.json()['id']).json()
    assert run['status']=='failed' and run['paper_decision_id'] is None
    assert 'Sensitive' not in run['error']
    with Session(client.app.state.engine) as s:assert s.scalar(select(func.count()).select_from(PaperDecision))==0


def test_success_is_proposal_only_request_retry_idempotent_and_key_conflict(client,configured,monkeypatch):
    calls=[]
    def worker(context,config,cancelled):calls.append(context);return result()
    monkeypatch.setattr(agents,'execute_worker',worker)
    first=client.post('/api/trading-agents/runs',json=configured)
    assert first.status_code==202,first.text
    identifier=first.json()['id'];completed=client.get('/api/trading-agents/runs/'+identifier).json()
    assert completed['status']=='completed' and completed['paper_decision_id'] is None
    second=client.post('/api/trading-agents/runs',json=configured)
    assert second.status_code==202 and second.json()['id']==identifier and len(calls)==1
    assert client.post('/api/trading-agents/runs',json={**configured,'mapping_rationale':'A different mapping must use a different key'}).status_code==409
    assert 'evidence' not in completed['inputs']
    assert completed['inputs']['evidence_refs'][0]['document_version_id']
    with Session(client.app.state.engine) as s:assert s.scalar(select(func.count()).select_from(PaperDecision))==0


def test_consent_disabled_config_and_write_auth_block_runs(client,configured,monkeypatch):
    assert client.post('/api/trading-agents/runs',json=configured,headers={'Authorization':''}).status_code==401
    denied=client.post('/api/trading-agents/runs',json={**configured,'consent':False})
    assert denied.status_code==422
    monkeypatch.setattr(agents,'status',lambda:{'enabled':False,'configured':True,'core_configured':True,'dependency_available':True,'reason':'Disabled test integration'})
    assert client.post('/api/trading-agents/runs',json=configured).status_code==422
    with Session(client.app.state.engine) as s:assert s.scalar(select(func.count()).select_from(TradingAgentRun))==0


def test_cancelled_queued_run_never_executes_and_actor_bound(client,configured,monkeypatch):
    monkeypatch.setattr(agents,'run_background',lambda *args:None)
    response=client.post('/api/trading-agents/runs',json=configured)
    identifier=response.json()['id']
    assert client.post('/api/trading-agents/runs',json={**configured,'request_key':'second-test-key'}).status_code==409
    assert client.post('/api/trading-agents/runs/'+identifier+'/cancel',headers={'Authorization':''}).status_code==401
    cancelled=client.post('/api/trading-agents/runs/'+identifier+'/cancel')
    assert cancelled.status_code==200 and cancelled.json()['status']=='cancelled'
    assert client.post('/api/trading-agents/runs/'+identifier+'/paper').status_code==409
    with Session(client.app.state.engine) as s:
        run=s.get(TradingAgentRun,identifier);assert run.active_slot is None
        with pytest.raises(ValueError):agents.cancel(s,run,'another-identity')


def test_paper_apply_rejects_changed_core_build_before_mutation(client,configured,accepted_package,monkeypatch):
    monkeypatch.setattr(agents,'execute_worker',lambda *args:result())
    identifier=client.post('/api/trading-agents/runs',json=configured).json()['id']
    changed=deepcopy(accepted_package);changed['build_hash']='0'*64
    monkeypatch.setattr(agents,'fetch_package',lambda:changed)
    response=client.post('/api/trading-agents/runs/'+identifier+'/paper')
    assert response.status_code==409 and 'changed' in response.json()['detail']
    with Session(client.app.state.engine) as s:
        assert s.scalar(select(func.count()).select_from(PaperDecision))==0
        assert s.get(PaperAccount,'paper').version==0

@pytest.mark.parametrize('guard',['synthetic','warning','missing_citation','unknown_citation','hidden_unknown','stale_capture'])
def test_evidence_and_citation_guards_prevent_executable_result(configured,accepted_package,client,monkeypatch,guard):
    package=deepcopy(accepted_package)
    if guard=='synthetic':package['records'][0]['synthetic']=True
    if guard=='warning':package['records'][0]['quality_status']='WARN'
    if guard=='stale_capture':package['records'][0]['retrieved_at']=(datetime.now(timezone.utc)-timedelta(days=366)).isoformat()
    monkeypatch.setattr(agents,'fetch_package',lambda:package)
    with Session(client.app.state.engine) as s:
        inputs,_=agents.prepare(s,agents.AgentRequest(**configured))
    proposal=result()
    if guard=='missing_citation':proposal['citations']=[]
    if guard=='unknown_citation':proposal['citations']=['E99'];proposal['reasoning']='Unknown fact [E99]'
    if guard=='hidden_unknown':proposal['reports']['risk']='Unprovided evidence [E99]'
    guarded=agents.guarded_result(proposal,inputs)
    assert not guarded['execution_allowed'] and guarded['guard_reasons']


def test_subprocess_environment_excludes_core_credentials_and_telemetry(monkeypatch):
    monkeypatch.setenv('CORE_API_TOKEN','secret-core');monkeypatch.setenv('DATABASE_URL','private-database');monkeypatch.setenv('LANGSMITH_API_KEY','private-telemetry');monkeypatch.setenv('OPENAI_BASE_URL','https://unwanted.example.org');monkeypatch.setenv('OPENAI_API_KEY','test-model-key');monkeypatch.setenv('TRADING_AGENTS_PROVIDER','openai')
    environment=agents.worker_environment()
    assert environment['OPENAI_API_KEY']=='test-model-key'
    assert environment['PYTHON_DOTENV_DISABLED']=='1'
    assert all(key not in environment for key in ('CORE_API_TOKEN','DATABASE_URL','LANGSMITH_API_KEY','OPENAI_BASE_URL'))


def test_explicit_apply_uses_shared_paper_ledger_once_and_retry_is_immutable(client,configured,monkeypatch):
    monkeypatch.setattr(agents,'execute_worker',lambda *args:result())
    identifier=client.post('/api/trading-agents/runs',json=configured).json()['id']
    first=client.post('/api/trading-agents/runs/'+identifier+'/paper')
    assert first.status_code==200,first.text
    assert first.json()['action']=='BUY' and first.json()['details']['fill']['mode']=='paper'
    # A retry returns the immutable recorded action even if today's Core later changes.
    monkeypatch.setattr(agents,'fetch_package',lambda:{'build_hash':'now-different'})
    second=client.post('/api/trading-agents/runs/'+identifier+'/paper')
    assert second.status_code==200 and second.json()['id']==first.json()['id']
    with Session(client.app.state.engine) as s:
        assert s.scalar(select(func.count()).select_from(PaperDecision))==1
        assert s.get(PaperAccount,'paper').version==1
    assert client.get('/api/research/performance').status_code==200


def test_worker_cancellation_kills_child_without_reading_provider_output(monkeypatch):
    processes=[]
    class Process:
        def __init__(self,*args,**kwargs):self.killed=False;self.waited=False;processes.append(self)
        def poll(self):return None if not self.killed else -9
        def kill(self):self.killed=True
        def wait(self,timeout):self.waited=True;return -9
    monkeypatch.setattr(agents.subprocess,'Popen',Process)
    with pytest.raises(ValueError,match='cancelled'):agents.execute_worker({}, {},lambda:True)
    assert processes[0].killed and processes[0].waited


def test_worker_hard_deadline_kills_child(monkeypatch):
    processes=[]
    class Process:
        def __init__(self,*args,**kwargs):self.killed=False;self.waited=False;processes.append(self)
        def poll(self):return None if not self.killed else -9
        def kill(self):self.killed=True
        def wait(self,timeout):self.waited=True;return -9
    ticks=iter([0,agents.MAX_SECONDS+1])
    monkeypatch.setattr(agents.subprocess,'Popen',Process)
    monkeypatch.setattr(agents.time,'monotonic',lambda:next(ticks))
    with pytest.raises(ValueError,match='timed out'):agents.execute_worker({}, {},lambda:False)
    assert processes[0].killed and processes[0].waited

@pytest.mark.parametrize('field,replacement',[('canonical_name','Spoofed asset identity'),('publisher','Spoofed evidence publisher'),('source_url','https://wrong-source.example.org'),('retrieved_at','2000-01-01T00:00:00+00:00')])
def test_rehashed_fact_metadata_must_match_core_registries(accepted_package,field,replacement):
    package=deepcopy(accepted_package)
    package['records'][0][field]=replacement
    rehash(package)
    with pytest.raises(ValueError):agents.validate_package(package)

@pytest.mark.parametrize('response_kind',['redirect','access_denied','invalid_json','oversize'])
def test_core_transport_failure_refuses_export_without_following_redirect(accepted_package,monkeypatch,response_kind):
    monkeypatch.setenv('CORE_API_URL','https://core.example.invalid')
    original=httpx.Client;calls=[]
    def handle(request):
        calls.append(request)
        if response_kind=='redirect':return httpx.Response(302,headers={'Location':'https://other.example.invalid'})
        if response_kind=='access_denied':return httpx.Response(401,json={'detail':'Private access diagnostic'})
        if response_kind=='invalid_json':return httpx.Response(200,content=b'not JSON')
        return httpx.Response(200,json=accepted_package)
    if response_kind=='oversize':monkeypatch.setattr(agents,'MAX_PACKAGE_BYTES',100)
    monkeypatch.setattr(agents.httpx,'Client',lambda **kwargs:original(transport=httpx.MockTransport(handle),**kwargs))
    with pytest.raises(ValueError) as error:agents.fetch_package()
    assert len(calls)==1 and 'Private access diagnostic' not in str(error.value)
