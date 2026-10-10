"""Closed, upstream-only CommodityEvidencePackage v1 and frozen parser bundles."""
import json
import zipfile
from decimal import Decimal
from pathlib import Path
from sqlalchemy import select
from jsonschema import Draft202012Validator, FormatChecker
from .models import Entity, Source, Document, Observation, ObservationDetail, EvidenceBuild, Candidate, SourceAccess, Review, CompanyFacilityRelationship, Relationship, EntitySupersession, EntityEvidence
from .quality import inspect_quality
from .pipeline import logical_hash, parse, replay, PARSER_VERSION
from .schemas import ExtractionIn
from .services import record,normalize_value

VERSION='1.0.0'
SCHEMA=Path(__file__).parent/'evidence-v1.schema.json'
PROHIBITED={'impact_score','surprise_score','market_state','analogue_score','supply_pressure','price_prediction','procurement_signal','trading_signal','factor_weight','alpha'}

def decimal_text(value):
    if value is None: return None
    result=format(Decimal(value),'f')
    return result.rstrip('0').rstrip('.') if '.' in result else result

def validate_package(package):
    def visit(value):
        if isinstance(value,dict):
            if PROHIBITED.intersection(value): raise ValueError('Proprietary/downstream fields are prohibited')
            for child in value.values(): visit(child)
        elif isinstance(value,list):
            for child in value: visit(child)
    visit(package)
    Draft202012Validator(json.loads(SCHEMA.read_text()),format_checker=FormatChecker()).validate(package)
    def indexed(items,key):
        mapping={item[key]:item for item in items}
        if len(mapping)!=len(items): raise ValueError('Duplicate contract identity: '+key)
        return mapping
    entities=indexed(package['entities'],'external_entity_id')
    sources=indexed(package['sources'],'source_id')
    docs=indexed(package['documents'],'document_id')
    indexed(package['records'],'record_id')
    indexed(package['relationships'],'relationship_id')
    indexed(package['build_manifest'],'build_id')
    for doc in docs.values():
        if doc['source_id'] not in sources: raise ValueError('Document source is absent')
    for item in [*package['records'],*package['relationships']]:
        doc=docs.get(item['document_id'])
        if not doc or doc['content_hash']!=item['content_hash'] or doc['source_id']!=item['source_id']: raise ValueError('Export provenance join is invalid')
        if 'external_entity_id' in item:
            identity=entities.get(item['external_entity_id'])
            if not identity or identity['entity_type']!='facility': raise ValueError('Observation entity is absent or not a facility')
            for field in ('entity_type','canonical_name','aliases','facility_type','country','region','commodity'):
                if item[field]!=identity[field]: raise ValueError('Observation identity differs from entity registry')
            source=sources[item['source_id']]
            if item['publisher']!=source['publisher'] or item['source_url']!=doc['original_url'] or item['published_at']!=doc['published_at'] or item['retrieved_at']!=doc['retrieved_at'] or item['synthetic']!=(source['source_type']=='synthetic'):
                raise ValueError('Observation source metadata differs from registry')
            if item['attribute_type']!='status':
                value,unit=normalize_value(item['reported_value'],item['reported_unit'],item['attribute_type'])
                if item['normalized_value']!=decimal_text(value) or item['unit']!=unit: raise ValueError('Export normalization mismatch')
            elif item['reported_unit']!='status' or item['unit']!='status' or item['normalized_value'] is not None or item['reported_value'] not in ('operating','closed','suspended','planned','construction'):
                raise ValueError('Invalid exported operational status')
        if item['valid_to'] and item['valid_to']<item['valid_from']: raise ValueError('Invalid exported validity interval')
        if 'company_id' in item and (entities.get(item['company_id'],{}).get('entity_type')!='company' or entities.get(item['facility_id'],{}).get('entity_type')!='facility'):
            raise ValueError('Relationship identity types are invalid')
    for identity in entities.values():
        current=identity['external_entity_id'];seen=set()
        while current:
            if current in seen or current not in entities: raise ValueError('Invalid exported supersession chain')
            seen.add(current);current=entities[current]['superseded_by']
    for manifest in package['build_manifest']:
        doc=docs.get(manifest['document_id'])
        if not doc or doc['content_hash']!=manifest['content_hash']: raise ValueError('Build manifest input document is absent or inconsistent')
    for item in package['identity_evidence']:
        if item['external_entity_id'] not in entities or item['document_id'] not in docs: raise ValueError('Identity evidence is not traceable')
    content={k:v for k,v in package.items() if k!='build_hash'}
    if logical_hash(content)!=package['build_hash']: raise ValueError('Package logical hash mismatch')
    return package

