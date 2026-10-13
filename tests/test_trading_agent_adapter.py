"""Real upstream factories with a fake model; no paid calls or vendor data."""
import copy
import importlib.util
import socket
import subprocess
import sys
import pytest
from app import trading_agent_adapter as adapter


@pytest.fixture
def context():
    return {'instrument':'ALUMINIUM','as_of':'2026-10-13T12:00:00Z','mapping_rationale':'Explicit plant supply linkage; hypothesis only',
            'evidence':{'package_version':'1.0.0','build_hash':'a'*64,'records':[{'citation':'E1','entity_id':'plant-1','observation_id':'obs-1','document_version_id':'doc-1','reported_value':'400','reported_unit':'kt/year'}],
                        'entities':[{'id':'plant-1','name':'Synthetic Plant'}],'documents':[{'id':'doc-1','content_hash':'b'*64}], 'quality':{'warnings':1}},
            'quotes':[{'id':'q1','price':'2500','observed_at':'2026-10-13T11:55:00Z'}], 'portfolio':{'cash':'10000','quantity':'0'}}


CONFIG={'provider':'openai','quick_model':'configured-test','deep_model':'configured-test'}


def fake_model(citation='E1', structured=True, rating='Hold'):
    from langchain_core.messages import AIMessage
    class Model:
        calls=[]
        def invoke(self,messages):
            self.calls.append(messages)
            assert messages[0].content.startswith('This is an aluminium PAPER')
            return AIMessage(content='Evidence limited ['+citation+']; paper hypothesis only.')
        def with_structured_output(self,schema):
            if not structured: raise NotImplementedError('No schema')
            parent=self
            class Bound:
                def invoke(self,messages):
                    parent.calls.append(messages)
                    if schema.__name__=='ResearchPlan':
                        return schema(recommendation='Hold',rationale='Sparse ['+citation+']',strategic_actions='Wait')
                    if schema.__name__=='TraderProposal':
                        return schema(action='Hold',reasoning='Sparse ['+citation+']')
                    return schema(rating=rating,executive_summary='Do not act ['+citation+']',investment_thesis='Sparse plant evidence ['+citation+']')
            return Bound()
    return Model()


def require_upstream(monkeypatch):
    if importlib.util.find_spec('tradingagents') is None:
        pytest.skip('Pinned optional TradingAgents dependency not installed')
    monkeypatch.setenv('PYTHON_DOTENV_DISABLED','1')
    # No sockets, including model transport and data vendors, are permitted in fake-model graph tests.
    def denied(*args,**kwargs):raise AssertionError('External network attempted')
    monkeypatch.setattr(socket.socket,'connect',denied)
    import tradingagents
    assert tradingagents.__version__==adapter.UPSTREAM_VERSION


def test_actual_upstream_graph_evidence_only(context,monkeypatch):
    require_upstream(monkeypatch)
    before=copy.deepcopy(context)
    quick,deep=fake_model(),fake_model()
    result=adapter._run_graph(context,CONFIG,quick,deep)
    assert result['action']=='HOLD' and result['rating']=='Hold' and result['citations']==['E1']
    assert result['upstream_commit']==adapter.UPSTREAM_COMMIT
    assert len(quick.calls)==6 and len(deep.calls)==2
    assert context==before
    assert set(result['reports'])=={'evidence','quotes','research_debate','research_plan','trader','risk_debate','portfolio'}
    assert 'Bull Analyst:' in result['reports']['research_debate']
    assert 'Bear Analyst:' in result['reports']['research_debate']


def test_upstream_invalid_citation_and_freetext_are_rejected(context,monkeypatch):
    require_upstream(monkeypatch)
    with pytest.raises(adapter.AgentAdapterError,match='citations'):
        adapter._run_graph(context,CONFIG,fake_model('E999'),fake_model('E999'))
    with pytest.raises(adapter.AgentAdapterError,match='Typed final'):
        adapter._run_graph(context,CONFIG,fake_model(structured=False),fake_model(structured=False))


