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

def normalize_value(value, unit, attribute='capacity'):
    from decimal import localcontext
    allowed = {'capacity': {'t/year':Decimal(1), 'kt/year':Decimal(1000), 'Mt/year':Decimal(1000000)},
               'power': {'MW':Decimal(1)}, 'ownership_percentage': {'percentage':Decimal(1)}}
    factors=allowed.get(attribute,{})
    if unit not in factors: raise ValueError('Unsupported unit for attribute dimension')
    text=str(value)
    if ',' in text:
        import re
        if not re.fullmatch(r'[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?',text):
            raise ValueError('Invalid thousands grouping')
        text=text.replace(',','')
    try: amount=Decimal(text)
    except InvalidOperation as exc: raise ValueError('Value must be numeric') from exc
    if not amount.is_finite() or amount<0: raise ValueError('Value must be finite and nonnegative')
    with localcontext() as context:
        context.prec=60
        result=amount*factors[unit]
        if result>=Decimal('1e24') or result!=result.quantize(Decimal('0.000001')):
            raise ValueError('Value exceeds exact numeric range/precision (24 integer, 6 fractional digits)')
    if attribute=='ownership_percentage' and result>100: raise ValueError('Percentage exceeds 100')
    return result, {'capacity':'t/year','power':'MW','ownership_percentage':'percentage'}[attribute]

def normalize_capacity(value,unit):
    return float(normalize_value(value,unit)[0])

def record(obj):
    from datetime import date,datetime
    def encode(value):
        if isinstance(value,(date,datetime)): return value.isoformat()
        if isinstance(value,Decimal): return format(value,'f')
        return value
    return {c.name: encode(getattr(obj,c.name)) for c in obj.__table__.columns}

from .domain import canonical

def resolve(session,name,country=None,entity_kind='facility'):
    from .models import EntitySupersession,EntityAlias
    entities=session.scalars(select(Entity).where(Entity.kind==entity_kind)).all()
    if country: entities=[e for e in entities if e.country==country]
    links={link.old_entity_id:link.new_entity_id for link in session.scalars(select(EntitySupersession))}
    all_entities={e.id:e for e in session.scalars(select(Entity))}
    def current(e):
        seen=set()
        while e.id in links:
            if e.id in seen: raise ValueError('Supersession cycle')
            seen.add(e.id);e=all_entities[links[e.id]]
        return e
    key=canonical(name)
    exact={current(e).id:current(e) for e in entities if key in [canonical(e.name),*map(canonical,e.aliases)]}
    if len(exact)==1:
        e=next(iter(exact.values()));return {'status':'resolved','entity_id':e.id,'candidates':[record(e)]}
    if exact: return {'status':'ambiguous','entity_id':None,'candidates':[record(exact[k]) for k in sorted(exact)]}
    ranked=sorted([(min(muniquant_core.name_distance(key,canonical(n)) for n in [e.name,*e.aliases]),e) for e in entities if e.id not in links],key=lambda x:(x[0],x[1].id))
    return {'status':'unresolved','entity_id':None,'candidates':[record(e) for distance,e in ranked[:5] if distance<=max(3,len(key)//3)]}

def acquire(session,storage,data):
    from .acquisition import register_bytes
    obj,duplicate=register_bytes(session,storage,data.model_dump(mode='json',exclude={'content'}),data.content.encode('utf-8'))
    session.add(Run(status='duplicate' if duplicate else 'success',pipeline_version='1.0.0',manifest={'content_hash':obj.content_hash,'document_id':obj.id,'adapter':'text-upload-v1'}))
    return obj,duplicate

def add_observation(session, data):
    entity = session.get(Entity, data.entity_id)
    doc = session.get(Document, data.document_id)
    if not entity or entity.kind != 'facility': raise ValueError('Unknown facility')
    if not doc: raise ValueError('Unknown evidence document')
    messages=[]
    normalized=None; unit=None
    if data.attribute != 'status':
        exact,unit=normalize_value(data.reported_value,data.reported_unit,data.attribute)
        normalized=float(exact)
        prior=session.scalars(select(Observation).where(Observation.entity_id==entity.id, Observation.attribute==data.attribute)).all()
        if any(p.normalized_value and abs(normalized-p.normalized_value)/p.normalized_value > .5 for p in prior):
            messages.append('Value differs by more than 50% from an existing observation; review required')
    else:
        if data.reported_unit != 'status' or data.reported_value not in ('operating','closed','suspended','planned','construction'):
            raise ValueError('Status must use unit status and a supported operational state')
    if not doc.published_at: messages.append('Publication date missing')
    obs=Observation(**data.model_dump(mode='json'), normalized_value=normalized, normalized_unit=unit,
                    quality_status='WARN' if messages else 'PASS', quality_messages=messages)
    session.add(obs); session.flush()
    from .models import ObservationDetail
    session.add(ObservationDetail(observation_id=obs.id,normalized_value=exact if data.attribute!='status' else None,normalized_unit=unit,valid_from=data.valid_from,valid_to=data.valid_to))
    session.flush()
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
