"""DC1 step B3: tools/split.py splits a platform database into a Data Core and a Workspace database."""
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from argparse import Namespace
from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from app.core_client import CoreClient
from app.main import create_app
from conftest import CORE_HOME, CORE_PYTHON, CORE_TOKEN, start_core
from tools import split

FIXTURES = Path(__file__).parent / 'fixtures'
DEMO_EXPORT = 'c6f6b3d6386d3dcb0e50a97b0b4422646937d8c6bf96e4a6a84a515a952b8a95'  # the platform demo's v1 build hash

def restore(tmp_path, name, change=None):
    base = FIXTURES / name
    for path, digest in json.loads((base / 'manifest.json').read_text())['files'].items():
        assert hashlib.sha256((base / path).read_bytes()).hexdigest() == digest, path
    database = tmp_path / 'platform.db'
    with sqlite3.connect(database) as connection:
        connection.executescript((base / 'database.sql').read_text())
        if change: connection.executescript(change)
    shutil.copytree(base / 'snapshots', tmp_path / 'platform-snapshots')
    return database

def arguments(tmp_path, source, core, workspace, snapshots=True, dry_run=False):
    return Namespace(source=str(source), core=core, workspace=workspace, report=tmp_path / 'report.json',
                     snapshots=tmp_path / 'platform-snapshots' if snapshots else None,
                     core_snapshots=tmp_path / 'core-snapshots' if snapshots else None,
                     workspace_snapshots=tmp_path / 'workspace-snapshots' if snapshots else None,
                     core_home=str(CORE_HOME), core_python=CORE_PYTHON, dry_run=dry_run)

def test_mixed_database_splits_with_lead_material_on_the_workspace_side(tmp_path, new_database, monkeypatch):
    source = restore(tmp_path, 'platform-mixed')
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    core_url, workspace_url = new_database('core'), new_database('workspace')
    report = split.split(arguments(tmp_path, source, core_url, workspace_url))
    assert report['status'] == 'PASS', json.dumps(report['tables'], indent=1)
    assert report['source']['unchanged'] and hashlib.sha256(source.read_bytes()).hexdigest() == before
    assert report['lead_sources'] == [split.PERMUTABLE_SOURCE]
    tables = report['tables']
    # Every row is on exactly one side, unchanged; lead-feed rows in the Workspace's lead store.
    assert all(entry['complete'] for entry in tables.values())
    expected = {'sources': (1, 1), 'source_access': (0, 1), 'documents': (1, 3), 'document_version': (1, 3), 'source_document_relation': (1, 3),
                'source_snapshot': (1, 3), 'runs': (1, 5), 'retrieval_attempt': (0, 3)}
    for name, (core, workspace) in expected.items():
        assert (tables[name]['to_core'], tables[name]['to_workspace']) == (core, workspace), name
        assert tables[name]['core_equal'] and tables[name]['workspace_equal'] and tables[name]['workspace_table'] == split.LEAD_STORE[name]
    assert tables['audit']['to_core'] + tables['audit']['to_workspace'] == tables['audit']['source_rows'] and tables['audit']['to_workspace'] >= 8
    for name in ('lead', 'lead_revision', 'lead_headline', 'research_event', 'investigation_entry', 'asset_location', 'asset_dependency'):
        assert tables[name]['to_workspace'] == tables[name]['source_rows'] > 0 and tables[name]['workspace_equal'], name
    # The note citing a vendor response is kept as it is and reported.
    [outside] = report['workspace_references_outside_the_core']
    assert (outside['table'], outside['column'], outside['points_to']) == ('investigation_entry', 'document_id', 'lead store')
    assert len(list((tmp_path / 'workspace-snapshots').iterdir())) == 3 and len(list((tmp_path / 'core-snapshots').iterdir())) == 1
    # Both targets are ready for their applications: drift-free and working together.
    monkeypatch.setenv('DATABASE_URL', workspace_url)
    command.check(Config('alembic.ini'))
    with open(tmp_path / 'core.log', 'w') as log:
        process, url = start_core(core_url, tmp_path / 'core-snapshots', log)
        connection = CoreClient(url, CORE_TOKEN)
        app = create_app(workspace_url, tmp_path / 'workspace-snapshots', write_token='test-token', core=connection)
        try:
            with TestClient(app) as client:
                client.headers['Authorization'] = 'Bearer test-token'
                [lead] = client.get('/api/leads').json()['leads']
                assert lead['status'] == 'confirmed' and [m['name'] for m in lead['matched_entities']] == ['Fjord Aluminium Works']
                assert connection.observation(lead['observation_id'])['document_id'] == lead['primary_document_id']
                document = lead['latest_revision']['document_id']
                assert client.post('/api/permutable/documents/' + document + '/replay', json={}).json()['equivalent']
                assert connection.document(document) is None  # the vendor response is not a Core document
                events = client.get('/api/research').json()['events']
                outage = next(e for e in events if e['external_key'] == 'fixture-plant-outage')
                assert any('registered_relationship' in edge['reasons'] for edge in outage['chain']['edges'])
                graph = client.get('/api/asset-map').json()
                assert graph['missing_locations'] == 2 and len(graph['dependencies']) == 1
                [case] = client.get('/api/investigations').json()
                assert len(client.get('/api/investigations/' + case['id'] + '/notebook').json()['entries']) == 2
                package = connection.http.get('/export').json()
                assert split.PERMUTABLE_SOURCE not in {s['source_id'] for s in package['sources']} and len(package['documents']) == 1
        finally:
            app.state.engine.dispose(); connection.close()
            process.terminate(); process.wait(10)

