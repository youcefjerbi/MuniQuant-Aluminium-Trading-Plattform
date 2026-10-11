from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from urllib.parse import urlsplit, unquote
from sqlalchemy.orm import Session
from app.research_demo import populate


def quote(client, key, price, observed=None, historical=False):
    when=observed or datetime.now(timezone.utc)
    body={'external_key':key,'price':price,'occurred_at':when.isoformat(),'historical':historical,'source_reference':'synthetic:chart-test'}
    if historical: body['known_at']=when.isoformat()
    result=client.post('/api/research/quotes',json=body)
    assert result.status_code==201,result.text
    return result.json()


def test_tradingview_config_is_scoped_validated_and_contains_no_ledger(client):
    result=client.get('/market-chart',params={'symbol':'NASDAQ:AAPL','interval':'60'},follow_redirects=False)
    assert result.status_code==307
    parsed=urlsplit(result.headers['location'])
    assert parsed.hostname=='www.tradingview-widget.com'
    config=json.loads(unquote(parsed.fragment))
    assert config['symbol']=='NASDAQ:AAPL' and config['interval']=='60'
    assert 'token' not in config and 'trades' not in config
    assert result.headers['referrer-policy']=='no-referrer'
    assert client.get('/market-chart',params={'symbol':'<script>'},follow_redirects=False).status_code==422
    assert client.get('/market-chart',params={'symbol':'https://evil.example'},follow_redirects=False).status_code==422
    assert client.get('/market-chart',params={'interval':'bad'},follow_redirects=False).status_code==422
    root=client.get('/')
    assert "script-src 'self'" in root.headers['content-security-policy']
    assert "frame-src 'self' https://www.tradingview-widget.com" in root.headers['content-security-policy']
    assert '/static/market.js' in root.text


def test_empty_account_does_not_invent_performance(client):
    result=client.get('/api/research/performance').json()
    assert result['summary'] is None and not result['trades'] and not result['points']
    client.post('/api/research/policy',json={})
    result=client.get('/api/research/performance').json()
    assert result['summary']['equity']=='100000' and result['points'][0]['price'] is None
    assert result['summary']['market_return_percent'] is None


def test_paper_profit_includes_fees_and_slippage_and_updates_at_stored_quotes(client):
    with Session(client.app.state.engine) as s: populate(s)
    before=client.get('/api/research/performance').json()
    assert before['summary']['trade_count']==1
    assert before['trades'][0]['action']=='BUY'
    assert Decimal(before['summary']['pnl'])<0
    assert Decimal(before['summary']['fees'])>0
    assert all(p['price']!='104' for p in before['points']) # historical outcome quotes are excluded
    account=client.get('/api/research').json()['account']
    quote(client,'new-price','110')
    after=client.get('/api/research/performance').json()
    expected=Decimal(account['cash'])+Decimal(account['quantity'])*110
    assert Decimal(after['summary']['equity'])==expected
    assert Decimal(after['summary']['pnl'])==expected-100000
    assert Decimal(after['summary']['market_return_percent'])==10
    assert after['summary']['trade_count']==1 # quotes value the position; they do not create orders
    assert Decimal(after['points'][-1]['quantity'])==Decimal(account['quantity'])


def test_delayed_old_and_historical_quotes_do_not_replace_latest_mark(client):
    with Session(client.app.state.engine) as s: populate(s)
    quote(client,'current','110')
    quote(client,'delayed-old','999',observed=datetime.now(timezone.utc)-timedelta(hours=1))
    quote(client,'historical-only','888',observed=datetime.now(timezone.utc)-timedelta(minutes=1),historical=True)
    result=client.get('/api/research/performance').json()
    assert result['points'][-1]['price']=='110'
    assert Decimal(result['summary']['market_return_percent'])==10


def test_chart_symbol_is_context_only_and_does_not_change_paper_settings(client):
    with Session(client.app.state.engine) as s: populate(s)
    before=client.get('/api/research').json()['account']
    client.get('/market-chart',params={'symbol':'NASDAQ:AAPL'},follow_redirects=False)
    assert client.get('/api/research').json()['account']==before
