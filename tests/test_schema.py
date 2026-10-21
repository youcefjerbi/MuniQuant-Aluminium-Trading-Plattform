"""DC1 step B1: the Workspace's own migration line creates exactly its own tables."""
import json
import re
from pathlib import Path
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from app.models import Base

WORKSPACE_TABLES = {'lead', 'lead_revision', 'lead_headline', 'research_event', 'research_quote', 'research_outcome', 'paper_policy',
                    'research_paper_account', 'research_paper_decision', 'investigation', 'investigation_revision', 'investigation_entry',
                    'investigation_task', 'investigation_task_evidence', 'asset_location', 'asset_dependency', 'market_observations',
                    'paper_accounts', 'paper_orders', 'audit'}
# The licensed lead feed's store: today's platform table each one comes from.
LEAD_STORE = {'lead_source': 'sources', 'lead_source_access': 'source_access', 'lead_snapshot': 'source_snapshot', 'lead_document': 'documents',
              'lead_document_version': 'document_version', 'lead_source_document': 'source_document_relation', 'lead_run': 'runs',
              'lead_retrieval_attempt': 'retrieval_attempt'}
CORE_TABLES = {'entities', 'company', 'facility', 'country', 'region', 'facility_type', 'commodity', 'entity_alias', 'entity_supersession',
               'entity_evidence', 'sources', 'source_access', 'documents', 'document_version', 'source_snapshot', 'source_document_relation',
               'runs', 'retrieval_attempt', 'observations', 'observation_detail', 'relationships', 'company_facility_relationship',
               'evidence_build', 'candidate', 'reviews'}
# Links to Core tables that became plain reference fields: (table, column, Core table).
REFERENCE_FIELDS = {('lead', 'primary_document_id', 'documents'), ('lead', 'observation_id', 'observations'),
                    ('investigation_entry', 'document_id', 'documents'), ('asset_location', 'entity_id', 'entities'),
                    ('asset_location', 'document_id', 'documents'), ('asset_dependency', 'from_entity_id', 'entities'),
                    ('asset_dependency', 'to_entity_id', 'entities'), ('asset_dependency', 'document_id', 'documents'),
                    ('market_observations', 'document_id', 'documents')}
TODAY = Path(__file__).parent / 'fixtures' / 'schema'

def describe(engine, tables):
    """Normalized structure of the tables: columns in order, keys, indexes and checks."""
    inspector = inspect(engine)
    norm = lambda sql: re.sub(r'\s+', ' ', sql or '').strip()
    result = {}
    for table in sorted(tables):
        result[table] = {
            'columns': [[c['name'], str(c['type']), c['nullable'], norm(str(c['default'])) if c.get('default') is not None else None] for c in inspector.get_columns(table)],
            'primary_key': sorted(inspector.get_pk_constraint(table)['constrained_columns']),
            'foreign_keys': sorted([fk['constrained_columns'], fk['referred_table'], fk['referred_columns']] for fk in inspector.get_foreign_keys(table)),
            'unique': sorted(sorted(u['column_names']) for u in inspector.get_unique_constraints(table)),
            'indexes': sorted([i['name'], i['column_names'], bool(i['unique'])] for i in inspector.get_indexes(table)),
            'checks': sorted([c.get('name'), norm(c['sqltext'])] for c in inspector.get_check_constraints(table))}
    return result

def expected_from_today(today):
    """Today's platform tables with the split applied: lead store renamed, Core links made plain fields."""
    renamed = {old: new for new, old in LEAD_STORE.items()}
    def rename(name):
        # Generated names start with the table name: ix_documents_source_id, documents_version_check, ...
        for old, new in sorted(renamed.items(), key=lambda item: -len(item[0])):
            for prefix in ('ix_', ''):
                if name and name.startswith(prefix + old + '_'): return prefix + new + name[len(prefix + old):]
        return name
    expected = {}
    for table in sorted(WORKSPACE_TABLES | set(LEAD_STORE.values())):
        entry = json.loads(json.dumps(today['tables'][table]))
        name = renamed.get(table, table)
        dropped = {column for owner, column, _ in REFERENCE_FIELDS if owner == name}
        entry['foreign_keys'] = sorted([columns, renamed.get(referred, referred), referred_columns] for columns, referred, referred_columns in entry['foreign_keys']
                                       if not (len(columns) == 1 and columns[0] in dropped))
        entry['indexes'] = sorted([rename(index), columns, unique] for index, columns, unique in entry['indexes'])
        entry['checks'] = sorted([rename(check), sql] for check, sql in entry['checks'])
        if name == 'lead_source_access':
            # Every lead source is lead-only: the platform's usage_scope column and its check are gone.
            entry['columns'] = [column for column in entry['columns'] if column[0] != 'usage_scope']
            entry['checks'] = [check for check in entry['checks'] if check[0] != 'ck_source_access_usage']
        expected[name] = entry
    return expected

def migrated(new_database, monkeypatch):
    url = new_database('schema')
    monkeypatch.setenv('DATABASE_URL', url)
    command.upgrade(Config('alembic.ini'), 'head')
    return url

def test_single_straight_migration_line():
    script = ScriptDirectory.from_config(Config('alembic.ini'))
    revisions = list(script.walk_revisions())
    assert len(revisions) == 1 and len(script.get_bases()) == 1 and len(script.get_heads()) == 1
    assert not any(revision.branch_labels for revision in revisions)

def test_models_declare_exactly_the_workspace_tables():
    assert set(Base.metadata.tables) == WORKSPACE_TABLES | set(LEAD_STORE)
    assert not set(Base.metadata.tables) & CORE_TABLES
    for table in Base.metadata.tables.values():
        assert not {key.column.table.name for key in table.foreign_keys} & CORE_TABLES, table.name

def test_exact_tables_and_drift(new_database, monkeypatch):
    url = migrated(new_database, monkeypatch)
    command.check(Config('alembic.ini'))
    engine = create_engine(url)
    try:
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) == WORKSPACE_TABLES | set(LEAD_STORE) | {'alembic_version'}
        assert not inspector.get_view_names()
        if engine.dialect.name == 'postgresql':
            with engine.connect() as connection:
                assert not connection.execute(text('SELECT trigger_name FROM information_schema.triggers WHERE trigger_schema = current_schema()')).all()
    finally: engine.dispose()

def test_baseline_matches_todays_platform_tables(new_database, monkeypatch):
    url = migrated(new_database, monkeypatch)
    engine = create_engine(url)
    try:
        dialect = engine.dialect.name
        actual = describe(engine, WORKSPACE_TABLES | set(LEAD_STORE))
    finally: engine.dispose()
    today = json.loads((TODAY / f'today-{dialect}.json').read_text())
    expected = expected_from_today(today)
    for table in sorted(expected):
        assert actual[table] == expected[table], table
    if dialect == 'postgresql':
        # Today's search triggers, replaced by app.permutable.refresh_search.
        assert {name for _, name in today['triggers']} == {'search_entity_changed', 'search_parent_changed', 'search_child_changed'}

def test_migration_round_trip(new_database, monkeypatch):
    migrated(new_database, monkeypatch)
    config = Config('alembic.ini')
    command.downgrade(config, 'base')
    command.upgrade(config, 'head')
    command.check(config)
