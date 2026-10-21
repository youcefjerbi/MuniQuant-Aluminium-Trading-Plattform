"""Workspace tests run against a real Data Core: its own process, environment and new database.

CORE_HOME is a checkout of the Data Core (default: ../muniquant-data-core) and CORE_PYTHON an
interpreter with it installed (default: CORE_HOME/.venv/bin/python). The two projects never share
a Python environment, as in production.
"""
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from uuid import uuid4
import httpx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from fastapi.testclient import TestClient
from alembic.config import Config
from alembic import command
from app.core_client import CoreClient
from app.main import create_app

ROOT = Path(__file__).resolve().parents[1]
CORE_HOME = Path(os.getenv('CORE_HOME') or ROOT.parent / 'muniquant-data-core').resolve()
CORE_PYTHON = os.getenv('CORE_PYTHON') or str(CORE_HOME / '.venv' / 'bin' / 'python')
CORE_TOKEN = 'core-test-token'

class Core:
    """A running Data Core; post() and get() call its API directly, as a curator in the Core would."""
    def __init__(self, url, directory):
        self.url, self.directory = url, directory
        self.http = httpx.Client(base_url=url + '/api', headers={'Authorization': 'Bearer ' + CORE_TOKEN}, timeout=30)
    def post(self, path, data):
        response = self.http.post('/' + path, json=data)
        assert response.status_code == 201, response.text
        return response.json()
    def get(self, path, **params):
        response = self.http.get('/' + path, params=params)
        assert response.status_code == 200, response.text
        return response.json()

def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]

def core_environment(database, snapshots):
    """Environment for a Core process; database is a SQLite path or a SQLAlchemy URL."""
    url = str(database) if '://' in str(database) else 'sqlite:///' + str(database)
    return {**os.environ, 'DATABASE_URL': url, 'SNAPSHOT_DIR': str(snapshots),
            'WRITE_TOKEN': CORE_TOKEN, 'WRITE_ACTOR': 'core-curator', 'REQUIRE_READ_AUTH': 'false', 'WRITE_IDENTITIES_JSON': ''}

def start_core(database, snapshots, log):
    """Start a Core server on a free port; return (process, url) once its health check answers."""
    port = free_port()
    process = subprocess.Popen([CORE_PYTHON, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port), '--log-level', 'warning'],
                               cwd=CORE_HOME, env=core_environment(database, snapshots), stdout=log, stderr=subprocess.STDOUT)
    url = f'http://127.0.0.1:{port}'
    for _ in range(200):
        try:
            if httpx.get(url + '/api/health', timeout=1).status_code == 200: return process, url
        except httpx.HTTPError: pass
        if process.poll() is not None: break
        time.sleep(0.1)
    process.kill()
    raise RuntimeError('The Data Core did not start; see ' + str(log.name))

@pytest.fixture(scope='session')
def core_template(tmp_path_factory):
    """One migrated, empty Core database; each test gets its own copy."""
    if not (CORE_HOME / 'app' / 'main.py').is_file() or not Path(CORE_PYTHON).is_file():
        pytest.fail(f'Workspace tests need the Data Core: set CORE_HOME (now {CORE_HOME}) and CORE_PYTHON (now {CORE_PYTHON})')
    database = tmp_path_factory.mktemp('core-template') / 'core.db'
    subprocess.run([CORE_PYTHON, '-m', 'alembic', 'upgrade', 'head'], cwd=CORE_HOME, env=core_environment(database, database.parent / 'snapshots'),
                   check=True, capture_output=True)
    return database

@pytest.fixture
def core(tmp_path, core_template):
    directory = tmp_path / 'core'
    directory.mkdir()
    shutil.copy(core_template, directory / 'core.db')
    with open(directory / 'server.log', 'w') as log:
        process, url = start_core(directory / 'core.db', directory / 'snapshots', log)
        running = Core(url, directory)
        try: yield running
        finally:
            running.http.close()
            process.terminate()
            try: process.wait(10)
            except subprocess.TimeoutExpired: process.kill()

@pytest.fixture
def client(tmp_path, monkeypatch, core):
    url='sqlite:///'+str(tmp_path/'test.db')
    admin=None
    if os.getenv('TEST_DATABASE_URL'):
        admin=create_engine(os.environ['TEST_DATABASE_URL'])
        schema='test_'+uuid4().hex
        with admin.begin() as connection: connection.execute(text('CREATE SCHEMA '+schema))
        url=make_url(os.environ['TEST_DATABASE_URL']).update_query_dict({'options':'-csearch_path='+schema}).render_as_string(hide_password=False)
    monkeypatch.setenv('DATABASE_URL',url)
    command.upgrade(Config('alembic.ini'),'head')
    connection=CoreClient(core.url,CORE_TOKEN)
    app=create_app(url,tmp_path/'snapshots',write_token='test-token',core=connection)
    with TestClient(app) as client:
        client.headers['Authorization']='Bearer test-token'
        yield client
    app.state.engine.dispose()
    connection.close()
    if admin:
        with admin.begin() as connection: connection.execute(text('DROP SCHEMA '+schema+' CASCADE'))
        admin.dispose()

@pytest.fixture
def new_database(tmp_path):
    """Make new, empty databases: SQLite files, or fresh PostgreSQL schemas under TEST_DATABASE_URL."""
    schemas=[]
    admin=create_engine(os.environ['TEST_DATABASE_URL']) if os.getenv('TEST_DATABASE_URL') else None
    def make(name):
        if not admin: return 'sqlite:///'+str(tmp_path/(name+'.db'))
        schema='test_'+uuid4().hex
        with admin.begin() as connection: connection.execute(text('CREATE SCHEMA '+schema))
        schemas.append(schema)
        return make_url(os.environ['TEST_DATABASE_URL']).update_query_dict({'options':'-csearch_path='+schema}).render_as_string(hide_password=False)
    yield make
    if admin:
        with admin.begin() as connection:
            for schema in schemas: connection.execute(text('DROP SCHEMA '+schema+' CASCADE'))
        admin.dispose()

@pytest.fixture
def example(core):
    """A Core facility, source and captured document."""
    e=core.post('entities',{'name':'Test Smelter','country':'NO','facility_type':'smelter','aliases':['Test Works']})
    s=core.post('sources',{'name':'Test source','publisher':'Test publisher','source_type':'company','url':'https://example.org/source','access_status':'permitted'})
    payload={'source_id':s['id'],'title':'Report','original_url':'https://example.org/report','published_at':'2025-01-01','content':'Capacity: 400 kt/year'}
    d=core.post('documents',payload)
    return e,s,d,payload
