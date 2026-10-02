"""Deterministic paper-only stock/options replay. No broker or live feed connection."""
import hashlib
import math
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, model_validator
from sqlalchemy import select, update
from .models import PaperAccount, PaperOrder, Audit, now
from .schemas import Input
from .services import record

INITIAL_CASH=10_000_000
START_CURSOR=60
LAST_CURSOR=119
DATASET='synthetic-replay-v1'
STOCKS={'AA':('Alcoa',4000),'CENX':('Century Aluminum',2000),'SPY':('S&P 500 ETF',50000),'QQQ':('Nasdaq-100 ETF',45000)}
DATES=[]
d=date(2025,1,2)
while len(DATES)<120:
    if d.weekday()<5: DATES.append(d.isoformat())
    d+=timedelta(days=1)

@lru_cache(maxsize=1)
def instruments():
    result={s:{'id':s,'symbol':s,'name':name,'kind':'stock','underlying':s,'multiplier':1,'currency':'USD'} for s,(name,_) in STOCKS.items()}
    for symbol,(_,base) in STOCKS.items():
        step=500 if base<10000 else 5000
        for strike in [base-step,base,base+step]:
            for right in ['call','put']:
                identifier=f'{symbol}-{DATES[-1]}-{right[0].upper()}-{strike//100}'
                result[identifier]={'id':identifier,'symbol':symbol,'name':f'{symbol} {right} ${strike/100:g}',
                    'kind':'option','underlying':symbol,'right':right,'strike_cents':strike,'expiry':DATES[-1],
                    'multiplier':100,'currency':'USD','settlement':'synthetic cash settlement','exercise':'expiry only'}
    return result

