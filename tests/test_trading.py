from uuid import uuid4
import pytest
from sqlalchemy.orm import Session
from app.models import PaperAccount, PaperOrder
from app.trading import quote, instruments, LAST_CURSOR, INITIAL_CASH, portfolio


def order(client,instrument='AA',side='buy',quantity=10,**kwargs):
    payload={'request_id':str(uuid4()),'instrument':instrument,'side':side,'quantity':quantity,'order_type':'market'}
    payload.update(kwargs)
    return client.post('/api/paper/orders',json=payload)

def workspace(client):
    r=client.get('/api/paper/workspace');assert r.status_code==200,r.text
    return r.json()

def test_history_is_synthetic_and_no_future_bars(client):
    data=workspace(client)
    assert data['cash_cents']==10_000_000
    bars=client.get('/api/paper/history/AA').json()
    assert bars['data_status']=='synthetic' and len(bars['bars'])==data['cursor']+1
    assert bars['bars'][-1]['date']==data['session_date']
    for b in bars['bars']: assert b['low']<=min(b['open'],b['close'])<=max(b['open'],b['close'])<=b['high']
    assert client.get('/api/paper/history/UNKNOWN').status_code==404

def test_buy_sell_cash_and_pl(client):
    before=workspace(client);price=quote('AA',before['cursor'])
    assert order(client).status_code==201
    after=workspace(client)
    assert after['cash_cents']==INITIAL_CASH-10*price
    assert after['equity_cents']==INITIAL_CASH and after['unrealized_cents']==0
    assert client.post('/api/paper/advance',json={'expected_cursor':before['cursor']}).status_code==200
    current=workspace(client);new_price=quote('AA',current['cursor'])
    assert current['unrealized_cents']==(new_price-price)*10
    assert order(client,side='sell',quantity=4).status_code==201
    after=workspace(client)
    assert after['positions'][0]['quantity']==6
    assert after['realized_cents']==(new_price-price)*4
    assert after['equity_cents']-INITIAL_CASH==after['realized_cents']+after['unrealized_cents']

@pytest.mark.parametrize('kwargs',[{'quantity':0},{'quantity':-1},{'quantity':1.5},{'instrument':'BOGUS'},{'side':'sell'},{'quantity':100000},{'order_type':'limit'},{'order_type':'market','limit_cents':100},{'order_type':'limit','limit_cents':0}])
def test_reject_invalid_orders_without_balance_change(client,kwargs):
    r=order(client,**kwargs)
    assert r.status_code==422,r.text
    after=workspace(client)
    assert after['cash_cents']==INITIAL_CASH and not after['orders']

def test_double_submit_and_mismatched_reuse(client):
    key=str(uuid4())
    first=order(client,request_id=key).json()
    second=order(client,request_id=key).json()
    assert first['id']==second['id'] and len(workspace(client)['orders'])==1
    assert order(client,request_id=key,quantity=11).status_code==409

def test_cash_reservation_and_cancel(client):
    pending=order(client,quantity=100,order_type='limit',limit_cents=1).json()
    assert pending['status']=='open'
    assert workspace(client)['reserved_cash_cents']==100
    response=client.post(f"/api/paper/orders/{pending['id']}/cancel")
    assert response.status_code==200
    assert workspace(client)['reserved_cash_cents']==0
    assert client.post(f"/api/paper/orders/{pending['id']}/cancel").status_code==409

def test_pending_sell_reserves_owned_quantity(client):
    order(client,quantity=10)
    assert order(client,side='sell',quantity=8,order_type='limit',limit_cents=1000000).json()['status']=='open'
    assert workspace(client)['positions'][0]['available_quantity']==2
    assert order(client,side='sell',quantity=3).status_code==422

def test_limit_fills_only_at_replay_close_and_stale_advance_rejected(client):
    # Choose a declining synthetic interval so the pending limit crosses next close.
    idx=next(i for i in range(60,118) if quote('AA',i+1)<quote('AA',i))
    with Session(client.app.state.engine) as s:
        s.get(PaperAccount,'shared-pilot').cursor=idx;s.commit()
    limit=quote('AA',idx+1)
    pending=order(client,quantity=5,order_type='limit',limit_cents=limit).json()
    assert pending['status']=='open'
    advanced=client.post('/api/paper/advance',json={'expected_cursor':idx}).json()
    assert advanced['orders'][0]['status']=='filled'
    assert advanced['orders'][0]['fill_cents']==limit
    assert advanced['cash_cents']==INITIAL_CASH-limit*5
    assert client.post('/api/paper/advance',json={'expected_cursor':idx}).status_code==409

@pytest.mark.parametrize('right',['call','put'])
def test_options_multiplier_and_long_only(client,right):
    option=next(i for i in instruments().values() if i['kind']=='option' and i['symbol']=='AA' and i['right']==right)
    price=quote(option['id'],60)
    assert order(client,instrument=option['id'],quantity=2).status_code==201
    data=workspace(client)
    assert data['cash_cents']==INITIAL_CASH-price*2*100
    assert data['positions'][0]['quantity']==2
    assert order(client,instrument=option['id'],side='sell',quantity=3).status_code==422
    assert order(client,instrument=option['id'],side='sell',quantity=2).status_code==201
    assert not workspace(client)['positions']
    assert workspace(client)['cash_cents']==INITIAL_CASH

def test_option_expiry_settles_and_cancels_pending(client):
    option=next(i for i in instruments().values() if i['kind']=='option' and i['symbol']=='AA')
    with Session(client.app.state.engine) as s:
        s.get(PaperAccount,'shared-pilot').cursor=LAST_CURSOR-1;s.commit()
    premium=quote(option['id'],LAST_CURSOR-1)
    assert order(client,instrument=option['id'],quantity=1).status_code==201
    pending=order(client,instrument=option['id'],side='sell',quantity=1,order_type='limit',limit_cents=1000000)
    assert pending.json()['status']=='open'
    data=client.post('/api/paper/advance',json={'expected_cursor':LAST_CURSOR-1}).json()
    payoff=quote(option['id'],LAST_CURSOR)
    assert not data['positions']
    assert data['cash_cents']==INITIAL_CASH-premium*100+payoff*100
    assert {o['status'] for o in data['orders']}=={'filled','expired','settled'}
    assert order(client,instrument=option['id'],quantity=1).status_code==422
    assert client.post('/api/paper/advance',json={'expected_cursor':LAST_CURSOR}).status_code==422

def test_write_auth_and_export_boundary(client):
    client.headers.clear()
    assert order(client).status_code==401
    assert client.post('/api/paper/advance',json={'expected_cursor':60}).status_code==401
    package=client.get('/api/export').json()
    assert not any('paper' in k or 'order' in k for k in package)
