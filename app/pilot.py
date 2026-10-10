"""Small real, source-linked aluminium pilot. Explicit URLs, not a crawler.

No raw third-party documents are distributed with the repository. --online captures
public corporate materials for local research only; source decisions are audited.
Dates for undated snapshots describe observation-at-capture, not historical change dates.
"""
import argparse,json,os
from datetime import date
from pathlib import Path
from uuid import uuid5,NAMESPACE_URL
from urllib.parse import urlsplit
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import make_engine,DATABASE_URL
from .models import Entity,Source,SourceAccess,EntityEvidence,Document,Relationship,CompanyFacilityRelationship,Audit
from .domain import sync_entity
from .acquisition import acquire_remote
from .pipeline import extract,PlainHTML
from .schemas import RetrievalIn,ExtractionIn
from .contract import export_v1,freeze_v1,replay_v1
from decimal import Decimal

ACTOR='authorized-pilot-curator'
SOURCES={
 'alcoa':('Alcoa','https://www.alcoa.com/australia/en/'),
 'hydro':('Norsk Hydro','https://www.hydro.com/en/global/'),
 'rio':('Rio Tinto','https://www.riotinto.com/operations/')}
DOCUMENTS={
 'portland':('alcoa','https://www.alcoa.com/australia/en/pdf/smelting-portland-aluminum-smelter-fact-sheet.pdf',None),
 'husnes':('hydro','https://www.hydro.com/en/global/media/news/2024/hydro-invests-nok-200-million-at-husnes-aluminium-plant/','2024-12-19'),
 'norway':('hydro','https://www.hydro.com/en/global/about-hydro/hydro-worldwide/europe/norway/',None),
 'brazil':('hydro','https://www.hydro.com/en/global/sustainability/operating-in-the-brazilian-amazon/managing-our-operations/',None),
 'boyne':('rio','https://www.riotinto.com/operations/anz/gladstone/boyne-smelters-ltd',None),
 'aluminium':('rio','https://www.riotinto.com/en/products/aluminium',None),
 'weipa':('rio','https://www.riotinto.com/operations/anz/weipa',None)}
# identity, country, type, product, document key, source substring confirming identity
ASSETS=[
 ('Portland Aluminium','AU','smelter','aluminium','portland','PORTLAND ALUMINIUM'),
 ('Hydro Husnes','NO','smelter','aluminium','husnes','Hydro Husnes'),
 ('Hydro Sunndal','NO','smelter','aluminium','norway','Sunndal'),
 ('Hydro Karmøy','NO','smelter','aluminium','norway','Karmøy'),
 ('Hydro Årdal','NO','smelter','aluminium','norway','Årdal'),
 ('Hydro Høyanger','NO','smelter','aluminium','norway','Høyanger'),
 ('Albras','BR','smelter','aluminium','brazil','Albras'),
 ('Alunorte','BR','refinery','alumina','brazil','Alunorte'),
 ('Paragominas','BR','bauxite_mine','bauxite','brazil','Paragominas'),
 ('Boyne Smelters Limited','AU','smelter','aluminium','boyne','Boyne Smelters Limited'),
 ('Yarwun','AU','refinery','alumina','aluminium','Yarwun'),
 ('Queensland Alumina Limited','AU','refinery','alumina','aluminium','Queensland Alumina'),
 ('Bell Bay Aluminium','AU','smelter','aluminium','aluminium','Bell Bay'),
 ('Amrun','AU','bauxite_mine','bauxite','weipa','Amrun'),
 ('Andoom','AU','bauxite_mine','bauxite','weipa','Andoom')]

def identifier(label): return str(uuid5(NAMESPACE_URL,'muniquant-pilot:'+label))

def text_for(doc,storage):
    raw=(Path(storage)/doc.content_hash).read_bytes()
    if doc.media_type=='application/pdf':
        import io
        from pypdf import PdfReader
        return '\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(raw)).pages)
    parser=PlainHTML();parser.feed(raw.decode('utf-8'));return ' '.join(' '.join(parser.parts).split())

