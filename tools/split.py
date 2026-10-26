"""Split an existing MuniQuant platform database into a new Data Core and a new Workspace database.

DC1 step B3. The source is opened read-only and never changed (a SQLite source is fingerprinted
before and after). Both targets must be new: a SQLite path that does not exist yet, or a
PostgreSQL database without tables. --dry-run checks everything and writes only the report.

Every source row goes to exactly one side, unchanged:
- Workspace: leads, research and practice trading, investigations, the map and the old trading
  tables, and the licensed lead feeds (Permutable): every source with a lead-only access decision,
  with its access decisions, responses, saved copies, capture runs and attempt logs, which move into
  the Workspace's lead store. Change-history rows go with the record they describe.
- Data Core: everything else in the 26 Core tables. The Core's own import tool writes it
  (tools/core_import.py in the Core repository, run in the Core's environment), leaving out the rows
  that went to the Workspace; the Workspace never writes the Core database itself.
A saved copy used on both sides is copied to both. The source is refused, and nothing is written,
when a Core fact, link or identity cites a lead-feed document, when a source mixes lead-only and
evidence access decisions, or when it holds tables this tool does not know.

The report compares, for every source table, the rows in the source with the rows on each side:
counts, IDs and fingerprints. It also lists Workspace references to Core records that point to
lead-store records instead; they are kept as they are and reported, never changed.

    python -m tools.split SOURCE --core CORE --workspace WORKSPACE --report REPORT.json
                          [--snapshots DIR --core-snapshots NEW_DIR --workspace-snapshots NEW_DIR]
                          [--core-home PATH] [--core-python PATH] [--dry-run]

SOURCE, CORE and WORKSPACE are SQLAlchemy URLs or SQLite file paths. CORE_HOME (default
../muniquant-data-core) is a Data Core checkout and CORE_PYTHON (default CORE_HOME/.venv/bin/python)
an interpreter with it installed.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import date, datetime
from uuid import NAMESPACE_URL, uuid5
from decimal import Decimal
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import column, create_engine, inspect, select, table as table_clause, text
from sqlalchemy.engine import make_url
from app.db import make_engine
from app.models import Base

ROOT = Path(__file__).resolve().parents[1]
# The platform head this tool knows: commit 26a0bcd, the last release before the split.
SOURCE_REVISION = 'd8317b920a11'
PERMUTABLE_SOURCE = str(uuid5(NAMESPACE_URL, 'muniquant:source:permutable-ai'))  # app.permutable.SOURCE_ID
CORE_TABLES = {'entities', 'company', 'facility', 'country', 'region', 'facility_type', 'commodity', 'entity_alias', 'entity_supersession',
               'entity_evidence', 'sources', 'source_access', 'documents', 'document_version', 'source_snapshot', 'source_document_relation',
               'runs', 'retrieval_attempt', 'observations', 'observation_detail', 'relationships', 'company_facility_relationship',
               'evidence_build', 'candidate', 'reviews', 'audit'}
# Platform table -> Workspace lead-store table for the lead feeds' rows.
LEAD_STORE = {'sources': 'lead_source', 'source_access': 'lead_source_access', 'source_snapshot': 'lead_snapshot', 'documents': 'lead_document',
              'document_version': 'lead_document_version', 'source_document_relation': 'lead_source_document', 'runs': 'lead_run',
              'retrieval_attempt': 'lead_retrieval_attempt'}
WORKSPACE_TABLES = sorted(set(Base.metadata.tables) - set(LEAD_STORE.values()))
KEYS = {name: [c.name for c in table.primary_key.columns] for name, table in Base.metadata.tables.items()}
# Core facts and identities that may only cite evidence documents: (table, identifying column, document column).
CITATIONS = [('observations', 'id', 'document_id'), ('relationships', 'id', 'document_id'), ('company_facility_relationship', 'relationship_id', 'document_id'),
             ('entity_evidence', 'entity_id', 'document_id'), ('evidence_build', 'id', 'document_id')]
# Workspace fields that hold Core IDs: (table, column, Core table).
CORE_REFERENCES = [('lead', 'primary_document_id', 'documents'), ('lead', 'observation_id', 'observations'), ('investigation_entry', 'document_id', 'documents'),
                   ('asset_location', 'entity_id', 'entities'), ('asset_location', 'document_id', 'documents'), ('asset_dependency', 'from_entity_id', 'entities'),
                   ('asset_dependency', 'to_entity_id', 'entities'), ('asset_dependency', 'document_id', 'documents'), ('market_observations', 'document_id', 'documents')]

def location_url(location):
    url = make_url(location if '://' in location else 'sqlite:///' + str(Path(location).resolve()))
    if url.drivername.startswith('sqlite') and (not url.database or url.database == ':memory:'):
        raise ValueError('Use a SQLite file path, not an in-memory database')
    return url

def file_sha256(url):
    if not url.drivername.startswith('sqlite'): return None
    return hashlib.sha256(Path(url.database).read_bytes()).hexdigest()

def open_source(url):
    if url.drivername.startswith('sqlite'):
        path = Path(url.database).resolve()
        if not path.is_file(): raise ValueError('Source database not found: ' + str(path))
        return create_engine(f'sqlite:///file:{path}?mode=ro&uri=true')
    options = (url.query.get('options', '') + ' -c default_transaction_read_only=on').strip()
    return create_engine(url.update_query_dict({'options': options}))

def require_new_target(url):
    if url.drivername.startswith('sqlite'):
        path = Path(url.database)
        for candidate in (path, Path(str(path) + '-journal'), Path(str(path) + '-wal')):
            if candidate.exists(): raise ValueError('Target must be a new database; refusing existing ' + str(candidate))
        return
    engine = create_engine(url)
    try:
        inspector = inspect(engine)
        if inspector.get_table_names() or inspector.get_view_names(): raise ValueError('Target PostgreSQL database must be empty')
    finally: engine.dispose()

def canonical(value):
    if isinstance(value, Decimal): return format(value.normalize(), 'f')
    if isinstance(value, float): return repr(value)
    if isinstance(value, (date, datetime)): return value.isoformat()
    return value

def fingerprint(rows):
    content = [[[key, canonical(row[key])] for key in sorted(row)] for row in rows]
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str).encode()).hexdigest()

def key_of(row, keys):
    return tuple(str(row[name]) for name in keys)

def read(connection, name, model):
    """Every row of a source table through the Workspace column types, in key order."""
    keys = [c.name for c in model.primary_key.columns]
    columns = [column(c.name, c.type) for c in model.columns]
    rows = [dict(row._mapping) for row in connection.execute(select(*columns).select_from(table_clause(name)))]
    return sorted(rows, key=lambda row: key_of(row, keys))

def read_source(connection):
    """Rows of the Workspace tables and of the platform tables that may hold lead-feed rows."""
    inspector = inspect(connection)
    tables = set(inspector.get_table_names()) - {'alembic_version'}
    unknown = sorted(tables - CORE_TABLES - set(WORKSPACE_TABLES))
    if unknown: raise ValueError('Unknown tables in the source; nothing would be dropped silently: ' + ', '.join(unknown))
    missing = sorted((CORE_TABLES | set(WORKSPACE_TABLES)) - tables)
    if missing: raise ValueError('Not a MuniQuant platform database at revision ' + SOURCE_REVISION + '; missing: ' + ', '.join(missing))
    revision = connection.execute(text('SELECT version_num FROM alembic_version')).scalar()
    if revision != SOURCE_REVISION:
        raise ValueError(f'Source is at revision {revision}; upgrade a copy with the platform at commit 26a0bcd (revision {SOURCE_REVISION}) first')
    rows = {name: read(connection, name, Base.metadata.tables[name]) for name in WORKSPACE_TABLES}
    for name, store in LEAD_STORE.items():
        model = Base.metadata.tables[store]
        extra = ['usage_scope'] if name == 'source_access' else []
        typed = [column(c.name, c.type) for c in model.columns] + [column(x) for x in extra]
        keys = [c.name for c in model.primary_key.columns]
        rows[name] = sorted((dict(row._mapping) for row in connection.execute(select(*typed).select_from(table_clause(name)))), key=lambda row: key_of(row, keys))
    for name, identifier, field in CITATIONS:
        rows['cites_' + name] = [dict(row._mapping) for row in connection.execute(select(column(identifier).label('id'), column(field).label('document_id')).select_from(table_clause(name)))]
    for name in ('entities', 'observations'):
        rows['core_' + name] = set(connection.execute(select(column('id')).select_from(table_clause(name))).scalars())
    rows['core_documents'] = {row['id'] for row in rows['documents']}
    rows['counts'] = {name: connection.execute(text(f'SELECT COUNT(*) FROM {name}')).scalar() for name in sorted(tables)}
    return revision, rows

def classify(rows):
    """Decide the side of every row; refuse sources the split cannot separate cleanly."""
    problems = []
    access = {}
    for row in rows['source_access']: access.setdefault(row['source_id'], set()).add(row['usage_scope'])
    lead_sources = {source for source, scopes in access.items() if 'leads_only' in scopes}
    lead_sources |= {row['source_id'] for row in rows['lead']}
    lead_sources |= {PERMUTABLE_SOURCE} & {row['id'] for row in rows['sources']}
    for source in sorted(lead_sources):
        if access.get(source, {'leads_only'}) != {'leads_only'}:
            problems.append(f'source {source} has both lead-only and evidence access decisions; record one usage before splitting')
    documents = {row['id'] for row in rows['documents'] if row['source_id'] in lead_sources}
    for name in ('lead_revision', 'lead_headline'):
        for row in rows[name]:
            if row['document_id'] not in documents: problems.append(f"{name} {row['id']} cites document {row['document_id']}, which is not a lead-feed response")
    for name, _, _ in CITATIONS:
        for row in rows['cites_' + name]:
            if row['document_id'] in documents: problems.append(f"{name} {row['id']} cites lead-feed document {row['document_id']}; cite the primary source before splitting")
    for row in rows['source_document_relation']:
        if (row['source_id'] in lead_sources) != (row['document_id'] in documents):
            problems.append(f"source_document_relation {row['source_id']}/{row['document_id']} links a lead feed with evidence")
    if problems: raise ValueError('The source cannot be split as it is: ' + '; '.join(problems[:20]))
    lead_hashes = {row['content_hash'] for row in rows['documents'] if row['id'] in documents} | {row['snapshot_hash'] for row in rows['document_version'] if row['document_id'] in documents}
    core_hashes = {row['content_hash'] for row in rows['documents'] if row['id'] not in documents} | {row['snapshot_hash'] for row in rows['document_version'] if row['document_id'] not in documents}
    def lead_run(row):
        manifest = row['manifest'] if isinstance(row['manifest'], dict) else {}
        return (manifest.get('source_id') in lead_sources or manifest.get('document_id') in documents
                or manifest.get('adapter') in ('permutable-leads', 'permutable-api-v1'))
    runs = {row['id'] for row in rows['runs'] if lead_run(row)}
    side = {
        'sources': {row['id'] for row in rows['sources'] if row['id'] in lead_sources},
        'source_access': {row['id'] for row in rows['source_access'] if row['source_id'] in lead_sources},
        'documents': documents,
        'document_version': {row['document_id'] for row in rows['document_version'] if row['document_id'] in documents},
        'source_document_relation': {(row['source_id'], row['document_id']) for row in rows['source_document_relation'] if row['document_id'] in documents},
        'source_snapshot': {row['content_hash'] for row in rows['source_snapshot'] if row['content_hash'] in lead_hashes},
        'runs': runs,
        'retrieval_attempt': {row['id'] for row in rows['retrieval_attempt'] if row['run_id'] in runs},
    }
    shared = sorted(side['source_snapshot'] & core_hashes)
    workspace_ids = set().union(*[{str(row[c.name]) for row in rows[name] for c in Base.metadata.tables[name].primary_key.columns}
                                  for name in WORKSPACE_TABLES if name != 'audit'])
    workspace_ids |= {str(i) for name in ('sources', 'source_access', 'documents', 'runs', 'retrieval_attempt') for i in side[name]}
    side['audit'] = {row['id'] for row in rows['audit'] if row['record_id'] in workspace_ids}
    return side, shared

def lead_store_rows(rows, side):
    """Rows for the Workspace lead store, exactly as in the source; usage_scope is lead-only by definition."""
    result = {}
    for name, store in LEAD_STORE.items():
        keys = [c.name for c in Base.metadata.tables[store].primary_key.columns]
        chosen = [row for row in rows[name] if (key_of(row, keys) if len(keys) > 1 else str(row[keys[0]])) in
                  ({tuple(map(str, k)) for k in side[name]} if len(keys) > 1 else {str(k) for k in side[name]})]
        result[store] = [{k: v for k, v in row.items() if k != 'usage_scope'} for row in chosen]
    return result

def references_outside_core(rows, side):
    """Workspace fields meant for Core IDs that point to records the Core will not hold."""
    found = []
    for table, field, target in CORE_REFERENCES:
        known = rows['core_documents'] - side['documents'] if target == 'documents' else rows['core_' + target]
        for row in rows[table]:
            value = row[field]
            if value is not None and value not in known:
                found.append({'table': table, 'id': row['id'], 'column': field, 'value': value,
                              'points_to': 'lead store' if value in side['documents'] else 'nothing'})
    return found

def migrate_workspace(url):
    config = Config(str(ROOT / 'alembic.ini'))
    config.set_main_option('script_location', str(ROOT / 'migrations'))
    previous = os.environ.get('DATABASE_URL')
    os.environ['DATABASE_URL'] = url.render_as_string(hide_password=False)
    try: command.upgrade(config, 'head')
    finally:
        if previous is None: os.environ.pop('DATABASE_URL', None)
        else: os.environ['DATABASE_URL'] = previous

def write_workspace(url, planned):
    require_new_target(url)
    if url.drivername.startswith('sqlite'): Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    try:
        migrate_workspace(url)
        engine = make_engine(url.render_as_string(hide_password=False))
        try:
            with engine.begin() as connection:
                for table in Base.metadata.sorted_tables:
                    if planned[table.name]: connection.execute(table.insert(), planned[table.name])
            with engine.connect() as connection:
                return {table.name: read(connection, table.name, table) for table in Base.metadata.sorted_tables}
        finally: engine.dispose()
    except Exception:
        if url.drivername.startswith('sqlite'): Path(url.database).unlink(missing_ok=True)
        raise

def core_import(args, source_url, excluded, dry_run, workdir):
    """Run the Core's own import tool in the Core's environment; return its report."""
    home = Path(args.core_home or os.getenv('CORE_HOME') or ROOT.parent / 'muniquant-data-core').resolve()
    python = args.core_python or os.getenv('CORE_PYTHON') or str(home / '.venv' / 'bin' / 'python')
    if not (home / 'tools' / 'core_import.py').is_file(): raise ValueError(f'Data Core checkout not found at {home}; set --core-home')
    exclusions, report = Path(workdir) / 'core-exclusions.json', Path(workdir) / 'core-import.json'
    exclusions.write_text(json.dumps({name: sorted([list(k) if isinstance(k, tuple) else k for k in keys]) for name, keys in excluded.items() if keys}, indent=1))
    target = location_url(args.core)
    command_line = [python, '-m', 'tools.core_import', source_url.render_as_string(hide_password=False), target.render_as_string(hide_password=False),
                    '--report', str(report), '--exclude', str(exclusions)]
    if args.snapshots: command_line += ['--snapshots', str(Path(args.snapshots).resolve()), '--target-snapshots', str(Path(args.core_snapshots).resolve())]
    if dry_run: command_line.append('--dry-run')
    result = subprocess.run(command_line, cwd=home, capture_output=True, text=True)
    if not report.exists(): raise ValueError('The Core import tool refused the Core side: ' + (result.stderr.strip().splitlines() or ['no output'])[-1])
    return json.loads(report.read_text()), json.loads(exclusions.read_text())

def copy_workspace_snapshots(directory, target, hashes):
    target = Path(target)
    target.mkdir(parents=True)
    problems = []
    for digest in hashes:
        source = Path(directory) / digest
        if not source.is_file(): problems.append(digest + ': missing'); continue
        shutil.copy2(source, target / digest)
        if hashlib.sha256((target / digest).read_bytes()).hexdigest() != digest: problems.append(digest + ': content does not match')
    return problems

def split(args):
    source_url = location_url(args.source)
    targets = [location_url(args.core), location_url(args.workspace)]
    rendered = [url.render_as_string(hide_password=False) for url in [source_url, *targets]]
    if len(set(rendered)) != 3: raise ValueError('Source, Core and Workspace databases must all differ')
    if bool(args.snapshots) != bool(args.core_snapshots and args.workspace_snapshots): raise ValueError('Give the snapshot directory and both new target directories')
    for directory in (args.core_snapshots, args.workspace_snapshots):
        if directory and Path(directory).exists(): raise ValueError('Target snapshot directory must be new: ' + str(directory))
    if not args.dry_run:
        for url in targets: require_new_target(url)
    before = file_sha256(source_url)
    engine = open_source(source_url)
    try:
        with engine.connect() as connection: revision, rows = read_source(connection)
    finally: engine.dispose()
    side, shared = classify(rows)
    planned = {name: rows[name] for name in WORKSPACE_TABLES if name != 'audit'}
    planned['audit'] = [row for row in rows['audit'] if row['id'] in side['audit']]
    planned.update(lead_store_rows(rows, side))
    excluded = {name: set(side[name]) - (set(shared) if name == 'source_snapshot' else set()) for name in LEAD_STORE}
    excluded['audit'] = side['audit']
    report = {'tool': 'tools.split', 'mode': 'dry-run' if args.dry_run else 'split',
              'source': {'url': source_url.render_as_string(hide_password=True), 'revision': revision, 'sha256_before': before},
              'core': {'url': targets[0].render_as_string(hide_password=True)}, 'workspace': {'url': targets[1].render_as_string(hide_password=True)},
              'lead_sources': sorted(side['sources']), 'snapshots_on_both_sides': shared,
              'workspace_references_outside_the_core': references_outside_core(rows, side), 'tables': {}}
    workdir = Path(tempfile.mkdtemp(prefix='split-'))
    try:
        imported, exclusions = core_import(args, source_url, excluded, args.dry_run, workdir)
        report['core']['import_report'] = imported
        report['core']['rows_left_out'] = exclusions
        written = None
        if not args.dry_run and imported.get('status') == 'PASS':
            try: written = write_workspace(targets[1], planned)
            except Exception:
                # Leave no half-split result behind: remove the new Core side as well.
                if targets[0].drivername.startswith('sqlite'): Path(targets[0].database).unlink(missing_ok=True)
                if args.core_snapshots: shutil.rmtree(args.core_snapshots, ignore_errors=True)
                raise
            if args.snapshots:
                hashes = sorted(row['content_hash'] for row in planned['lead_snapshot'])
                report['workspace']['snapshots'] = {'files': len(hashes), 'problems': copy_workspace_snapshots(args.snapshots, args.workspace_snapshots, hashes)}
    finally: shutil.rmtree(workdir, ignore_errors=True)
    # Before and after: every source row is on exactly one side (a shared saved copy on both), unchanged.
    for name in sorted(set(WORKSPACE_TABLES) | CORE_TABLES):
        entry = {'source_rows': rows['counts'][name]}
        if name in set(WORKSPACE_TABLES) | set(LEAD_STORE):
            store = LEAD_STORE.get(name, name)
            expected = planned[store]
            entry.update({'workspace_table': store, 'to_workspace': len(expected), 'workspace_fingerprint': fingerprint(expected)})
            if written is not None:
                entry.update({'workspace_rows': len(written[store]), 'workspace_rows_fingerprint': fingerprint(written[store])})
                entry['workspace_ids_equal'] = [key_of(row, KEYS[store]) for row in expected] == [key_of(row, KEYS[store]) for row in written[store]]
                entry['workspace_equal'] = entry['workspace_ids_equal'] and entry['workspace_fingerprint'] == entry['workspace_rows_fingerprint']
        if name in CORE_TABLES:
            core = imported['tables'][name]
            entry.update({'to_core': core['source_rows'], 'core_fingerprint': core['source_fingerprint']})
            if 'target_rows' in core: entry.update({'core_rows': core['target_rows'], 'core_ids_equal': core['ids_equal'], 'core_equal': core['equal']})
        both = len(shared) if name == 'source_snapshot' else 0
        entry['complete'] = entry.get('to_core', 0) + entry.get('to_workspace', 0) - both == entry['source_rows']
        report['tables'][name] = entry
    after = file_sha256(source_url)
    report['source'].update({'sha256_after': after, 'unchanged': before == after})
    complete = all(entry.get('complete', True) for entry in report['tables'].values())
    if args.dry_run:
        report['status'] = 'DRY_RUN_OK' if imported.get('status') == 'DRY_RUN_OK' and complete else 'FAIL'
    else:
        equal = written is not None and all(entry.get('workspace_equal', True) and entry.get('core_equal', True) for entry in report['tables'].values())
        snapshots_ok = not report['workspace'].get('snapshots', {}).get('problems') and not imported.get('snapshots', {}).get('target_problems')
        report['status'] = 'PASS' if imported.get('status') == 'PASS' and equal and complete and snapshots_ok and report['source']['unchanged'] else 'FAIL'
    return report

def markdown(report):
    lines = ['# Split report', '', f"Status: **{report['status']}** ({report['mode']})", '',
             f"Source: `{report['source']['url']}` at revision `{report['source']['revision']}`, unchanged: {report['source']['unchanged']}",
             f"Data Core: `{report['core']['url']}`", f"Workspace: `{report['workspace']['url']}`", '',
             f"Lead-feed sources moved to the Workspace: {len(report['lead_sources'])}; saved copies on both sides: {len(report['snapshots_on_both_sides'])}", '',
             '| Source table | Source rows | To Core | To Workspace | Equal after |', '|---|---|---|---|---|']
    for name, entry in report['tables'].items():
        equal = all(entry.get(k, True) for k in ('core_equal', 'workspace_equal', 'complete'))
        source = entry.get('source_rows', entry.get('to_core', entry.get('to_workspace')))
        target = entry.get('workspace_table', '')
        lines.append(f"| {name}{' → ' + target if target and target != name else ''} | {source} | {entry.get('to_core', '—')} | {entry.get('to_workspace', '—')} | {'yes' if equal else 'NO'} |")
    references = report['workspace_references_outside_the_core']
    lines += ['', f'Workspace references to Core records that point elsewhere (kept unchanged): {len(references)}']
    lines += [f"- {r['table']} {r['id']}.{r['column']} = {r['value']} ({r['points_to']})" for r in references[:50]]
    return '\n'.join(lines) + '\n'

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('source')
    parser.add_argument('--core', required=True, help='new Data Core database')
    parser.add_argument('--workspace', required=True, help='new Workspace database')
    parser.add_argument('--report', required=True, type=Path, help='new JSON report path; a Markdown summary is written next to it')
    parser.add_argument('--snapshots', type=Path, help="the source's snapshot directory")
    parser.add_argument('--core-snapshots', type=Path, help='new directory for the Core saved copies')
    parser.add_argument('--workspace-snapshots', type=Path, help='new directory for the lead-feed saved copies')
    parser.add_argument('--core-home', help='Data Core checkout (default: CORE_HOME or ../muniquant-data-core)')
    parser.add_argument('--core-python', help='interpreter with the Data Core installed (default: CORE_PYTHON or CORE_HOME/.venv/bin/python)')
    parser.add_argument('--dry-run', action='store_true', help='check everything and write the report only')
    args = parser.parse_args()
    summary = args.report.with_suffix('.md')
    if args.report.exists() or summary.exists(): parser.error('Report path already exists; choose a new one')
    try: report = split(args)
    except ValueError as exc: parser.exit(2, f'Refused: {exc}\n')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('x') as stream: json.dump(report, stream, indent=2, default=str)
    summary.write_text(markdown(report))
    print(json.dumps({'status': report['status'], 'report': str(args.report), 'summary': str(summary)}))
    raise SystemExit(0 if report['status'] in ('PASS', 'DRY_RUN_OK') else 1)

if __name__ == '__main__': main()
