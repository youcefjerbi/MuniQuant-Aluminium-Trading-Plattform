"""Machine-readable upstream findings; blocking corruption cannot cross the export boundary."""
from collections import Counter
from datetime import date
from pathlib import Path
import hashlib
import re
from sqlalchemy import select
from .models import Entity, Source, Document, Observation, ObservationDetail, Candidate, EvidenceBuild, SourceAccess, DocumentVersion, SourceSnapshot, EntityEvidence, CompanyFacilityRelationship, Relationship
from .services import normalize_value

def inspect_quality(s,storage):
    findings=[]
    def add(code,severity,kind,identifier,message):
        findings.append({'code':code,'severity':severity,'record_type':kind,'record_id':identifier,'message':message,
                         'remediation':{'BLOCK':'Correct source data or resolve/reject candidate before export','ERROR':'Correct the invalid record','WARN':'Review source evidence and document the decision','INFO':'No action unless provenance is incorrect'}[severity]})
    entities={e.id:e for e in s.scalars(select(Entity))}
    sources={o.id:o for o in s.scalars(select(Source))}
    documents={o.id:o for o in s.scalars(select(Document))}
    counts=Counter(d.content_hash for d in documents.values())
    latest={}
    for policy in s.scalars(select(SourceAccess).order_by(SourceAccess.decided_at,SourceAccess.id)): latest[policy.source_id]=policy
    lead_docs={d.id for d in documents.values() if latest.get(d.source_id) is not None and latest[d.source_id].usage_scope=='leads_only'}
    def cites_lead(kind,identifier,document_id):
        if document_id in lead_docs:
            add('LEAD_SOURCE_CITED','BLOCK',kind,identifier,'Lead-only licensed feed is cited as evidence; cite the primary source instead')
    for entity in entities.values():
        if not s.scalar(select(EntityEvidence).where(EntityEvidence.entity_id==entity.id)):
            add('MISSING_ASSET_EVIDENCE','WARN','entity',entity.id,'Curated identity has no explicit source locator')
    for doc in documents.values():
        def add_doc(code,severity,message,doc=doc):
            # Lead-only documents never enter the package, so their integrity findings cannot block export.
            if doc.id in lead_docs and severity=='BLOCK': severity,message='INFO',message+' (lead-only document; excluded from export)'
            add(code,severity,'document',doc.id,message)
        source=sources.get(doc.source_id)
        if not source or not source.publisher or not source.url or not source.name:
            add_doc('MISSING_SOURCE_METADATA','BLOCK','Source metadata is incomplete')
        if source and source.access_status not in ('permitted','synthetic'):
            add_doc('ACCESS_NOT_PERMITTED','BLOCK','Source access is not permitted')
        policy=s.scalar(select(SourceAccess).where(SourceAccess.source_id==doc.source_id).order_by(SourceAccess.decided_at.desc(),SourceAccess.id.desc()))
        if policy and policy.status!='permitted': add_doc('ACCESS_REVOKED','BLOCK','Latest audited source-access decision blocks export')
        if not policy and source and source.source_type!='synthetic': add_doc('MISSING_ACCESS_AUDIT','WARN','Source has no audited access decision')
        # Lead-feed snapshots are curator work items, not evidence, so an unknown publication date is expected.
        if not doc.published_at and doc.id not in lead_docs: add_doc('MISSING_PUBLICATION_DATE','WARN','Source publication date is unknown')
        try:
            if doc.published_at and date.fromisoformat(doc.published_at)>date.fromisoformat(doc.retrieved_at[:10]):
                add_doc('PUBLICATION_AFTER_RETRIEVAL','BLOCK','Publication is after retrieval date')
        except ValueError: add_doc('INVALID_DOCUMENT_DATE','BLOCK','Invalid source date')
        if not re.fullmatch(r'[a-f0-9]{64}',doc.content_hash):
            add_doc('INVALID_CONTENT_HASH','BLOCK','Malformed content hash')
            continue
        path=Path(storage)/doc.content_hash
        if not path.is_file(): add_doc('MISSING_SNAPSHOT','BLOCK','Raw snapshot is missing')
        elif path.stat().st_size>10_000_000 or hashlib.sha256(path.read_bytes()).hexdigest()!=doc.content_hash:
            add_doc('CORRUPT_SNAPSHOT','BLOCK','Raw snapshot does not match its content hash')
        if not s.get(DocumentVersion,doc.id) or not s.get(SourceSnapshot,doc.content_hash):
            add_doc('MISSING_VERSION_METADATA','BLOCK','Version/snapshot registry linkage is absent')
        if counts[doc.content_hash]>1: add_doc('DUPLICATE_CONTENT','INFO','Identical bytes occur under distinct provenance')
    seen=set()
    historical={}
    for obs in s.scalars(select(Observation).order_by(Observation.id)):
        entity=entities.get(obs.entity_id)
        if not entity or entity.kind!='facility': add('UNRESOLVED_ENTITY','BLOCK','observation',obs.id,'Observation has no valid facility identity')
        if obs.document_id not in documents or not obs.evidence_reference:
            add('MISSING_PROVENANCE','BLOCK','observation',obs.id,'Exact document and evidence locator are required')
        cites_lead('observation',obs.id,obs.document_id)
        detail=s.get(ObservationDetail,obs.id)
        if not detail: add('MISSING_EXACT_OBSERVATION','BLOCK','observation',obs.id,'Exact numeric/native date representation is absent')
        try:
            start=date.fromisoformat(obs.valid_from);end=date.fromisoformat(obs.valid_to) if obs.valid_to else None
            if end and end<start: raise ValueError('Invalid validity interval')
            if detail and (detail.valid_from!=start or detail.valid_to!=end): raise ValueError('Native date differs from source observation')
            if obs.attribute!='status':
                value,unit=normalize_value(obs.reported_value,obs.reported_unit,obs.attribute)
                if not detail or detail.normalized_value!=value or detail.normalized_unit!=unit: raise ValueError('Exact normalized value/unit differs from reported value')
            elif obs.reported_unit!='status' or obs.reported_value not in ('operating','closed','suspended','planned','construction'):
                raise ValueError('Invalid status dimension')
        except ValueError as exc: add('INVALID_ATTRIBUTE','BLOCK','observation',obs.id,str(exc))
        key=(obs.entity_id,obs.document_id,obs.attribute,obs.reported_value,obs.reported_unit,obs.valid_from,obs.valid_to)
        if key in seen: add('DUPLICATE_OBSERVATION','WARN','observation',obs.id,'Repeated sourced fact')
        seen.add(key)
        for previous,previous_detail in historical.get((obs.entity_id,obs.attribute),[]):
            if obs.valid_from <= (previous.valid_to or '9999-12-31') and previous.valid_from <= (obs.valid_to or '9999-12-31'):
                current_value=detail.normalized_value if detail and obs.attribute!='status' else obs.reported_value
                old_value=previous_detail.normalized_value if previous_detail and obs.attribute!='status' else previous.reported_value
                if current_value!=old_value:
                    add('CONFLICTING_OBSERVATIONS','WARN','observation',obs.id,'Overlapping validity intervals carry conflicting facts; retain both and review source vintages')
        historical.setdefault((obs.entity_id,obs.attribute),[]).append((obs,detail))
        for message in obs.quality_messages:
            if '50%' in message: add('SUSPICIOUS_VALUE_CHANGE','WARN','observation',obs.id,message)
    ownership={}
    for link in s.scalars(select(Relationship)):
        exact=s.get(CompanyFacilityRelationship,link.id)
        company=entities.get(link.company_id);facility=entities.get(link.facility_id)
        if not exact or not company or company.kind!='company' or not facility or facility.kind!='facility' or link.document_id not in documents:
            add('INVALID_RELATIONSHIP','BLOCK','relationship',link.id,'Relationship requires company, facility, exact dates and source evidence')
        elif 'legacy' in exact.evidence_reference.lower():
            add('IMPRECISE_RELATIONSHIP_LOCATOR','WARN','relationship',link.id,'Legacy relationship needs a precise document locator')
        cites_lead('relationship',link.id,link.document_id)
        if exact and exact.role=='OWNS' and exact.percentage is not None:
            ownership.setdefault(exact.facility_id,[]).append(exact)
    for facility_id,shares in ownership.items():
        for point in sorted({link.valid_from for link in shares}):
            active=[link for link in shares if link.valid_from<=point and (not link.valid_to or link.valid_to>=point)]
            # Multiple source vintages for one company are evidence conflicts, not extra owners.
            by_company={}
            for link in active: by_company[link.company_id]=max(by_company.get(link.company_id,0),link.percentage)
            if sum(by_company.values())>100:
                add('OWNERSHIP_TOTAL_EXCEEDS_100','WARN','entity',facility_id,'Overlapping ownership evidence exceeds 100%; investigate dates and conflicting source vintages')
                break
    for link in s.scalars(select(EntityEvidence)): cites_lead('entity',link.entity_id,link.document_id)
    for build in s.scalars(select(EvidenceBuild)): cites_lead('build',build.id,build.document_id)
    for candidate in s.scalars(select(Candidate)):
        if candidate.status=='resolved' and (not candidate.entity_id or not candidate.observation_id):
            add('INCOMPLETE_RESOLVED_CANDIDATE','BLOCK','candidate',candidate.id,'Resolved candidate is missing its persisted observation')
        if candidate.status not in ('resolved','rejected'):
            add('UNRESOLVED_CANDIDATE','BLOCK','candidate',candidate.id,'Extracted name requires a manual identity decision')
    severities=Counter(f['severity'] for f in findings)
    status='FAIL' if severities['BLOCK'] or severities['ERROR'] else 'WARN' if severities['WARN'] else 'PASS'
    return {'status':status,'counts':dict(severities),'findings':findings,
            'coverage':{'facilities':sum(e.kind=='facility' for e in entities.values()),'companies':sum(e.kind=='company' for e in entities.values()),'sources':len(sources),'documents':len(documents)}}