@pytest.mark.parametrize('change',[{'mapping_rationale':''},{'as_of':'not-a-date'},{'evidence':{'package_version':'0.1.0-draft'}},{'instrument':''}])
def test_invalid_context_before_optional_import(context,change):
    context.update(change)
    with pytest.raises(adapter.AgentAdapterError):adapter.run_evidence_agents(context,CONFIG)


def test_missing_isolation_and_provider_fail_closed(context,monkeypatch):
    monkeypatch.delenv('PYTHON_DOTENV_DISABLED',raising=False)
    with pytest.raises(adapter.AgentAdapterError,match='isolated'):adapter.run_evidence_agents(context,CONFIG)
    with pytest.raises(adapter.AgentAdapterError,match='Unsupported'):adapter._validate(context,{**CONFIG,'provider':'web-agent'})
    with pytest.raises(adapter.AgentAdapterError,match='local'):adapter._validate(context,{**CONFIG,'provider':'ollama','base_url':'https://example.com/v1'})


def test_worker_sanitizes_failure_protocol():
    result=subprocess.run([sys.executable,'-m','app.trading_agent_worker'],input='{"unexpected":"secret-provider-payload"}',text=True,capture_output=True,check=True)
    assert result.stderr==''
    assert result.stdout=='{"error": "Evidence-agent analysis unavailable; no paper action proposed."}\n'
    assert 'secret' not in result.stdout


@pytest.mark.parametrize('rating,action',[('Buy','BUY'),('Overweight','BUY'),('Hold','HOLD'),('Underweight','SELL'),('Sell','SELL')])
def test_exact_upstream_structured_rating_mapping(context,monkeypatch,rating,action):
    require_upstream(monkeypatch)
    result=adapter._run_graph(context,CONFIG,fake_model(),fake_model(rating=rating))
    assert result['rating']==rating and result['action']==action


def test_public_adapter_checks_pin_and_explicit_provider_configuration(context,monkeypatch):
    require_upstream(monkeypatch)
    from tradingagents.llm_clients import factory
    seen=[]
    def client(provider,model,**kwargs):
        seen.append((provider,model,kwargs))
        class Client:
            def get_llm(self):return fake_model()
        return Client()
    monkeypatch.setattr(factory,'create_llm_client',client)
    assert adapter.run_evidence_agents(context,{**CONFIG,'max_tokens':9000,'request_timeout':99})['action']=='HOLD'
    assert len(seen)==2
    assert all(item[2]=={'base_url':'https://api.openai.com/v1','timeout':30,'max_retries':0,'max_tokens':1600} for item in seen)



def test_native_openai_requests_disable_provider_storage(context,monkeypatch):
    require_upstream(monkeypatch)
    monkeypatch.setenv('OPENAI_API_KEY','test-only-placeholder-key')
    def inspect(context,config,quick,deep):
        for model in (quick,deep):
            assert model.store is False
            assert model._get_request_payload('test-only prompt')['store'] is False
        return {'action':'HOLD'}
    monkeypatch.setattr(adapter,'_run_graph',inspect)
    assert adapter.run_evidence_agents(context,{**CONFIG,'quick_model':'gpt-4.1-mini','deep_model':'gpt-4.1-mini'})['action']=='HOLD'



def test_large_core_evidence_is_transient_not_persisted_in_reports(context,monkeypatch):
    require_upstream(monkeypatch)
    context['evidence']['records'][0]['source_excerpt']='RAW_CORE_ONLY_SENTINEL '+('industrial observation '*1400)
    quick,deep=fake_model(),fake_model()
    result=adapter._run_graph(context,CONFIG,quick,deep)
    assert len(str(context['evidence']))>adapter.MAX_REPORT_CHARS
    import json
    provenance=json.loads(result['reports']['evidence'])
    assert provenance=={'package_version':'1.0.0','build_hash':'a'*64,'citations':['E1']}
    assert 'RAW_CORE_ONLY_SENTINEL' not in json.dumps(result)
    assert any('RAW_CORE_ONLY_SENTINEL' in str(messages) for messages in quick.calls)
