"""Explicit upstream v1 contract. Increment version before breaking this mapping."""
import json
from pathlib import Path

def obj(properties): return {'type':'object','additionalProperties':False,'properties':properties,'required':list(properties)}
def string(**kw): return {'type':'string',**kw}
def nullable(**kw): return {'type':['string','null'],**kw}
def array(items): return {'type':'array','items':items}
hash_value=string(pattern='^[a-f0-9]{64}$')
record=obj({
 'record_id':string(minLength=1),'external_entity_id':string(minLength=1),'entity_type':{'const':'facility'},
 'canonical_name':string(minLength=1),'aliases':array(string()),'facility_type':string(enum=['smelter','refinery','bauxite_mine']),
 'country':string(pattern='^[A-Z]{2}$'),'region':nullable(),'commodity':string(minLength=1),
 'attribute_type':string(enum=['capacity','status','power','ownership_percentage']),
 'reported_value':string(minLength=1),'reported_unit':string(minLength=1),
 'normalized_value':nullable(pattern=r'^[0-9]+(?:\.[0-9]+)?$'),'unit':string(enum=['t/year','MW','percentage','status']),
 'valid_from':string(format='date'),'valid_to':nullable(format='date'),
 'published_at':nullable(format='date'),'retrieved_at':string(format='date-time'),
 'source_id':string(minLength=1),'document_id':string(minLength=1),'content_hash':hash_value,
 'evidence_reference':string(minLength=1),'source_url':string(format='uri'),'publisher':string(minLength=1),
 'resolution_status':{'const':'resolved'},'quality_status':string(enum=['PASS','WARN']),'quality_codes':array(string()),
 'synthetic':{'type':'boolean'},'parser_version':string(minLength=1),'pipeline_version':{'const':'1.0.0'},'package_version':{'const':'1.0.0'}
})
source=obj({'source_id':string(),'name':string(minLength=1),'publisher':string(minLength=1),'source_type':string(),
 'url':string(format='uri'),'access_status':string(enum=['permitted','synthetic']),'access_notes':string()})
document=obj({'document_id':string(),'source_id':string(),'title':string(minLength=1),'original_url':string(format='uri'),
 'media_type':string(enum=['text/plain','text/html','text/csv','application/pdf','application/json']),
 'version':{'type':'integer','minimum':1},'published_at':nullable(format='date'),'retrieved_at':string(format='date-time'),
 'content_hash':hash_value,'storage_reference':hash_value})
manifest=obj({'build_id':hash_value,'document_id':string(),'content_hash':hash_value,'parser_version':string(),
 'pipeline_version':{'const':'1.0.0'},'output_hash':hash_value})
entity=obj({'external_entity_id':string(),'entity_type':string(enum=['company','facility']),'canonical_name':string(minLength=1),'aliases':array(string()),'facility_type':nullable(enum=['smelter','refinery','bauxite_mine',None]),'country':string(pattern='^[A-Z]{2}$'),'region':nullable(),'commodity':string(),'superseded_by':nullable()})
identity_evidence=obj({'external_entity_id':string(),'document_id':string(),'evidence_reference':string(minLength=3),'reviewer':string(minLength=1),'reason':string(minLength=10)})
relationship=obj({'relationship_id':string(),'company_id':string(),'facility_id':string(),'role':string(enum=['OWNS','OPERATES']),'percentage':nullable(pattern=r'^[0-9]+(?:\.[0-9]+)?$'),'valid_from':string(format='date'),'valid_to':nullable(format='date'),'source_id':string(),'document_id':string(),'content_hash':hash_value,'evidence_reference':string(minLength=3)})
schema=obj({'package_version' :{'const':'1.0.0'},'pipeline_version':{'const':'1.0.0'},'records':array(record),'entities':array(entity),'identity_evidence':array(identity_evidence),'relationships':array(relationship),
 'sources':array(source),'documents':array(document),'build_manifest':array(manifest),'build_hash':hash_value})
schema.update({'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'https://github.com/youcefjerbi/MuniQuant-Aluminium-Trading-Plattform/blob/main/app/evidence-v1.schema.json','title':'CommodityEvidencePackage v1 — upstream industrial evidence'})
Path('app/evidence-v1.schema.json').write_text(json.dumps(schema,indent=2)+'\n')
