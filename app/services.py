import hashlib
import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select, func
import muniquant_core
from .models import (
    Entity, Source, Document, Observation, Review, Run, MarketObservation, Relationship, Audit,
    RetrievalAttempt,
)
from .units import normalize as normalize_unit

PIPELINE_VERSION = '0.1.0'

def record(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

def canonical(name):
    folded=''.join(c for c in unicodedata.normalize('NFKD',name) if not unicodedata.combining(c)).casefold()
    tokens=''.join(c if c.isalnum() else ' ' for c in folded.replace('&',' and ')).split()
    suffixes={'plc','ltd','limited','inc','corp','corporation','co','company','llc','gmbh','ag','sa','nv','bv','pty','pte','as'}
    while len(tokens)>1 and tokens[-1] in suffixes: tokens.pop()
    return ' '.join(tokens)

def resolve(session, name, country=None):
    entities = session.scalars(select(Entity).where(Entity.kind == 'facility')).all()
    key = canonical(name)
    canonical_hits=[e for e in entities if canonical(e.name)==key]
    alias_hits=[e for e in entities if key in [canonical(alias) for alias in e.aliases]]
    hits=canonical_hits or alias_hits
    method='NORMALIZED' if canonical_hits else 'ALIAS'
    if country:
        local=[e for e in hits if e.country==country]
        if local: hits=local
    matches=[{'entity_id':e.id,'method':method,'score':1.0,'matched_text':e.name} for e in hits]
    if len(hits)==1:
        return {'status':'resolved','entity_id':hits[0].id,'match_method':method,'candidates':[record(hits[0])],'matches':matches}
    if hits:
        return {'status':'ambiguous','entity_id':None,'match_method':method,'candidates':[record(e) for e in hits],'matches':matches}
    ranked=[]
    for entity in entities:
        choices=[entity.name,*entity.aliases]
        best=min((muniquant_core.name_distance(key,canonical(value)),value) for value in choices)
        denominator=max(1,len(key),len(canonical(best[1])))
        score=max(0.0,1-(best[0]/denominator))
        if country and entity.country and entity.country!=country: score=max(0.0,score-.05)
        ranked.append((score,entity,best[1]))
    ranked.sort(key=lambda item:(-item[0],item[1].id))
    selected=[item for item in ranked[:5] if item[0]>=.67]
    candidates=[record(entity) for _,entity,_ in selected]
    matches=[{'entity_id':entity.id,'method':'FUZZY','score':round(score,4),'matched_text':matched} for score,entity,matched in selected]
    return {'status':'unresolved','entity_id':None,'match_method':'FUZZY' if selected else 'NONE','candidates':candidates,'matches':matches}

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
    finished=datetime.now(timezone.utc).isoformat()
    if existing:
        run=Run(status='duplicate',finished_at=finished,manifest={'content_hash':digest,'document_id':existing.id,'adapter':'text-upload-v1','adapter_version':'1.0.0'})
        session.add(run);session.flush()
        session.add(RetrievalAttempt(run_id=run.id,source_id=source.id,document_id=existing.id,
                    requested_url=data.original_url,http_status=200,outcome='UNCHANGED'))
        return existing, True
    version = (session.scalar(select(func.max(Document.version)).where(Document.source_id==data.source_id, Document.original_url==data.original_url)) or 0)+1
    payload = data.model_dump(mode='json', exclude={'content'})
    doc = Document(**payload, content_hash=digest, version=version)
    session.add(doc); session.flush()
    run=Run(status='success',finished_at=finished,manifest={'content_hash':digest,'document_id':doc.id,'adapter':'text-upload-v1','adapter_version':'1.0.0'})
    session.add(run);session.flush()
    session.add(RetrievalAttempt(run_id=run.id,source_id=source.id,document_id=doc.id,
                requested_url=data.original_url,http_status=200,outcome='SUCCESS'))
    return doc, False

def add_observation(session, data):
    entity = session.get(Entity, data.entity_id)
    doc = session.get(Document, data.document_id)
    if not entity or entity.kind != 'facility': raise ValueError('Unknown facility')
    if not doc: raise ValueError('Unknown evidence document')
    messages=[]
    normalized=None; unit=None
    if data.attribute == 'capacity':
        normalized_decimal,unit,_=normalize_unit(data.reported_value,data.reported_unit,expected_dimension='MASS_RATE')
        normalized=float(normalized_decimal)
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
    def compatibility(obj, fields):
        data=record(obj)
        return {field:data[field] for field in fields}
    entity_fields=('id','name','kind','facility_type','country','region','commodity','aliases')
    source_fields=('id','name','publisher','source_type','url','access_status','notes')
    observation_fields=('id','entity_id','document_id','attribute','reported_value','reported_unit','normalized_value',
                        'normalized_unit','valid_from','valid_to','evidence_reference','quality_status','quality_messages',
                        'parser_version','recorded_at')
    relationship_fields=('id','company_id','facility_id','role','percentage','valid_from','valid_to','document_id')
    market_fields=('id','instrument','exchange','market','contract_code','prompt_date','commodity','grade','region',
                   'price_type','value','currency','unit','effective_at','published_at','volume','open_interest',
                   'data_status','document_id','evidence_reference')
    package={'package_version':'0.1.0-draft','pipeline_version':PIPELINE_VERSION,
             'entities': [compatibility(e,entity_fields) for e in session.scalars(select(Entity).order_by(Entity.id))],
             'sources': [compatibility(s,source_fields) for s in session.scalars(select(Source).order_by(Source.id))],
             'documents':sorted(docs.values(),key=lambda d:d['id']),
             'observations': [dict(compatibility(o,observation_fields),resolution_status='resolved') for o in session.scalars(select(Observation).order_by(Observation.id)) if not o.superseded_by_id],
             'relationships':[compatibility(r,relationship_fields) for r in session.scalars(select(Relationship).order_by(Relationship.id)) if not r.superseded_by_id],
             'market_observations':[compatibility(m,market_fields) for m in session.scalars(select(MarketObservation).order_by(MarketObservation.id)) if not m.superseded_by_id]}
    logical=json.dumps(package, sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    package['build_hash']=hashlib.sha256(logical).hexdigest()
    return package