@lru_cache(maxsize=4)
def stock_bars(symbol):
    value=STOCKS[symbol][1];bars=[]
    for i,day in enumerate(DATES):
        noise=int(hashlib.sha256(f'{DATASET}:{symbol}:{i}'.encode()).hexdigest()[:8],16)
        opening=value
        value=max(100,round(value*(1+((noise%401)-180)/10000)))
        spread=max(2,opening*(50+noise%100)//10000)
        bars.append({'date':day,'open':opening,'high':max(opening,value)+spread,'low':max(1,min(opening,value)-spread),
                     'close':value,'volume':500_000+noise%5_000_000})
    return bars

def quote(identifier,cursor):
    inst=instruments().get(identifier)
    if not inst: raise ValueError('Unknown simulated instrument')
    spot=stock_bars(inst['underlying'])[cursor]['close']
    if inst['kind']=='stock': return spot
    intrinsic=max(0,spot-inst['strike_cents']) if inst['right']=='call' else max(0,inst['strike_cents']-spot)
    # A toy premium series, explicitly not a calibrated option valuation model.
    time_value=round(spot*.035*math.sqrt((LAST_CURSOR-cursor)/LAST_CURSOR))
    return intrinsic+time_value

def order_rows(s): return list(s.scalars(select(PaperOrder).order_by(PaperOrder.id)))

def portfolio(orders):
    positions={};realized=0
    for o in sorted(orders, key=lambda row: (row.session_index, row.id)):
        if o.status not in ('filled','settled'): continue
        p=positions.setdefault(o.instrument,{'quantity':0,'cost_cents':0})
        amount=o.fill_cents*o.quantity*instruments()[o.instrument]['multiplier']
        if o.side=='buy': p['quantity']+=o.quantity;p['cost_cents']+=amount
        else:
            if o.quantity>p['quantity']: raise ValueError('Invalid paper ledger: sale exceeds position')
            released=(Decimal(p['cost_cents'])*o.quantity/p['quantity']).quantize(Decimal('1'),rounding=ROUND_HALF_UP)
            p['cost_cents']-=int(released);p['quantity']-=o.quantity;realized+=amount-int(released)
    return positions,realized

def reserves(orders):
    cash=0;shares={}
    for o in orders:
        if o.status!='open': continue
        if o.side=='buy': cash+=o.limit_cents*o.quantity*instruments()[o.instrument]['multiplier']
        else: shares[o.instrument]=shares.get(o.instrument,0)+o.quantity
    return cash,shares

def account(s,mutate=False):
    a=s.get(PaperAccount,'shared-pilot')
    if not a: raise HTTPException(409,'Paper account not initialized; run database migrations')
    if mutate:
        previous=a.version
        changed=s.execute(update(PaperAccount).where(PaperAccount.id==a.id,PaperAccount.version==previous).values(version=previous+1))
        if changed.rowcount!=1: raise HTTPException(409,'Account changed in another request; refresh and retry')
        s.refresh(a)
    return a

def snapshot(s):
    a=account(s);orders=order_rows(s);positions,realized=portfolio(orders);reserved,shares=reserves(orders)
    holdings=[];market_value=0
    for identifier,p in positions.items():
        if not p['quantity']:continue
        inst=instruments()[identifier];last=quote(identifier,a.cursor);value=last*p['quantity']*inst['multiplier'];market_value+=value
        holdings.append(dict(p,instrument=identifier,name=inst['name'],kind=inst['kind'],multiplier=inst['multiplier'],
            quote_cents=last,market_value_cents=value,unrealized_cents=value-p['cost_cents'],available_quantity=p['quantity']-shares.get(identifier,0)))
    return {'dataset':DATASET,'data_status':'synthetic','session_date':DATES[a.cursor],'cursor':a.cursor,'last_cursor':LAST_CURSOR,
        'initial_cash_cents':INITIAL_CASH,'cash_cents':a.cash_cents,'reserved_cash_cents':reserved,'available_cash_cents':a.cash_cents-reserved,
        'equity_cents':a.cash_cents+market_value,'realized_cents':realized,'unrealized_cents':sum(p['unrealized_cents'] for p in holdings),
        'positions':holdings,'orders':[record(o) for o in reversed(orders)],
        'instruments':[dict(i,quote_cents=quote(i['id'],a.cursor),expired=i['kind']=='option' and a.cursor==LAST_CURSOR) for i in instruments().values()]}

class OrderIn(Input):
    request_id: UUID
    instrument: str=Field(min_length=1,max_length=100)
    side: Literal['buy','sell']
    order_type: Literal['market','limit']='market'
    quantity: int=Field(gt=0,le=100000,strict=True)
    limit_cents: int | None=Field(default=None,gt=0,le=100_000_000,strict=True)
    @model_validator(mode='after')
    def limit_required(self):
        if (self.order_type=='limit') != (self.limit_cents is not None): raise ValueError('Only limit orders require a limit price')
        return self

class AdvanceIn(Input):
    expected_cursor: int=Field(ge=0,le=LAST_CURSOR)

def fill(s,a,o,price):
    amount=price*o.quantity*instruments()[o.instrument]['multiplier']
    a.cash_cents+=amount if o.side=='sell' else -amount
    o.status='filled';o.fill_cents=price;o.filled_at=DATES[a.cursor];o.session_index=a.cursor
    s.flush()

def executable(o,price): return o.order_type=='market' or (price<=o.limit_cents if o.side=='buy' else price>=o.limit_cents)

def register_routes(app,session,writer):
    router=APIRouter(prefix='/api/paper',tags=['Paper trading — synthetic only'])
    @router.get('/workspace')
    def workspace(s=Depends(session)): return snapshot(s)

    @router.get('/history/{identifier}')
    def history(identifier:str,s=Depends(session)):
        a=account(s);inst=instruments().get(identifier)
        if not inst: raise HTTPException(404,'Unknown simulated instrument')
        if inst['kind']=='stock': bars=stock_bars(identifier)[:a.cursor+1]
        else:
            bars=[]
            for i in range(a.cursor+1):
                close=quote(identifier,i);opening=quote(identifier,max(0,i-1))
                bars.append({'date':DATES[i],'open':opening,'high':max(opening,close),'low':min(opening,close),'close':close,'volume':None})
        return {'instrument':inst,'dataset':DATASET,'data_status':'synthetic','bars':bars,'session_date':DATES[a.cursor]}

    @router.post('/orders',status_code=201)
    def place(data:OrderIn,s=Depends(session),actor=Depends(writer)):
        a=account(s,True)
        previous=s.scalar(select(PaperOrder).where(PaperOrder.request_id==str(data.request_id)))
        if previous:
            if any(getattr(previous,k)!=v for k,v in data.model_dump(exclude={'request_id'}).items()):
                raise HTTPException(409,'Request ID was already used for a different order')
            s.rollback();return record(previous)
        inst=instruments().get(data.instrument)
        if not inst: raise ValueError('Unknown simulated instrument')
        if inst['kind']=='option' and a.cursor==LAST_CURSOR: raise ValueError('This simulated option has expired')
        orders=order_rows(s);positions,_=portfolio(orders);reserved,shares=reserves(orders)
        current=quote(data.instrument,a.cursor)
        cost_price=data.limit_cents if data.order_type=='limit' else current
        if data.side=='buy' and cost_price*data.quantity*inst['multiplier']>a.cash_cents-reserved:
            raise ValueError('Insufficient available paper cash; pending buy limits reserve cash')
        if data.side=='sell' and data.quantity>positions.get(data.instrument,{}).get('quantity',0)-shares.get(data.instrument,0):
            raise ValueError('Insufficient available position; only sell-to-close is supported')
        o=PaperOrder(**data.model_dump(exclude={'request_id'}),request_id=str(data.request_id),status='open',session_index=a.cursor,actor=actor)
        s.add(o);s.flush()
        if executable(o,current): fill(s,a,o,current)
        s.add(Audit(actor=actor,action='paper_order',record_id=str(o.id),detail={'instrument':o.instrument,'side':o.side,'quantity':o.quantity,'dataset':DATASET}))
        s.commit();return record(o)

    @router.post('/orders/{identifier}/cancel')
    def cancel(identifier:int,s=Depends(session),actor=Depends(writer)):
        account(s,True);o=s.get(PaperOrder,identifier)
        if not o: raise HTTPException(404,'Order not found')
        if o.status!='open': raise HTTPException(409,'Only an open order can be cancelled')
        o.status='cancelled';s.add(Audit(actor=actor,action='paper_cancel',record_id=str(o.id),detail={}))
        s.commit();return record(o)

    @router.post('/advance')
    def advance(data:AdvanceIn,s=Depends(session),actor=Depends(writer)):
        a=account(s,True)
        if a.cursor!=data.expected_cursor: raise HTTPException(409,'Replay session changed; refresh before advancing')
        if a.cursor>=LAST_CURSOR: raise ValueError('End of the simulated replay')
        a.cursor+=1;s.flush()
        for o in order_rows(s):
            if o.status!='open':continue
            inst=instruments()[o.instrument]
            if inst['kind']=='option' and a.cursor==LAST_CURSOR: o.status='expired';continue
            price=quote(o.instrument,a.cursor)
            if executable(o,price): fill(s,a,o,price)
        s.flush()
        if a.cursor==LAST_CURSOR:
            holdings,_=portfolio(order_rows(s))
            for identifier,p in holdings.items():
                if p['quantity'] and instruments()[identifier]['kind']=='option':
                    price=quote(identifier,a.cursor)
                    o=PaperOrder(request_id='expiry:'+identifier,instrument=identifier,side='sell',order_type='market',quantity=p['quantity'],
                        fill_cents=price,status='settled',session_index=a.cursor,filled_at=DATES[a.cursor],actor='simulator')
                    s.add(o);a.cash_cents+=price*p['quantity']*100
        s.add(Audit(actor=actor,action='paper_advance',record_id=a.id,detail={'cursor':a.cursor,'date':DATES[a.cursor]}))
        s.commit();return snapshot(s)
    app.include_router(router)
