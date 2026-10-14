from datetime import datetime,timedelta,timezone
from decimal import Decimal as D
from types import SimpleNamespace
import pytest
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from sqlalchemy.sql.dml import Update
from app.models import uid
from app.research import Conflict
from app.research_models import PaperAccount,PaperPolicy,ResearchQuote,PaperDecision,ResearchEvent
from app.research_schemas import PolicyIn
from app.trading_agent_models import TradingAgentRun
from app.trading_agent_paper import apply_agent_decision


def setup_run(s,action='BUY',cash='100000',quantity='0',settings=None):
    timestamp=datetime.now(timezone.utc).isoformat()
    policy=PaperPolicy(id=uid(),settings=PolicyIn(enabled=True,**(settings or {})).model_dump(mode='json'),actor='test')
    s.add(policy);s.flush()
    account=PaperAccount(id='paper',policy_id=policy.id,instrument='ALUMINIUM_DEMO',cash=cash,quantity=quantity,peak_equity=str(D(cash)+D(quantity)*100),version=0)
    quote=ResearchQuote(id=uid(),external_key=uid(),instrument=account.instrument,price='100',observed_at=timestamp,known_at=timestamp,historical=0,source_reference='Synthetic test price')
    s.add_all([account,quote]);s.flush()
    run=TradingAgentRun(id=uid(),request_key=uid(),instrument=account.instrument,status='completed',actor='curator',created_at=timestamp,completed_at=timestamp,
        inputs={'as_of':timestamp,'build_hash':'b'*64,'context_hash':'c'*64,'entity_ids':['core-id'],'record_ids':['fact-id'],'evidence_refs':[{'record_id':'fact-id','document_version_id':'doc-id'}],
                'portfolio':{'cash':cash,'quantity':quantity,'version':0,'policy_id':policy.id,'instrument':account.instrument},'quotes':[{'id':quote.id,'price':quote.price}]},
        result={'action':action,'reasoning':'Synthetic evidence-backed proposal','citations':['E1'],'reports':{},'execution_allowed':True,'guard_reasons':[]})
    s.add(run);s.commit();return run,account,policy,quote


def test_buy_fees_slippage_cash_only_and_idempotence(client):
    with Session(client.app.state.engine) as s:
        run,account,policy,quote=setup_run(s)
        decision=apply_agent_decision(s,run,'curator');s.commit()
        fill=decision.details['fill'];units=D(fill['quantity']);price=D(fill['price']);fee=D(fill['fee'])
        assert price==D('100.05') and fee==D(fill['notional'])*D('0.0005')
        s.refresh(account)
        assert D(account.cash)==D('100000')-units*price-fee and D(account.quantity)==units and account.version==1
        assert D(fill['notional'])<=1000
        assert apply_agent_decision(s,run,'curator').id==decision.id
        assert s.scalar(select(func.count()).select_from(PaperDecision))==1
        assert s.scalar(select(func.count()).select_from(ResearchEvent))==1
        assert s.scalar(select(ResearchEvent)).external_key=='trading-agent:'+run.id
        assert decision.details['mode']=='paper' and decision.details['core_refs']['record_ids']==['fact-id']

@pytest.mark.parametrize('guard',['stale','paused','changed_policy','changed_version','historical_quote','stale_quote','funds','short','blocked_result'])
def test_execution_guards_make_no_ledger_mutations(client,guard):
    with Session(client.app.state.engine) as s:
        run,account,policy,quote=setup_run(s,action='SELL' if guard=='short' else 'BUY',cash='0' if guard=='funds' else '100000')
        if guard=='stale':run.created_at=(datetime.now(timezone.utc)-timedelta(seconds=301)).isoformat()
        if guard=='paused':policy.settings={**policy.settings,'enabled':False}
        if guard=='changed_policy':run.inputs={**run.inputs,'portfolio':{**run.inputs['portfolio'],'policy_id':'old-policy'}}
        if guard=='changed_version':account.version=1
        if guard=='historical_quote':quote.historical=1
        if guard=='stale_quote':quote.observed_at=(datetime.now(timezone.utc)-timedelta(seconds=301)).isoformat()
        if guard=='blocked_result':run.result={**run.result,'execution_allowed':False,'guard_reasons':['unsupported evidence']}
        s.commit();before=(account.cash,account.quantity,account.version)
        with pytest.raises(Conflict):apply_agent_decision(s,run,'curator')
        assert s.scalar(select(func.count()).select_from(PaperDecision))==0
        assert s.scalar(select(func.count()).select_from(ResearchEvent))==0
        s.refresh(account);assert (account.cash,account.quantity,account.version)==before
        assert run.paper_decision_id is None