def export_v1(s,storage):
    quality=inspect_quality(s,storage)
    if quality['status']=='FAIL': raise ValueError('Quality BLOCK/ERROR findings prevent export; inspect /api/quality')
    records=[]
    for obs in s.scalars(select(Observation).order_by(Observation.id)):
        entity=s.get(Entity,obs.entity_id);doc=s.get(Document,obs.document_id);source=s.get(Source,doc.source_id);detail=s.get(ObservationDetail,obs.id)
        codes=[finding['code'] for finding in quality['findings'] if finding['record_id'] in (obs.id,doc.id,entity.id) and finding['severity']=='WARN']
        records.append({'record_id':obs.id,'external_entity_id':entity.id,'entity_type':entity.kind,'canonical_name':entity.name,
                        'aliases':sorted(entity.aliases),'facility_type':entity.facility_type,'country':entity.country,'region':entity.region,
                        'commodity':entity.commodity,'attribute_type':obs.attribute,'reported_value':obs.reported_value,'reported_unit':obs.reported_unit,
                        'normalized_value':decimal_text(detail.normalized_value),'unit':detail.normalized_unit or obs.reported_unit,
                        'valid_from':detail.valid_from.isoformat(),'valid_to':detail.valid_to.isoformat() if detail.valid_to else None,
                        'published_at':doc.published_at,'retrieved_at':doc.retrieved_at,'source_id':source.id,'document_id':doc.id,'content_hash':doc.content_hash,
                        'evidence_reference':obs.evidence_reference,'source_url':doc.original_url,'publisher':source.publisher,
                        'resolution_status':'resolved','quality_status':'WARN' if codes else 'PASS','quality_codes':sorted(set(codes)),
                        'synthetic':source.source_type=='synthetic','parser_version':obs.parser_version,'pipeline_version':VERSION,'package_version':VERSION})
    identities=[]
    for entity in s.scalars(select(Entity).order_by(Entity.id)):
        link=s.get(EntitySupersession,entity.id)
        identities.append({'external_entity_id':entity.id,'entity_type':entity.kind,'canonical_name':entity.name,'aliases':sorted(entity.aliases),'facility_type':entity.facility_type,'country':entity.country,'region':entity.region,'commodity':entity.commodity,'superseded_by':link.new_entity_id if link else None})
    identity_evidence=[{'external_entity_id':link.entity_id,'document_id':link.document_id,'evidence_reference':link.evidence_reference,'reviewer':link.reviewer,'reason':link.reason} for link in s.scalars(select(EntityEvidence).order_by(EntityEvidence.entity_id,EntityEvidence.document_id))]
    relationships=[]
    for link in s.scalars(select(CompanyFacilityRelationship).order_by(CompanyFacilityRelationship.relationship_id)):
        doc=s.get(Document,link.document_id)
        relationships.append({'relationship_id':link.relationship_id,'company_id':link.company_id,'facility_id':link.facility_id,'role':link.role,'percentage':decimal_text(link.percentage),'valid_from':link.valid_from.isoformat(),'valid_to':link.valid_to.isoformat() if link.valid_to else None,'source_id':doc.source_id,'document_id':doc.id,'content_hash':doc.content_hash,'evidence_reference':link.evidence_reference})
    doc_ids=sorted({r['document_id'] for r in records}|{r['document_id'] for r in relationships}|{r['document_id'] for r in identity_evidence}|{b.document_id for b in s.scalars(select(EvidenceBuild))})
    source_ids=sorted({s.get(Document,identifier).source_id for identifier in doc_ids})
    sources=[]
    for identifier in source_ids:
        source=s.get(Source,identifier)
        sources.append({'source_id':source.id,'name':source.name,'publisher':source.publisher,'source_type':source.source_type,'url':source.url,'access_status':source.access_status,'access_notes':source.notes})
    docs=[]
    for identifier in doc_ids:
        doc=s.get(Document,identifier)
        docs.append({'document_id':doc.id,'source_id':doc.source_id,'title':doc.title,'original_url':doc.original_url,'media_type':doc.media_type,'version':doc.version,'published_at':doc.published_at,'retrieved_at':doc.retrieved_at,'content_hash':doc.content_hash,'storage_reference':doc.content_hash})
    manifest=[]
    for build in s.scalars(select(EvidenceBuild).order_by(EvidenceBuild.id)):
        replay(s,storage,build.id)
        manifest.append({'build_id':build.id,'document_id':build.document_id,'content_hash':build.content_hash,'parser_version':build.parser_version,'pipeline_version':build.pipeline_version,'output_hash':build.output_hash})
    package={'package_version':VERSION,'pipeline_version':VERSION,'records':records,'entities':identities,'identity_evidence':identity_evidence,'relationships':relationships,'sources':sources,'documents':docs,'build_manifest':manifest}
    package['build_hash']=logical_hash(package)
    return validate_package(package)

