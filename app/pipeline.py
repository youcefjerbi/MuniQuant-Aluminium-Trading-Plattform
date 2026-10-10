"""Versioned configurable adapters and deterministic frozen-snapshot parser replay."""
import csv
import hashlib
import io
import json
import re
from html.parser import HTMLParser
from uuid import uuid5, NAMESPACE_URL
from pathlib import Path
from sqlalchemy import select
from .models import Document, EvidenceBuild, Candidate, Review, Run, Observation, Audit, ObservationDetail
from .schemas import ObservationIn
from .services import resolve, add_observation, record, normalize_value

PARSER_VERSION='industrial-adapters-1.0.0'
PIPELINE_VERSION='1.0.0'

def logical_hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'): self.hidden+=1
    def handle_endtag(self,tag):
        if tag in ('script','style'): self.hidden=max(0,self.hidden-1)
    def handle_data(self,text):
        if not self.hidden: self.parts.append(text)

def parse(raw,media,spec):
    adapter=spec['adapter']
    rows=[]
    if adapter=='csv-v1':
        if media!='text/csv': raise ValueError('CSV adapter requires text/csv snapshot')
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        required={'facility_name','country','reported_value','reported_unit','valid_from','evidence_reference'}
        if not required.issubset(reader.fieldnames or []): raise ValueError('Missing required CSV columns: '+', '.join(sorted(required)))
        for line,row in enumerate(reader,2):
            if len(rows)>=1000: raise ValueError('At most 1000 candidates per build')
            rows.append({'facility_name':row['facility_name'],'country':row['country'], 'reported_value':row['reported_value'],
                         'unit':row['reported_unit'],'valid_from':row['valid_from'],'valid_to':row.get('valid_to') or None,
                         'attribute':row.get('attribute') or spec['attribute'],'evidence_reference':f"CSV row {line}: {row['evidence_reference']}"})
    else:
        pages=[]
        if adapter=='html-v1':
            if media!='text/html': raise ValueError('HTML adapter requires text/html snapshot')
            parser=PlainHTML();parser.feed(raw.decode('utf-8'))
            pages=[('HTML text',' '.join(' '.join(parser.parts).split()))]
        elif adapter=='pdf-v1':
            if media!='application/pdf' or not raw.startswith(b'%PDF-'): raise ValueError('PDF adapter requires a valid PDF snapshot')
            from pypdf import PdfReader
            pdf=PdfReader(io.BytesIO(raw))
            if pdf.is_encrypted: raise ValueError('Encrypted PDFs are not supported')
            if len(pdf.pages)>200: raise ValueError('PDF page limit is 200')
            if spec.get('page') and spec['page']>len(pdf.pages): raise ValueError('Requested page does not exist')
            for number,page in enumerate(pdf.pages,1):
                if not spec.get('page') or spec['page']==number:
                    text=page.extract_text() or ''
                    if len(text)>2_000_000: raise ValueError('PDF extracted text is too large')
                    pages.append((f'PDF page {number}',' '.join(text.split())))
        else: raise ValueError('Unknown parser version/adapter')
        prefix=' '.join(spec['prefix'].split());suffix=' '.join(spec['suffix'].split())
        pattern=re.compile(re.escape(prefix)+r'\s*(?P<value>[0-9][0-9,]*(?:\.[0-9]+)?)\s*'+re.escape(suffix),re.IGNORECASE)
        for locator,text in pages:
            for match in pattern.finditer(text):
                if len(rows)>=1000: raise ValueError('At most 1000 candidates per build')
                rows.append({'facility_name':spec['facility_name'],'country':spec.get('country'), 'reported_value':match['value'],
                             'unit':spec['unit'],'valid_from':spec['valid_from'],'valid_to':spec.get('valid_to'),
                             'attribute':spec['attribute'],'evidence_reference':f'{locator}, text offset {match.start()}; context: {match[0][:500]}'})
    if not rows: raise ValueError('No values matched; revise literal extraction context or use manual observation')
    for row in rows:
        if not row['facility_name'] or len(row['facility_name'])>256: raise ValueError('Invalid facility name in candidate')
        # Validate dimensions/dates before any rows become persisted observations.
        if row['attribute']!='status': normalize_value(row['reported_value'],row['unit'],row['attribute'])
        elif row['unit']!='status' or row['reported_value'] not in ('operating','closed','suspended','planned','construction'):
            raise ValueError('Invalid sourced operational status')
        ObservationIn(entity_id='candidate',document_id='candidate',attribute=row['attribute'],reported_value=row['reported_value'],reported_unit=row['unit'],valid_from=row['valid_from'],valid_to=row['valid_to'],evidence_reference=row['evidence_reference'])
    return rows

def snapshot_bytes(storage,doc):
    path=Path(storage)/doc.content_hash
    if not path.is_file(): raise ValueError('Snapshot is missing')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=doc.content_hash: raise ValueError('Snapshot integrity failure')
    return raw