def test_hold_audits_without_fill_even_when_model_guarded(client):
    with Session(client.app.state.engine) as s:
        run,account,_,_=setup_run(s,action='HOLD')
        run.result={**run.result,'execution_allowed':False,'guard_reasons':['Insufficient evidence']};s.commit()
        decision=apply_agent_decision(s,run,'curator');s.commit();s.refresh(account)
        assert decision.action=='HOLD' and decision.details['fill'] is None
        assert account.cash=='100000' and account.quantity=='0'
        assert apply_agent_decision(s,run,'curator').id==decision.id


def test_post_cost_exposure_and_cash_limits(client):
    with Session(client.app.state.engine) as s:
        run,account,_,_=setup_run(s,cash='100',quantity='0',settings={'fee_bps':100,'slippage_bps':100,'max_exposure_fraction':'0.5'})
        decision=apply_agent_decision(s,run,'curator');s.commit();s.refresh(account)
        position=D(account.quantity)*100;equity=D(account.cash)+position
        assert position<=equity*D('0.5') and D(account.cash)>=0
        assert D(decision.details['fill']['price'])==101


def test_account_cas_loss_rolls_back_event_and_decision(client,monkeypatch):
    with Session(client.app.state.engine) as s:
        run,account,_,_=setup_run(s);execute=s.execute
        def raced(statement,*args,**kwargs):
            if isinstance(statement,Update) and statement.table.name=='research_paper_account':return SimpleNamespace(rowcount=0)
            return execute(statement,*args,**kwargs)
        monkeypatch.setattr(s,'execute',raced)
        with pytest.raises(Conflict,match='concurrently'):apply_agent_decision(s,run,'curator')
        assert execute(select(func.count()).select_from(PaperDecision)).scalar()==0
        assert execute(select(func.count()).select_from(ResearchEvent)).scalar()==0
        s.refresh(account);assert account.version==0 and account.cash=='100000'


def another_run(s,run,account):
    timestamp=datetime.now(timezone.utc).isoformat()
    second=TradingAgentRun(id=uid(),request_key=uid(),instrument=run.instrument,status='completed',actor='curator',created_at=timestamp,completed_at=timestamp,
        inputs={**run.inputs,'as_of':timestamp,'portfolio':{**run.inputs['portfolio'],'cash':account.cash,'quantity':account.quantity,'version':account.version}},result=run.result)
    s.add(second);s.commit();return second

@pytest.mark.parametrize('limit',['cooldown','daily','drawdown'])
def test_risk_limits_block_without_new_trade(client,limit):
    with Session(client.app.state.engine) as s:
        run,account,policy,_=setup_run(s)
        first=apply_agent_decision(s,run,'curator');s.commit();s.refresh(account)
        second=another_run(s,run,account)
        if limit=='daily':
            first.created_at=(datetime.now(timezone.utc)-timedelta(seconds=120)).isoformat()
            policy.settings={**policy.settings,'cooldown_seconds':60,'max_daily_trades':1}
        if limit=='drawdown':
            account.peak_equity='1000000'
        s.commit();before=(account.cash,account.quantity,account.version)
        with pytest.raises(Conflict,match={'cooldown':'cooldown','daily':'Daily','drawdown':'drawdown'}[limit]):apply_agent_decision(s,second,'curator')
        assert s.scalar(select(func.count()).select_from(PaperDecision))==1
        s.refresh(account);assert (account.cash,account.quantity,account.version)==before


