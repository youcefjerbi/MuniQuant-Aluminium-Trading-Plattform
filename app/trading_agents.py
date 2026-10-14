"""Evidence-only TradingAgents orchestration; all Core reads use HTTP."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlsplit
import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import httpx
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from .models import now, uid
from .research import Conflict, stamp
from .research_models import PaperAccount, ResearchQuote
from .trading_agent_models import TradingAgentRun

UPSTREAM_COMMIT = '1394a3f72aa4393e1a98f51b382434c4b4c2d972'
MAX_SECONDS = 240
MAX_PACKAGE_BYTES = 5_000_000


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_key: str = Field(min_length=8, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    instrument: str = Field(min_length=1, max_length=64, pattern=r'^[A-Z0-9_.-]+$')
    entity_ids: list[str] = Field(min_length=1, max_length=10)
    mapping_rationale: str = Field(min_length=10, max_length=2000)
    consent: bool

    @field_validator('entity_ids')
    @classmethod
    def bounded_ids(cls, values):
        if len(values) != len(set(values)) or any(not v or len(v) > 128 for v in values):
            raise ValueError('Choose distinct Core entity IDs')
        return sorted(values)

    @field_validator('mapping_rationale')
    @classmethod
    def rationale(cls, value):
        if len(value.strip()) < 10:
            raise ValueError('Explain how the selected evidence relates to this instrument')
        return value.strip()


def logical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def settings():
    provider = os.getenv('TRADING_AGENTS_PROVIDER', 'openai')
    return {'provider': provider, 'quick_model': os.getenv('TRADING_AGENTS_QUICK_MODEL', ''),
            'deep_model': os.getenv('TRADING_AGENTS_DEEP_MODEL', ''),
            'base_url': os.getenv('TRADING_AGENTS_OLLAMA_URL', 'http://localhost:11434/v1') if provider == 'ollama' else None}


def status():
    config = settings()
    enabled = os.getenv('TRADING_AGENTS_ENABLED', 'false').lower() == 'true'
    try:
        from .trading_agent_adapter import _assert_upstream
        _assert_upstream()
        dependency = True
    except (importlib.metadata.PackageNotFoundError, ValueError):
        dependency = False
    configured = config['provider'] in ('openai', 'ollama') and bool(config['quick_model'] and config['deep_model'])
    if config['provider'] == 'openai':
        configured = configured and bool(os.getenv('OPENAI_API_KEY'))
    core = bool(os.getenv('CORE_API_URL'))
    reasons = []
    if not enabled: reasons.append('Evidence trading agents are disabled on this server.')
    if not core: reasons.append('Connect the Data Core API to browse accepted evidence.')
    if not dependency: reasons.append('Install the optional TradingAgents integration on the server.')
    if not configured: reasons.append('Configure the model provider and both model names on the server.')
    return {'enabled': enabled, 'configured': bool(configured), 'provider': config['provider'],
            'quick_model': config['quick_model'], 'deep_model': config['deep_model'],
            'core_configured': core, 'dependency_available': dependency, 'mode': 'paper',
            'reason': ' '.join(reasons), 'upstream_version': '0.6.0', 'upstream_commit': UPSTREAM_COMMIT}


def fetch_package():
    """A bounded, authenticated Core export; never read the Core database."""
    base = os.getenv('CORE_API_URL', '').rstrip('/')
    parsed = urlsplit(base)
    if not base or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Configure a valid CORE_API_URL on the server')
    if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1', '::1', 'core')):
        raise ValueError('Core must use HTTPS, or the local Core service')
    headers = {'Accept': 'application/json'}
    if os.getenv('CORE_API_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['CORE_API_TOKEN']
    try:
        with httpx.Client(timeout=15, follow_redirects=False, trust_env=False) as client:
            with client.stream('GET', base + '/api/export', headers=headers) as response:
                if response.status_code != 200:
                    raise ValueError('Core export is unavailable or blocked by Core access/quality checks')
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > MAX_PACKAGE_BYTES:
                        raise ValueError('Core export exceeds the 5 MB analysis limit; narrow the supported export before retrying')
        package = json.loads(raw)
        validate_package(package)
        return package
    except (httpx.HTTPError, json.JSONDecodeError):
        raise ValueError('Could not read a valid evidence package from Core') from None


def validate_package(package):
    schema = json.loads((Path(__file__).parent / 'evidence-v1.schema.json').read_text())
    if not Draft202012Validator(schema, format_checker=FormatChecker()).is_valid(package):
        raise ValueError('Core returned an invalid CommodityEvidencePackage 1.0.0')
    if logical_hash({k: v for k, v in package.items() if k != 'build_hash'}) != package['build_hash']:
        raise ValueError('Core evidence fingerprint does not match its contents')
    entities = {e['external_entity_id']: e for e in package['entities']}
    documents = {d['document_id']: d for d in package['documents']}
    sources = {s['source_id']: s for s in package['sources']}
    if any(len({row[key] for row in package[collection]}) != len(package[collection]) for collection, key in
           [('entities', 'external_entity_id'), ('documents', 'document_id'), ('sources', 'source_id'), ('records', 'record_id')]):
        raise ValueError('Core export contains duplicate identities')
    for fact in package['records']:
        doc, source = documents.get(fact['document_id']), sources.get(fact['source_id'])
        if not doc or not source or fact['external_entity_id'] not in entities or doc['content_hash'] != fact['content_hash'] or doc['source_id'] != fact['source_id']:
            raise ValueError('Core fact provenance is inconsistent')
        identity = entities[fact['external_entity_id']]
        identity_fields = ('entity_type', 'canonical_name', 'aliases', 'facility_type', 'country', 'region', 'commodity')
        if identity['entity_type'] != 'facility' or any(fact[key] != identity[key] for key in identity_fields):
            raise ValueError('Core fact identity differs from its registry')
        if (fact['publisher'] != source['publisher'] or fact['source_url'] != doc['original_url'] or
            any(fact[key] != doc[key] for key in ('published_at', 'retrieved_at')) or
            fact['synthetic'] != (source['source_type'] == 'synthetic')):
            raise ValueError('Core fact source metadata is inconsistent')
        if fact['valid_to'] and fact['valid_to'] < fact['valid_from']:
            raise ValueError('Core fact validity interval is inconsistent')


def evidence_catalog():
    package = fetch_package()
    return {'build_hash': package['build_hash'],
            'entities': [{'id': e['external_entity_id'], 'name': e['canonical_name']} for e in package['entities']],
            'records': [{'record_id': r['record_id'], 'entity_id': r['external_entity_id'],
                         'title': r['canonical_name'] + ' · ' + r['attribute_type'],
                         'quality_status': r['quality_status'], 'synthetic': r['synthetic']} for r in package['records']]}


def prepare(s, data):
    package = fetch_package()
    clock = now()
    today = clock[:10]
    entities = [e for e in package['entities'] if e['external_entity_id'] in data.entity_ids]
    if len(entities) != len(data.entity_ids): raise ValueError('Selected entity is absent from Core')
    facts = [r for r in package['records'] if r['external_entity_id'] in data.entity_ids and
             r['valid_from'] <= today and (not r['valid_to'] or r['valid_to'] >= today)]
    if not facts: raise ValueError('No currently valid accepted Core observations for the selected assets')
    if len(facts) > 50: raise ValueError('More than 50 selected facts; choose fewer assets')
    account = s.get(PaperAccount, 'paper')
    if not account or account.instrument != data.instrument:
        raise ValueError('Configure the paper account for this exact instrument first')
    portfolio = {k: getattr(account, k) for k in ('cash', 'quantity', 'version', 'policy_id', 'instrument')}
    quotes = s.scalars(select(ResearchQuote).where(ResearchQuote.instrument == data.instrument,
        ResearchQuote.known_at <= clock, ResearchQuote.observed_at <= clock, ResearchQuote.historical == 0)
        .order_by(ResearchQuote.observed_at.desc(), ResearchQuote.id).limit(100)).all()
    quote_data = [{k: getattr(q, k) for k in ('id', 'instrument', 'price', 'observed_at', 'known_at', 'source_reference')} for q in reversed(quotes)]
    if not quotes or (stamp(clock) - stamp(quotes[0].observed_at)).total_seconds() > 300:
        raise ValueError('Record a nonhistorical price quote from the last five minutes first')
    refs, selected = [], []
    guards = []
    for index, fact in enumerate(sorted(facts, key=lambda x: x['record_id']), 1):
        citation = 'E' + str(index)
        selected.append({**fact, 'citation': citation})
        refs.append({'citation': citation, 'record_id': fact['record_id'], 'entity_id': fact['external_entity_id'],
                     'document_id': fact['document_id'], 'document_version_id': fact['document_id'],
                     'content_hash': fact['content_hash'], 'quality_status': fact['quality_status'], 'synthetic': fact['synthetic']})
        if fact['synthetic']: guards.append('Synthetic evidence is analysis-only')
        if fact['quality_status'] != 'PASS': guards.append('Selected evidence has unresolved quality warnings')
        if (stamp(clock) - stamp(fact['retrieved_at'])).total_seconds() > 365 * 86400:
            guards.append('Selected evidence was retrieved more than one year ago')
        if stamp(fact['retrieved_at']) > stamp(clock): guards.append('Evidence capture is future-dated')
        if fact.get('published_at') and fact['published_at'][:10] > today:
            guards.append('Evidence publication is future-dated')
    doc_ids = {r['document_id'] for r in facts}
    source_ids = {r['source_id'] for r in facts}
    context = {'instrument': data.instrument, 'as_of': clock, 'mapping_rationale': data.mapping_rationale,
        'evidence': {'package_version': '1.0.0', 'build_hash': package['build_hash'], 'records': selected,
                     'entities': entities, 'documents': [d for d in package['documents'] if d['document_id'] in doc_ids],
                     'sources': [v for v in package['sources'] if v['source_id'] in source_ids],
                     'quality': {'guard_reasons': sorted(set(guards))}},
        'quotes': quote_data, 'portfolio': portfolio}
    if len(json.dumps(context).encode()) > 100_000: raise ValueError('Selected analysis context is too large')
    # Store references and decision inputs, not a shadow Core master/fact store.
    inputs = {'as_of': clock, 'build_hash': package['build_hash'], 'context_hash': logical_hash(context),
              'entity_ids': data.entity_ids, 'record_ids': [r['record_id'] for r in facts], 'evidence_refs': refs,
              'portfolio': portfolio, 'quotes': quote_data, 'mapping_rationale': data.mapping_rationale,
              'guard_reasons': sorted(set(guards)), 'models': settings()}
    return inputs, context


def public_run(run):
    return {key: getattr(run, key) for key in ('id', 'status', 'instrument', 'created_at', 'completed_at', 'actor',
                                              'inputs', 'result', 'error', 'paper_decision_id')}


def expire_abandoned(s):
    # No process may run beyond the hard worker timeout. Reclaim crash-abandoned slots.
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=MAX_SECONDS + 60)).isoformat()
    s.execute(update(TradingAgentRun).where(TradingAgentRun.active_slot.is_not(None), TradingAgentRun.created_at < cutoff)
              .values(status='failed', active_slot=None, completed_at=now(), error='Analysis expired; retry with current evidence'))
    s.commit()


def create_run(s, data, actor):
    existing = s.scalar(select(TradingAgentRun).where(TradingAgentRun.request_key == data.request_key))
    if existing:
        if existing.actor != actor or existing.instrument != data.instrument or existing.inputs['entity_ids'] != data.entity_ids or existing.inputs['mapping_rationale'] != data.mapping_rationale:
            raise Conflict('Request key already belongs to another analysis')
        return existing, None
    state = status()
    if not all(state[k] for k in ('enabled', 'configured', 'core_configured', 'dependency_available')):
        raise ValueError(state['reason'])
    if not data.consent: raise ValueError('Confirm sending selected evidence and simulated holdings to the configured model provider')
    expire_abandoned(s)
    if s.scalar(select(TradingAgentRun.id).where(TradingAgentRun.active_slot.is_not(None))):
        raise Conflict('An analysis is already active; wait or cancel it')
    inputs, context = prepare(s, data)
    run = TradingAgentRun(id=uid(), request_key=data.request_key, instrument=data.instrument, status='queued',
                          active_slot='workspace', actor=actor, inputs=inputs, created_at=now())
    s.add(run); s.commit(); s.refresh(run)
    return run, context


def guarded_result(result, inputs):
    if not isinstance(result, dict) or result.get('action') not in ('BUY', 'SELL', 'HOLD'):
        raise ValueError('Agent did not return a structured action')
    if result.get('upstream_commit') != UPSTREAM_COMMIT:
        raise ValueError('Unexpected TradingAgents implementation version')
    if not isinstance(result.get('reasoning'), str) or not result['reasoning'].strip() or len(result['reasoning']) > 24000:
        raise ValueError('Agent reasoning is missing or exceeds the limit')
    reports = result.get('reports', {})
    if not isinstance(reports, dict) or len(reports) > 20 or any(not isinstance(k, str) or not isinstance(v, str) or len(v) > 24000 for k, v in reports.items()):
        raise ValueError('Agent reports exceed the supported structure')
    citations = result.get('citations')
    if not isinstance(citations, list) or any(not isinstance(c, str) for c in citations):
        raise ValueError('Agent citations are invalid')
    permitted = {r['citation'] for r in inputs['evidence_refs']}
    mentioned = set(re.findall(r'\[(E[^\]]*)\]', result['reasoning'] + '\n' + '\n'.join(reports.values())))
    reasons = list(inputs['guard_reasons'])
    if not citations or not set(citations) <= permitted or not mentioned <= permitted or not set(citations) <= mentioned:
        reasons.append('Missing or unknown evidence citations; proposal cannot be executed')
    return {**result, 'execution_allowed': not reasons, 'guard_reasons': sorted(set(reasons))}


def worker_environment():
    # Inherit runtime/library essentials only. Provider telemetry and unrelated app secrets stay out.
    allowed = ('PATH', 'HOME', 'TMPDIR', 'SYSTEMROOT', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'LANG', 'LC_ALL')
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env['PYTHON_DOTENV_DISABLED'] = '1'
    env['LANGCHAIN_TRACING_V2'] = 'false'
    env['LANGSMITH_TRACING'] = 'false'
    if settings()['provider'] == 'openai' and os.getenv('OPENAI_API_KEY'):
        env['OPENAI_API_KEY'] = os.environ['OPENAI_API_KEY']
    return env


def execute_worker(context, config, cancelled):
    payload = json.dumps({'context': context, 'config': config}).encode()
    with tempfile.TemporaryFile() as input_file, tempfile.TemporaryFile() as output_file:
        input_file.write(payload); input_file.seek(0)
        process = subprocess.Popen([sys.executable, '-m', 'app.trading_agent_worker'], stdin=input_file,
            stdout=output_file, stderr=subprocess.DEVNULL, env=worker_environment(), cwd=str(Path(__file__).parents[1]))
        start = time.monotonic()
        try:
            while process.poll() is None:
                if cancelled(): raise ValueError('Analysis cancelled')
                if time.monotonic() - start > MAX_SECONDS: raise ValueError('Agent analysis timed out')
                if output_file.tell() > 500_000: raise ValueError('Agent output exceeded its limit')
                time.sleep(0.25)
            output_file.seek(0); raw = output_file.read(500_001)
            if len(raw) > 500_000: raise ValueError('Agent output exceeded its limit')
            result = json.loads(raw)
            if process.returncode or result.get('error'):
                raise ValueError('TradingAgents analysis failed; check provider configuration and retry')
            return result['result']
        except (json.JSONDecodeError, KeyError):
            raise ValueError('TradingAgents returned an invalid response') from None
        finally:
            if process.poll() is None:
                process.kill(); process.wait(timeout=5)


def run_background(engine, identifier, context):
    with Session(engine) as s:
        run = s.get(TradingAgentRun, identifier)
        if not run or run.status != 'queued': return
        run.status = 'running'; s.commit()
        inputs = run.inputs
    def cancelled():
        with Session(engine) as current:
            state = current.get(TradingAgentRun, identifier)
            return not state or state.status != 'running'
    result, error = None, None
    try:
        result = guarded_result(execute_worker(context, inputs['models'], cancelled), inputs)
    except Exception:
        error = 'Analysis failed or timed out. No paper trade was placed; check model setup and retry.'
    with Session(engine) as s:
        run = s.get(TradingAgentRun, identifier)
        if not run or run.status != 'running': return
        run.status = 'failed' if error else 'completed'
        run.result, run.error, run.completed_at, run.active_slot = result, error, now(), None
        s.commit()


def cancel(s, run, actor):
    if run.actor != actor: raise Conflict('Only the initiating identity may cancel this analysis')
    if run.status in ('queued', 'running'):
        run.status = 'cancelled'; run.active_slot = None; run.completed_at = now(); s.commit()
    return public_run(run)


def apply_paper(s, run, actor):
    if run.actor != actor: raise Conflict('Only the initiating identity may apply this proposal')
    if run.paper_decision_id:
        from .research_models import PaperDecision
        from .services import record
        return record(s.get(PaperDecision, run.paper_decision_id))
    if run.status != 'completed': raise Conflict('Wait for a completed analysis')
    if fetch_package()['build_hash'] != run.inputs['build_hash']:
        raise Conflict('Core evidence changed since analysis; run a new analysis')
    run.result = guarded_result(run.result, run.inputs)
    from .trading_agent_paper import apply_agent_decision
    from .services import record
    decision = apply_agent_decision(s, run, actor)
    s.commit()
    return record(decision)
