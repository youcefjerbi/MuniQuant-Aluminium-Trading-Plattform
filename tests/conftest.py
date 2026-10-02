import pytest
import os
from uuid import uuid4
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from fastapi.testclient import TestClient
from alembic.config import Config
from alembic import command
from app.main import create_app

@pytest.fixture
def client(tmp_path,monkeypatch):
    url='sqlite:///'+str(tmp_path/'test.db')
    admin=None
    if os.getenv('TEST_DATABASE_URL'):
        admin=create_engine(os.environ['TEST_DATABASE_URL'])
        schema='test_'+uuid4().hex
        with admin.begin() as connection: connection.execute(text('CREATE SCHEMA '+schema))
        url=make_url(os.environ['TEST_DATABASE_URL']).update_query_dict({'options':'-csearch_path='+schema}).render_as_string(hide_password=False)
    monkeypatch.setenv('DATABASE_URL',url)
    command.upgrade(Config('alembic.ini'),'head')
    app=create_app(url,tmp_path/'snapshots',write_token='test-token')
    with TestClient(app) as client:
        client.headers['Authorization']='Bearer test-token'
        yield client
    app.state.engine.dispose()
    if admin:
        with admin.begin() as connection: connection.execute(text('DROP SCHEMA '+schema+' CASCADE'))
        admin.dispose()

@pytest.fixture
def example(client):
    def post(path,data):
        r=client.post('/api/'+path,json=data)
        assert r.status_code==201,r.text
        return r.json()
    e=post('entities',{'name':'Test Smelter','country':'NO','facility_type':'smelter','aliases':['Test Works']})
    s=post('sources',{'name':'Test source','publisher':'Test publisher','source_type':'company','url':'https://example.org/source','access_status':'permitted'})
    payload={'source_id':s['id'],'title':'Report','original_url':'https://example.org/report','published_at':'2025-01-01','content':'Capacity: 400 kt/year'}
    d=post('documents',payload)
    return e,s,d,payload