def test_sell_reduces_long_position_with_costs(client):
    with Session(client.app.state.engine) as s:
        run,account,_,_=setup_run(s,action='SELL',quantity='20')
        decision=apply_agent_decision(s,run,'curator');s.commit();s.refresh(account)
        fill=decision.details['fill'];units=D(fill['quantity'])
        assert D(fill['price'])==D('99.95') and D(fill['notional'])<=1000
        assert D(account.quantity)==20-units and D(account.quantity)>=0
        assert D(account.cash)==100000+D(fill['notional'])-D(fill['fee'])


def test_run_cas_loss_rolls_back_account_event_and_decision(client,monkeypatch):
    with Session(client.app.state.engine) as s:
        run,account,_,_=setup_run(s);execute=s.execute
        def raced(statement,*args,**kwargs):
            if isinstance(statement,Update) and statement.table.name=='trading_agent_run':return SimpleNamespace(rowcount=0)
            return execute(statement,*args,**kwargs)
        monkeypatch.setattr(s,'execute',raced)
        with pytest.raises(Conflict,match='concurrently'):apply_agent_decision(s,run,'curator')
        assert execute(select(func.count()).select_from(PaperDecision)).scalar()==0
        assert execute(select(func.count()).select_from(ResearchEvent)).scalar()==0
        s.refresh(account);assert account.version==0 and account.cash=='100000'


def test_agent_proposals_never_feed_factual_chains_analogues_or_influence(client):
    from app import research,event_influence
    from app.research_models import ResearchOutcome
    with Session(client.app.state.engine) as s:
        run,account,policy,quote=setup_run(s)
        decision=apply_agent_decision(s,run,'curator');s.commit()
        proposal=s.get(ResearchEvent,decision.event_id)
        assert proposal.payload['is_agent_proposal'] is True
        current=datetime.now(timezone.utc)
        anchor={'id':uid(),'instrument':run.instrument,'occurred_at':current.isoformat(),'known_at':current.isoformat(),'kind':'other','title':'Actual synthetic input','summary':'','entity_ids':['core-id'],'countries':[],'tags':['agent-paper-proposal']}
        chain,features=research.build_chain(s,anchor,anchor['known_at'])
        assert proposal.id not in chain['event_ids']
        # Even an explicitly labeled old proposal with a high-similarity outcome is excluded.
        old=(current-timedelta(days=10)).isoformat()
        proposal.known_at=old;proposal.occurred_at=old;proposal.features=features
        s.add(ResearchOutcome(id=uid(),event_id=proposal.id,entry_quote_id=quote.id,exit_quote_id=quote.id,return_fraction='0.2',available_at=(current-timedelta(days=8)).isoformat()))
        factual=ResearchEvent(id=anchor['id'],external_key=uid(),instrument=run.instrument,kind='other',occurred_at=anchor['occurred_at'],known_at=anchor['known_at'],historical=0,payload=anchor,chain=chain,features=features)
        s.add(factual);s.commit()
        matches=research.analogues(s,factual,PolicyIn(**policy.settings))
        assert matches['sample_count']==0
        assert research.analogues(s,proposal,PolicyIn(**policy.settings))['sample_count']==0
        assert proposal.id not in {event['event_id'] for event in event_influence.report(s)['events']}
        assert factual.id in {event['event_id'] for event in event_influence.report(s)['events']}
        assert decision.id in {item.id for item in s.scalars(select(PaperDecision))}


def test_other_actor_cannot_apply_or_retrieve_agent_paper_decision(client):
    with Session(client.app.state.engine) as s:
        run,_,_,_=setup_run(s)
        with pytest.raises(Conflict,match='proposing actor'):apply_agent_decision(s,run,'other-curator')
        assert s.scalar(select(func.count()).select_from(PaperDecision))==0
        decision=apply_agent_decision(s,run,'curator');s.commit()
        with pytest.raises(Conflict,match='proposing actor'):apply_agent_decision(s,run,'other-curator')
        assert s.scalar(select(func.count()).select_from(PaperDecision))==1