def freeze_v1(s,storage,target):
    package=export_v1(s,storage)
    builds=[record(build) for build in s.scalars(select(EvidenceBuild).order_by(EvidenceBuild.id))]
    # The frozen registry includes audit metadata only; private downstream identity is never needed.
    registry=[record(entity) for entity in s.scalars(select(Entity).order_by(Entity.id))]
    recipe={'package':package,'builds':builds,'entities':registry,'candidates':[record(c) for c in s.scalars(select(Candidate).order_by(Candidate.id))],'reviews':[record(r) for r in s.scalars(select(Review).order_by(Review.id))]}
    recipe['recipe_hash']=logical_hash(recipe)
    hashes={doc['content_hash'] for doc in package['documents']}|{build['content_hash'] for build in builds}
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('recipe.json',json.dumps(recipe,sort_keys=True,indent=2))
        for digest in sorted(hashes): archive.write(Path(storage)/digest,'snapshots/'+digest)
    return package['build_hash']

def replay_v1(target):
    with zipfile.ZipFile(target) as archive:
        if len({item.filename for item in archive.infolist()})!=len(archive.infolist()): raise ValueError('Duplicate archive entry')
        if sum(item.file_size for item in archive.infolist())>100_000_000: raise ValueError('Bundle exceeds 100 MB limit')
        recipe=json.loads(archive.read('recipe.json'))
        if logical_hash({k:v for k,v in recipe.items() if k!='recipe_hash'})!=recipe['recipe_hash']: raise ValueError('Recipe integrity failure')
        package=validate_package(recipe['package'])
        docs={doc['document_id']:doc for doc in package['documents']}
        parsed=0
        candidates={c['id']:c for c in recipe['candidates']}
        reviews={r['id']:r for r in recipe['reviews']}
        entities={e['id']:e for e in recipe['entities']}
        if len(candidates)!=len(recipe['candidates']) or len(reviews)!=len(recipe['reviews']) or len(entities)!=len(recipe['entities']): raise ValueError('Duplicate frozen registry identity')
        if set(entities)!={identity['external_entity_id'] for identity in package['entities']}: raise ValueError('Frozen registry entity set differs')
        for identity in package['entities']:
            source=entities[identity['external_entity_id']]
            expected={'entity_type':source['kind'],'canonical_name':source['name'],'aliases':sorted(source['aliases']),'facility_type':source['facility_type'],'country':source['country'],'region':source['region'],'commodity':source['commodity']}
            if any(identity[field]!=value for field,value in expected.items()): raise ValueError('Frozen registry identity metadata differs')
        manifests={manifest['build_id']:manifest for manifest in package['build_manifest']}
        if set(manifests)!={build['id'] for build in recipe['builds']} or len(recipe['builds'])!=len(manifests): raise ValueError('Frozen build manifest set differs')
        frozen_records={r['record_id']:r for r in package['records']}
        checked_records=set()
        for build in recipe['builds']:
            if build['parser_version']!=PARSER_VERSION or build['pipeline_version']!=VERSION: raise ValueError('Unsupported frozen parser/pipeline version')
            manifest=manifests[build['id']]
            if any(manifest[field]!=build[field] for field in ('document_id','content_hash','parser_version','pipeline_version','output_hash')): raise ValueError('Frozen build manifest differs')
            expected_id=logical_hash({field:build[field] for field in ('document_id','content_hash','parser_version','pipeline_version')}|{'specification':build['specification']})
            if build['id']!=expected_id: raise ValueError('Frozen build identity differs')
            spec=ExtractionIn.model_validate(build['specification']).model_dump(mode='json')
            raw=archive.read('snapshots/'+build['content_hash'])
            if hashlib_hash(raw)!=build['content_hash']: raise ValueError('Frozen snapshot integrity failure')
            # Builds without accepted records still preserve media in recipe below.
            media=docs.get(build['document_id'],{}).get('media_type') or {'csv-v1':'text/csv','html-v1':'text/html','pdf-v1':'application/pdf'}[spec['adapter']]
            rows=parse(raw,media,spec)
            if rows!=build['logical_output'] or logical_hash(rows)!=build['output_hash']: raise ValueError('Frozen extraction differs')
            parsed+=len(rows)
            # Recompute normalized values and dates from parser output rather than copying stored values.
            from uuid import uuid5,NAMESPACE_URL
            for index,row in enumerate(rows):
                key=str(uuid5(NAMESPACE_URL,f"muniquant:{build['id']}:{index}"))
                candidate=candidates.get(key)
                if not candidate or candidate['raw_name']!=row['facility_name'] or candidate['reported_value']!=row['reported_value'] or candidate['evidence_reference']!=row['evidence_reference']:
                    raise ValueError('Frozen candidate differs from parser output')
                if candidate['status']=='rejected': continue
                if candidate['status']!='resolved': raise ValueError('Frozen candidate remains unresolved')
                exported=frozen_records.get(candidate['observation_id'])
                if not exported or exported['external_entity_id']!=candidate['entity_id'] or candidate['entity_id'] not in entities:
                    raise ValueError('Frozen resolved identity/observation is absent')
                if candidate['review_id']:
                    decision=reviews.get(candidate['review_id'])
                    if not decision or decision['status']!='accepted' or decision['selected_entity_id']!=candidate['entity_id'] or not decision['reviewer'] or not decision['reason']:
                        raise ValueError('Frozen manual identity has no reconstructable decision')
                value,unit=normalize_value(row['reported_value'],row['unit'],row['attribute']) if row['attribute']!='status' else (None,'status')
                if exported['document_id']!=build['document_id'] or exported['evidence_reference']!=row['evidence_reference'] or exported['attribute_type']!=row['attribute'] or exported['reported_value']!=row['reported_value'] or exported['normalized_value']!=decimal_text(value) or exported['unit']!=unit or exported['valid_from']!=row['valid_from'] or exported['valid_to']!=row['valid_to']:
                    raise ValueError('Export differs from re-extracted industrial fact')
                checked_records.add(exported['record_id'])
        # Manual facts have no parser recipe: verify normalization, and report them explicitly.
        manual_records=0
        for exported in package['records']:
            if exported['record_id'] not in checked_records:
                if exported['parser_version']==PARSER_VERSION: raise ValueError('Parser-produced record is missing its frozen build')
                manual_records+=1
                if exported['attribute_type']!='status':
                    value,unit=normalize_value(exported['reported_value'],exported['reported_unit'],exported['attribute_type'])
                    if exported['normalized_value']!=decimal_text(value) or exported['unit']!=unit: raise ValueError('Manual fact normalization mismatch')
        for doc in package['documents']:
            if hashlib_hash(archive.read('snapshots/'+doc['content_hash']))!=doc['content_hash']: raise ValueError('Snapshot integrity failure')
        return {'equivalent':True,'build_hash':package['build_hash'],'replayed_candidates':parsed,'builds':len(recipe['builds']),'records':len(package['records']),'manual_records_verified_only':manual_records}

def hashlib_hash(raw):
    import hashlib
    return hashlib.sha256(raw).hexdigest()
