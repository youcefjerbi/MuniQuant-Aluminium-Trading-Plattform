"""Explicit, bounded paper execution of a completed evidence-agent proposal."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from sqlalchemy import select, update, func
from .research import Conflict
from .research_models import PaperAccount, PaperPolicy, ResearchQuote, PaperDecision, ResearchEvent
from .research_schemas import PolicyIn
from .models import Audit, uid

D=Decimal

def clock():return datetime.now(timezone.utc)
def stamp(value):
    try:
        value=datetime.fromisoformat(value.replace('Z','+00:00')) if isinstance(value,str) else value
        if value.tzinfo is None or value.utcoffset() is None:raise ValueError()
        return value.astimezone(timezone.utc)
    except (ValueError,TypeError,AttributeError):raise Conflict('Invalid proposal timestamp') from None

def amount(value):
    try:
        result=D(str(value))
        if not result.is_finite() or result<0:raise ValueError()
        return result
    except (ValueError,InvalidOperation):raise Conflict('Invalid paper portfolio amount') from None

def apply_agent_decision(s,run,actor):
    """Return one ledger decision; caller commits. All broker access is absent."""
    from .trading_agent_models import TradingAgentRun
    run=s.scalar(select(TradingAgentRun).where(TradingAgentRun.id==run.id).with_for_update().execution_options(populate_existing=True))
    if not run:raise Conflict('Agent run not found')
    if run.actor!=actor:raise Conflict('Only the proposing actor may apply this paper decision')
    if run.paper_decision_id:
        decision=s.get(PaperDecision,run.paper_decision_id)
        if not decision:raise Conflict('Agent paper decision reference is invalid')
        return decision
    result=run.result or {};inputs=run.inputs or {};action=result.get('action')
    if run.status!='completed' or action not in {'BUY','SELL','HOLD'} or not isinstance(result.get('reasoning'),str):raise Conflict('A completed structured proposal is required')
    if action!='HOLD' and (result.get('execution_allowed') is not True or result.get('guard_reasons')):raise Conflict('Agent proposal is not eligible for paper execution')
    current=clock();timestamp=current.isoformat()
    for value in (run.created_at,run.completed_at,inputs.get('as_of')):
        age=(current-stamp(value)).total_seconds()
        if age<0 or age>300:raise Conflict('Agent proposal is stale; generate a new run')
    account=s.scalar(select(PaperAccount).where(PaperAccount.id=='paper').with_for_update().execution_options(populate_existing=True))
    if not account:raise Conflict('Configure the paper account first')
    portfolio=inputs.get('portfolio') or {}
    if account.instrument!=run.instrument or portfolio.get('version')!=account.version or portfolio.get('policy_id')!=account.policy_id or portfolio.get('instrument')!=account.instrument:
        raise Conflict('Paper account or policy changed; generate a new run')
    cash,quantity,peak=map(amount,(account.cash,account.quantity,account.peak_equity))
    if amount(portfolio.get('cash'))!=cash or amount(portfolio.get('quantity'))!=quantity:raise Conflict('Paper portfolio changed; generate a new run')
    policy_row=s.get(PaperPolicy,account.policy_id)
    if not policy_row:raise Conflict('Paper policy is unavailable')
    policy=PolicyIn(**policy_row.settings)
    if not policy.enabled:raise Conflict('Paper policy is paused')
    if policy.instrument!=run.instrument:raise Conflict('Proposal instrument does not match the paper policy')
    quote=s.scalar(select(ResearchQuote).where(ResearchQuote.instrument==run.instrument,ResearchQuote.historical==0,
        ResearchQuote.observed_at<=timestamp,ResearchQuote.known_at<=timestamp).order_by(ResearchQuote.observed_at.desc(),ResearchQuote.known_at.desc(),ResearchQuote.id).limit(1))
    if not quote or not 0<amount(quote.price) or not 0<=(current-stamp(quote.observed_at)).total_seconds()<=policy.max_quote_age_seconds or not 0<=(current-stamp(quote.known_at)).total_seconds()<=policy.max_quote_age_seconds:
        raise Conflict('A fresh nonhistorical paper quote is required')
    market_price=amount(quote.price);equity=cash+quantity*market_price;peak=max(peak,equity)
    if action!='HOLD':
        if equity<peak*(1-policy.max_drawdown_fraction):raise Conflict('Paper drawdown limit reached')
        previous=s.scalar(select(PaperDecision).where(PaperDecision.action!='HOLD').order_by(PaperDecision.created_at.desc(),PaperDecision.id).limit(1))
        if previous and (current-stamp(previous.created_at)).total_seconds()<policy.cooldown_seconds:raise Conflict('Paper trade cooldown is active')
        daily=s.scalar(select(func.count()).select_from(PaperDecision).where(PaperDecision.action!='HOLD',PaperDecision.created_at>=timestamp[:10],PaperDecision.created_at<timestamp[:10]+'T23:59:59.999999+00:00'))
        if daily>=policy.max_daily_trades:raise Conflict('Daily paper trade limit reached')
    fee_fraction=D(policy.fee_bps)/10000;slippage=D(policy.slippage_bps)/10000;fill=None
    if action=='BUY':
        price=market_price*(1+slippage)
        # Solve post-cost exposure constraint: position <= fraction * (equity - costs).
        fraction=policy.max_exposure_fraction
        cap=max(D(0),(fraction*equity-quantity*market_price)*price/(market_price*(1-fraction)+fraction*price*(1+fee_fraction)))
        budget=min(policy.max_trade_notional,cash/(1+fee_fraction),cap)
        units=(budget/price).quantize(D('0.00000001'),rounding=ROUND_DOWN)
        if units<=0:raise Conflict('Cash or exposure limit prevents a paper purchase')
        notional=units*price;fee=notional*fee_fraction
        new_cash=cash-notional-fee;new_quantity=quantity+units
        # Explicit mark-to-market post-fill guard accounts for both fee and slippage.
        marked_equity=new_cash+new_quantity*market_price
        if new_quantity*market_price>marked_equity*fraction:raise Conflict('Post-fill paper exposure limit exceeded')
        cash,quantity=new_cash,new_quantity
        fill={'quantity':str(units),'price':str(price),'fee':str(fee),'notional':str(notional),'mode':'paper'}
    elif action=='SELL':
        price=market_price*(1-slippage)
        units=min(quantity,(policy.max_trade_notional/price).quantize(D('0.00000001'),rounding=ROUND_DOWN))
        if units<=0:raise Conflict('No long paper position to sell; shorts are disabled')
        notional=units*price;fee=notional*fee_fraction;cash+=notional-fee;quantity-=units
        fill={'quantity':str(units),'price':str(price),'fee':str(fee),'notional':str(notional),'mode':'paper'}
    if cash<0 or quantity<0:raise Conflict('Paper execution cannot borrow cash or short')
    refs={'entity_ids':inputs.get('entity_ids',[]),'record_ids':inputs.get('record_ids',[]),'evidence_refs':inputs.get('evidence_refs',[]),'build_hash':inputs.get('build_hash'),'context_hash':inputs.get('context_hash')}
    with s.begin_nested():
        version=account.version
        changed=s.execute(update(PaperAccount).where(PaperAccount.id==account.id,PaperAccount.version==version,
            PaperAccount.policy_id==account.policy_id).values(cash=str(cash),quantity=str(quantity),peak_equity=str(peak),version=version+1))
        if changed.rowcount!=1:raise Conflict('Paper account changed concurrently; generate a new run')
        event_id=uid();chain={'version':'trading-agent-proposal-v1','window_hours':0,'event_ids':[event_id],'sequence':['other'],'edges':[]}
        event=ResearchEvent(id=event_id,external_key='trading-agent:'+run.id,instrument=run.instrument,kind='other',occurred_at=timestamp,known_at=timestamp,recorded_at=timestamp,historical=0,
            payload={'title':'Evidence agent paper proposal','summary':result['reasoning'],'source_reference':'trading-agent:'+run.id,'entity_ids':refs['entity_ids'],'countries':[],'tags':['agent-paper-proposal'],'proposal_run_id':run.id,'is_agent_proposal':True,'core_refs':refs},chain=chain,features={'kind:other':3,'tag:agent-paper-proposal':2})
        s.add(event);s.flush()
        details={'fill':fill,'cash_after':str(cash),'quantity_after':str(quantity),'equity_before':str(equity),'policy_snapshot':policy_row.settings,'chain_snapshot':chain,'mode':'paper','agent_run_id':run.id,'core_refs':refs,'citations':result.get('citations',[]),'sample_count':0,'interpretation':'Explicit evidence-agent proposal; not a deterministic historical analogue trade'}
        decision=PaperDecision(id=uid(),event_id=event.id,policy_id=policy_row.id,quote_id=quote.id,action=action,reason=result['reasoning'],details=details,actor=actor,created_at=timestamp)
        s.add(decision);s.flush()
        linked=s.execute(update(TradingAgentRun).where(TradingAgentRun.id==run.id,TradingAgentRun.paper_decision_id.is_(None)).values(paper_decision_id=decision.id))
        if linked.rowcount!=1:raise Conflict('Agent run was executed concurrently; refresh')
        s.add(Audit(actor=actor,action='agent_paper_decision',record_id=decision.id,detail={'agent_run_id':run.id,'mode':'paper','core_refs':refs}))
    s.refresh(run)
    return decision