def populate(s,storage,output,as_of,online=False):
    if not online: raise ValueError('Use --online to explicitly approve these bounded public-source captures; use evidence_cli replay for offline rebuild')
    for key,(publisher,url) in SOURCES.items():
        sid=identifier('source:'+key)
        source=s.get(Source,sid)
        if not source:
            source=Source(id=sid,name=publisher+' public industrial publications',publisher=publisher,source_type='company',url=url,access_status='permitted',notes='Public corporate publication for local research. No third-party redistribution license asserted.');s.add(source);s.flush()
        policy=s.scalar(select(SourceAccess).where(SourceAccess.source_id==sid))
        if not policy:
            s.add(SourceAccess(source_id=sid,status='permitted',allowed_hosts=[urlsplit(url).hostname],basis='Curator-approved bounded capture of publicly published corporate industrial material for this research pilot',retention='Local evidence retention only; review publisher terms before redistribution or shared hosting',reviewer=ACTOR))
    s.commit()
    docs={}
    for key,(source_key,url,published) in DOCUMENTS.items():
        data=RetrievalIn(source_id=identifier('source:'+source_key),url=url,title=key+' official industrial evidence',published_at=published)
        doc,_,_=acquire_remote(s,storage,data,ACTOR);docs[key]=doc
    texts={key:text_for(doc,storage) for key,doc in docs.items()}
    assets={}
    for name,country,kind,commodity,doc_key,needle in ASSETS:
        if needle.casefold() not in texts[doc_key].casefold(): raise ValueError('Identity is no longer present in official source: '+name)
        eid=identifier('facility:'+name)
        entity=s.get(Entity,eid)
        if not entity:
            entity=Entity(id=eid,name=name,kind='facility',country=country,facility_type=kind,commodity=commodity,region='',aliases=[needle] if needle!=name else [])
            s.add(entity);s.flush();sync_entity(s,entity,ACTOR)
        key=(eid,docs[doc_key].id)
        if not s.get(EntityEvidence,key):
            s.add(EntityEvidence(entity_id=eid,document_id=docs[doc_key].id,evidence_reference=('PDF page 1: ' if doc_key=='portland' else 'Official operations text: ')+needle,reviewer=ACTOR,reason='Curated facility name, country and industrial class from official operations description; no market inference'))
        assets[name]=entity
    companies={}
    for name,country in [('Alcoa of Australia','AU'),('CITIC','CN'),('Marubeni Aluminium Australia','AU'),('Norsk Hydro','NO'),('Rio Tinto','GB')]:
        eid=identifier('company:'+name);company=s.get(Entity,eid)
        if not company:
            company=Entity(id=eid,name=name,kind='company',country=country,region='',commodity='aluminium',aliases=[]);s.add(company);s.flush();sync_entity(s,company,ACTOR)
        companies[name]=company
    s.commit()
    specs=[('portland',{'adapter':'pdf-v1','facility_name':'Portland Aluminium','country':'AU','valid_from':as_of,'unit':'t/year','prefix':'annual nameplate production capacity of','suffix':'metric tons','page':1}),
           ('husnes',{'adapter':'html-v1','facility_name':'Hydro Husnes','country':'NO','valid_from':'2024-12-19','unit':'t/year','prefix':'annual production capacity of','suffix':'tonnes of primary aluminium'})]
    for key,spec in specs: extract(s,storage,docs[key].id,ExtractionIn(**spec),ACTOR);s.commit()
    for company_name,role,percentage in [('Alcoa of Australia','OWNS','55'),('CITIC','OWNS','22.5'),('Marubeni Aluminium Australia','OWNS','22.5'),('Alcoa of Australia','OPERATES',None)]:
        rid=identifier('portland:'+company_name+':'+role)
        if not s.get(Relationship,rid):
            s.add(Relationship(id=rid,company_id=companies[company_name].id,facility_id=assets['Portland Aluminium'].id,role=role,percentage=float(percentage) if percentage else None,valid_from=as_of,document_id=docs['portland'].id));s.flush()
            s.add(CompanyFacilityRelationship(relationship_id=rid,company_id=companies[company_name].id,facility_id=assets['Portland Aluminium'].id,document_id=docs['portland'].id,role=role,percentage=Decimal(percentage) if percentage else None,valid_from=date.fromisoformat(as_of),evidence_reference='PDF page 1, Operations: joint venture percentages and day-to-day operation'))
            s.add(Audit(actor=ACTOR,action='curated_relationship',record_id=rid,detail={'source':'Portland page 1','as_of_policy':'snapshot observation date, not historical change date'}))
    s.commit()
    package=export_v1(s,storage)
    root=Path(output);root.mkdir(parents=True,exist_ok=True)
    (root/'pilot-evidence-package.json').write_text(json.dumps(package,indent=2))
    bundle=root/'pilot-frozen-evidence.zip'
    if bundle.exists(): raise ValueError('Output bundle already exists; choose a new output directory')
    freeze_v1(s,storage,bundle)
    replay=replay_v1(bundle)
    summary={'as_of':as_of,'facilities':len(ASSETS),'company_records':len(companies),'source_families':len(SOURCES),'source_urls':len(docs),'registered_documents':len(package['documents']),'parsed_capacity_observations':len(package['records']),'relationships':len(package['relationships']),'build_hash':package['build_hash'],'replay':replay,'limitations':['Pilot coverage is 15 facilities, not final recommended 50–100','Source families: 3, not final recommended 5–10','Undated snapshots use capture observation date; not inferred historical effective dates','Portland PDF page 2 header says Huntly despite Portland body: extraction is restricted to page 1','Company country values are registration/jurisdiction metadata curated for this pilot; verify before legal use','Raw publisher snapshots retained locally; no redistribution license claimed']}
    (root/'pilot-validation.json').write_text(json.dumps(summary,indent=2));return summary

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--online',action='store_true');parser.add_argument('--as-of',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();date.fromisoformat(args.as_of)
    with Session(make_engine(DATABASE_URL)) as s: print(json.dumps(populate(s,os.getenv('SNAPSHOT_DIR','data/snapshots'),args.output,args.as_of,args.online),indent=2))
if __name__=='__main__': main()