def extract(s,storage,document_id,data,actor):
    doc=s.get(Document,document_id)
    if not doc: raise ValueError('Unknown document')
    spec=data.model_dump(mode='json')
    build_id=logical_hash({'document_id':doc.id,'content_hash':doc.content_hash,'parser_version':PARSER_VERSION,'pipeline_version':PIPELINE_VERSION,'specification':spec})
    existing=s.get(EvidenceBuild,build_id)
    if existing:
        # Still verify source integrity and replay before acknowledging a duplicate.
        replay(s,storage,build_id)
        return existing,True
    try:
        rows=parse(snapshot_bytes(storage,doc),doc.media_type,spec)
    except (ValueError, UnicodeError) as exc:
        # Preserve failure observability without committing any partial candidate facts.
        s.rollback()
        s.add(Run(status='failed',pipeline_version=PIPELINE_VERSION,manifest={'adapter':data.adapter,'document_id':doc.id,'build_id':build_id,'content_hash':doc.content_hash,'parser_version':PARSER_VERSION,'actor':actor,'error':str(exc)[:500]}))
        s.commit()
        raise ValueError(str(exc)) from exc
    build=EvidenceBuild(id=build_id,document_id=doc.id,content_hash=doc.content_hash,parser_version=PARSER_VERSION,pipeline_version=PIPELINE_VERSION,specification=spec,logical_output=rows,output_hash=logical_hash(rows),actor=actor)
    s.add(build);s.flush()
    for index,row in enumerate(rows):
        identifier=str(uuid5(NAMESPACE_URL,f'muniquant:{build_id}:{index}'))
        match=resolve(s,row['facility_name'],row['country'])
        candidate=Candidate(id=identifier,build_id=build_id,raw_name=row['facility_name'],country=row['country'],reported_value=row['reported_value'],unit=row['unit'],evidence_reference=row['evidence_reference'],status=match['status'],entity_id=match['entity_id'])
        s.add(candidate)
        if match['status']=='resolved':
            obj=add_observation(s,ObservationIn(entity_id=match['entity_id'],document_id=doc.id,attribute=row['attribute'],reported_value=row['reported_value'],reported_unit=row['unit'],valid_from=row['valid_from'],valid_to=row['valid_to'],evidence_reference=row['evidence_reference']))
            obj.parser_version=PARSER_VERSION;candidate.observation_id=obj.id
            s.add(Audit(actor=actor,action='extract_observation',record_id=obj.id,detail={'build_id':build_id,'candidate_id':identifier}))
        else:
            review=Review(raw_name=row['facility_name'],candidate_ids=[e['id'] for e in match['candidates']]);s.add(review);s.flush()
            candidate.review_id=review.id
            candidate.findings=[{'code':'UNRESOLVED_ENTITY','severity':'BLOCK','message':'Human identity review required'}]
    s.add(Run(status='success',pipeline_version=PIPELINE_VERSION,manifest={'adapter':data.adapter,'document_id':doc.id,'build_id':build_id,'content_hash':doc.content_hash,'parser_version':PARSER_VERSION,'output_hash':build.output_hash}))
    s.flush();return build,False

def replay(s,storage,build_id):
    build=s.get(EvidenceBuild,build_id)
    if not build: raise ValueError('Unknown build')
    if build.parser_version!=PARSER_VERSION or build.pipeline_version!=PIPELINE_VERSION: raise ValueError('Unsupported frozen parser/pipeline version')
    doc=s.get(Document,build.document_id)
    if not doc or doc.content_hash!=build.content_hash: raise ValueError('Build provenance changed')
    rows=parse(snapshot_bytes(storage,doc),doc.media_type,build.specification)
    reproduced=logical_hash(rows)
    if reproduced!=build.output_hash or rows!=build.logical_output: raise ValueError('Frozen parser output is not reproducible')
    return {'build_id':build.id,'parser_version':build.parser_version,'input_hash':build.content_hash,'output_hash':reproduced,'equivalent':True,'candidate_count':len(rows)}

def apply_review(s,review,actor):
    for candidate in s.scalars(select(Candidate).where(Candidate.review_id==review.id)):
        if not review.selected_entity_id:
            candidate.status='rejected';continue
        build=s.get(EvidenceBuild,candidate.build_id)
        row=next(row for row in build.logical_output if row['evidence_reference']==candidate.evidence_reference)
        obj=add_observation(s,ObservationIn(entity_id=review.selected_entity_id,document_id=build.document_id,attribute=row['attribute'],reported_value=row['reported_value'],reported_unit=row['unit'],valid_from=row['valid_from'],valid_to=row['valid_to'],evidence_reference=row['evidence_reference']))
        obj.parser_version=build.parser_version
        candidate.status='resolved';candidate.entity_id=review.selected_entity_id;candidate.observation_id=obj.id;candidate.findings=[]
        from .domain import add_alias
        add_alias(s,review.selected_entity_id,candidate.raw_name,actor,review.reason)
        s.add(Audit(actor=actor,action='review_observation',record_id=obj.id,detail={'review_id':review.id,'candidate_id':candidate.id}))
