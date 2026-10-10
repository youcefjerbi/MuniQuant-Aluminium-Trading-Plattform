import hashlib
import json
import unicodedata
import math
from decimal import Decimal, InvalidOperation
from pathlib import Path
from sqlalchemy import select, func
import muniquant_core
from .models import Entity, Source, Document, Observation, Review, Run, MarketObservation, Relationship, Audit

PIPELINE_VERSION = '0.1.0'

def normalize_capacity(value, unit):
    factors = {'t/year': Decimal(1), 'kt/year': Decimal(1000), 'Mt/year': Decimal(1000000)}
    if unit not in factors:
        raise ValueError('Unsupported capacity unit')
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError('Capacity must be numeric') from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError('Capacity must be finite and nonnegative')
    result = float(amount * factors[unit])
    if not math.isfinite(result):
        raise ValueError('Capacity overflow')
    # Legacy storage is float; reported decimal text remains unchanged.
    return result


def record(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

def canonical(name):
    return ' '.join(''.join(c if c.isalnum() else ' ' for c in unicodedata.normalize('NFKC', name).casefold()).split())

def resolve(session, name, country=None):
    entities = session.scalars(select(Entity).where(Entity.kind == 'facility')).all()
    if country: entities = [e for e in entities if e.country == country]
    key = canonical(name)
    exact = [e for e in entities if key in [canonical(e.name), *map(canonical, e.aliases)]]
    if len(exact) == 1: return {'status':'resolved', 'entity_id':exact[0].id, 'candidates':[record(exact[0])]}
    if exact: return {'status':'ambiguous', 'entity_id':None, 'candidates':[record(e) for e in exact]}
    ranked = sorted([(min(muniquant_core.name_distance(key, canonical(n)) for n in [e.name, *e.aliases]), e) for e in entities], key=lambda x:(x[0], x[1].id))
    return {'status':'unresolved', 'entity_id':None, 'candidates':[record(e) for d,e in ranked[:5] if d <= max(3,len(key)//3)]}

def acquire(session, storage, data):
    source = session.get(Source, data.source_id)
    if not source: raise ValueError('Unknown source')
    if source.access_status not in ('permitted','synthetic'): raise ValueError('Source access must be permitted before acquisition')
    raw = data.content.encode('utf-8')
    digest = hashlib.sha256(raw).hexdigest()
    existing = session.scalar(select(Document).where(Document.source_id==data.source_id, Document.original_url==data.original_url, Document.content_hash==digest))
    path = Path(storage) / digest
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != digest: raise ValueError('Snapshot integrity failure')
    if not path.exists():
        # Atomic create: identical concurrent writers cannot truncate a stored snapshot.
        try:
            with path.open('xb') as f: f.write(raw)
        except FileExistsError: pass
    if existing:
        session.add(Run(status='duplicate', manifest={'content_hash':digest,'document_id':existing.id,'adapter':'text-upload-v1'}))
        return existing, True
    version = (session.scalar(select(func.max(Document.version)).where(Document.source_id==data.source_id, Document.original_url==data.original_url)) or 0)+1
    payload = data.model_dump(mode='json', exclude={'content'})
    doc = Document(**payload, content_hash=digest, version=version)
    session.add(doc); session.flush()
    session.add(Run(status='success', manifest={'content_hash':digest,'document_id':doc.id,'adapter':'text-upload-v1'}))
    return doc, False

def add_observation(session, data):
    entity = session.get(Entity, data.entity_id)
    doc = session.get(Document, data.document_id)
    if not entity or entity.kind != 'facility': raise ValueError('Unknown facility')
    if not doc: raise ValueError('Unknown evidence document')
    messages=[]
    normalized=None; unit=None
    if data.attribute == 'capacity':
        normalized=normalize_capacity(data.reported_value, data.reported_unit)
        unit='t/year'
        prior=session.scalars(select(Observation).where(Observation.entity_id==entity.id, Observation.attribute=='capacity')).all()
        if any(p.normalized_value and abs(normalized-p.normalized_value)/p.normalized_value > .5 for p in prior):
            messages.append('Capacity differs by more than 50% from an existing observation; review required')
    else:
        if data.reported_unit != 'status' or data.reported_value not in ('operating','closed','suspended','planned','construction'):
            raise ValueError('Status must use unit status and a supported operational state')
    if not doc.published_at: messages.append('Publication date missing')
    obs=Observation(**data.model_dump(mode='json'), normalized_value=normalized, normalized_unit=unit,
                    quality_status='WARN' if messages else 'PASS', quality_messages=messages)
    session.add(obs); session.flush()
    return obs

def export_package(session, storage):
    docs = {d.id:record(d) for d in session.scalars(select(Document)).all()}
    for doc in docs.values():
        path=Path(storage)/doc['content_hash']
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=doc['content_hash']:
            raise ValueError('Evidence snapshot missing or corrupted: '+doc['id'])
        doc['evidence_url']='/api/documents/'+doc['id']+'/content'
    package={'package_version':'0.1.0-draft','pipeline_version':PIPELINE_VERSION,
             'entities': [record(e) for e in session.scalars(select(Entity).order_by(Entity.id))],
             'sources': [record(s) for s in session.scalars(select(Source).order_by(Source.id))],
             'documents':sorted(docs.values(),key=lambda d:d['id']),
             'observations': [dict(record(o),resolution_status='resolved') for o in session.scalars(select(Observation).order_by(Observation.id))],
             'relationships':[record(r) for r in session.scalars(select(Relationship).order_by(Relationship.id))],
             'market_observations':[]}
    logical=json.dumps(package, sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    package['build_hash']=hashlib.sha256(logical).hexdigest()
    return package
