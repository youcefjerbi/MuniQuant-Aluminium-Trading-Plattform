"""Opt-in fictional fixtures. Never represent these as market or facility facts."""
import os
from datetime import date
from decimal import Decimal
from .domain import sync_entity
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import make_engine, DATABASE_URL
from .models import Entity, Source, Document, Relationship, Review, CompanyFacilityRelationship, EntityEvidence
from .schemas import DocumentIn, ObservationIn
from .services import acquire, add_observation

def seed():
    engine=make_engine(DATABASE_URL)
    with Session(engine) as s:
        if s.scalar(select(Entity.id).limit(1)): return
        source=Source(name='MuniQuant demonstration dataset',publisher='MuniQuant fixtures',source_type='synthetic',url='https://example.org/muniquant-demo',access_status='synthetic',notes='Fictional industrial facilities for software testing.')
        s.add(source);s.flush()
        company=Entity(name='Example Metals Group',kind='company',country='DE',region='Europe',aliases=[])
        s.add(company);s.flush();sync_entity(s,company,'fixture-curator')
        facilities=[('Nordhaven Smelter','NO','Europe','smelter',420),('Riverton Aluminium','CA','North America','smelter',310),('Coastal Alumina Works','AU','Oceania','refinery',1800),('Highland Bauxite Mine','GN','Africa','bauxite_mine',2400),('East Bay Smelter','CN','Asia','smelter',560),('Gulf Aluminium Works','AE','Middle East','smelter',720)]
        content='SYNTHETIC DEMONSTRATION ONLY\n'+ '\n'.join(f'{name}: {capacity} kt/year, 2025-01-01' for name,_,_,_,capacity in facilities)
        doc,_=acquire(s,os.getenv('SNAPSHOT_DIR','data/snapshots'),DocumentIn(source_id=source.id,title='Fictional industrial capacity register 2025',original_url='https://example.org/muniquant-demo/industrial-2025',published_at='2025-01-01',content=content))
        created=[]
        for name,country,region,kind,capacity in facilities:
            e=Entity(name=name,kind='facility',facility_type=kind,country=country,region=region,commodity='alumina' if kind=='refinery' else ('bauxite' if kind=='bauxite_mine' else 'aluminium'),aliases=[name.replace('Smelter','Works')] if 'Smelter' in name else [])
            s.add(e);s.flush();sync_entity(s,e,'fixture-curator');created.append(e)
            add_observation(s,ObservationIn(entity_id=e.id,document_id=doc.id,reported_value=str(capacity),reported_unit='kt/year',valid_from='2025-01-01',evidence_reference=f'Synthetic register: {name}'))
            link=Relationship(company_id=company.id,facility_id=e.id,role='OWNS',percentage=100,valid_from='2025-01-01',document_id=doc.id)
            s.add(link);s.flush()
            s.add(CompanyFacilityRelationship(relationship_id=link.id,company_id=company.id,facility_id=e.id,document_id=doc.id,role='OWNS',percentage=Decimal(100),valid_from=date(2025,1,1),evidence_reference='Fictional register: '+name))
            s.add(EntityEvidence(entity_id=e.id,document_id=doc.id,evidence_reference='Synthetic register: '+name,reviewer='fixture-curator',reason='Explicit fictional development fixture, not verified industrial data'))
        s.add(Review(raw_name='Bay aluminium',candidate_ids=[created[4].id,created[5].id],status='pending'))
        s.commit()
    print('Loaded fictional demonstration data.')
if __name__=='__main__': seed()