def test_demo_data_splits_and_the_core_side_exports_the_same_package(tmp_path):
    source = restore(tmp_path, 'platform-demo')
    report = split.split(arguments(tmp_path, source, str(tmp_path / 'core.db'), str(tmp_path / 'workspace.db')))
    assert report['status'] == 'PASS' and not report['lead_sources'] and not report['workspace_references_outside_the_core']
    assert report['tables']['paper_accounts']['to_workspace'] == 1 and report['tables']['observations']['to_core'] == 6
    with open(tmp_path / 'core.log', 'w') as log:
        process, url = start_core(tmp_path / 'core.db', tmp_path / 'core-snapshots', log)
        connection = CoreClient(url, CORE_TOKEN)
        try: assert connection.http.get('/export').json()['build_hash'] == DEMO_EXPORT
        finally:
            connection.close(); process.terminate(); process.wait(10)

def test_dry_run_writes_only_the_report(tmp_path):
    source = restore(tmp_path, 'platform-mixed')
    report = split.split(arguments(tmp_path, source, str(tmp_path / 'core.db'), str(tmp_path / 'workspace.db'), dry_run=True))
    assert report['status'] == 'DRY_RUN_OK' and report['tables']['documents']['to_workspace'] == 3
    assert not any((tmp_path / name).exists() for name in ('core.db', 'workspace.db', 'core-snapshots', 'workspace-snapshots'))

@pytest.mark.parametrize('change, message', [
    # A Core fact citing a vendor response cannot be split: it must cite the primary source first.
    ("UPDATE observations SET document_id = (SELECT id FROM documents WHERE source_id = '{source}' LIMIT 1)", 'cites lead-feed document'),
    ("INSERT INTO source_access (id, source_id, status, allowed_hosts, basis, retention, reviewer, decided_at, usage_scope) "
     "VALUES ('mixed', '{source}', 'permitted', '[]', 'Evidence decision for a lead feed', 'Local', 'test', '2026-10-21', 'evidence')", 'both lead-only and evidence'),
    ("CREATE TABLE notes (id TEXT PRIMARY KEY)", 'Unknown tables'),
    ("UPDATE alembic_version SET version_num = 'bd298b7e2b38'", 'upgrade a copy'),
])
def test_refuses_sources_it_cannot_split_cleanly(tmp_path, change, message):
    source = restore(tmp_path, 'platform-mixed', change.format(source=split.PERMUTABLE_SOURCE))
    with pytest.raises(ValueError, match=message):
        split.split(arguments(tmp_path, source, str(tmp_path / 'core.db'), str(tmp_path / 'workspace.db')))
    assert not (tmp_path / 'core.db').exists() and not (tmp_path / 'workspace.db').exists()

def test_targets_must_be_new_and_the_command_saves_its_report(tmp_path):
    source = restore(tmp_path, 'platform-demo')
    (tmp_path / 'used.db').write_bytes(b'')
    with pytest.raises(ValueError, match='new database'):
        split.split(arguments(tmp_path, source, str(tmp_path / 'core.db'), str(tmp_path / 'used.db')))
    with pytest.raises(ValueError, match='must all differ'):
        split.split(arguments(tmp_path, source, str(source), str(tmp_path / 'workspace.db')))
    command_line = [sys.executable, '-m', 'tools.split', str(source), '--core', str(tmp_path / 'core.db'), '--workspace', str(tmp_path / 'workspace.db'),
                    '--report', str(tmp_path / 'cli' / 'report.json'), '--core-home', str(CORE_HOME), '--core-python', CORE_PYTHON]
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(command_line, cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads((tmp_path / 'cli' / 'report.json').read_text())['status'] == 'PASS'
    assert '| entities | 7 | 7 |' in (tmp_path / 'cli' / 'report.md').read_text()
    assert subprocess.run(command_line, cwd=root, capture_output=True, text=True).returncode != 0
