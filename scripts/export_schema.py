"""Generate the draft structural schema; review changes before a contract release."""
import json
from pathlib import Path
from sqlalchemy import Integer, Float, JSON
from app.models import Entity, Source, Document, Observation, Relationship, MarketObservation
models={'entities':Entity,'sources':Source,'documents':Document,'observations':Observation,'relationships':Relationship,'market_observations':MarketObservation}
schema={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'https://example.org/muniquant/commodity-evidence-package-0.1.schema.json','title':'Commodity Evidence Package 0.1 draft','type':'object','additionalProperties':False,'properties':{'package_version':{'const':'0.1.0-draft'},'pipeline_version':{'const':'0.1.0'},'build_hash':{'type':'string','pattern':'^[a-f0-9]{64}$'}}}
for key,model in models.items():
    props={}
    for c in model.__table__.columns:
        typ='integer' if isinstance(c.type,Integer) else 'number' if isinstance(c.type,Float) else 'array' if isinstance(c.type,JSON) else 'string'
        props[c.name]={'type':[typ,'null'] if c.nullable else typ}
        if typ=='array': props[c.name]['items']={'type':'string'}
    if key=='documents':
        props['content_hash']['pattern']='^[a-f0-9]{64}$'
        props['evidence_url']={'type':'string'}
        props['version']['minimum']=1
    if key=='observations':
        props['resolution_status']={'const':'resolved'}
        props['quality_status']={'enum':['PASS','WARN']}
        props['attribute']={'enum':['capacity','status']}
    schema['properties'][key]={'type':'array','items':{'type':'object','additionalProperties':False,'properties':props,'required':list(props)}}
schema['required']=list(schema['properties'])
Path('app/package.schema.json').write_text(json.dumps(schema,indent=2)+'\n')
