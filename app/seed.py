"""Opt-in fictional fixtures. Never represent these as market or facility facts."""
import os
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import make_engine, DATABASE_URL
from .models import Entity, Source, Document, MarketObservation, Relationship, Review
from .schemas import DocumentIn, ObservationIn
from .services import acquire, add_observation

def seed():
    engine=make_engine(DATABASE_URL)
    with Session(engine) as s:
        if s.scalar(select(Entity.id).limit(1)): return
        source=Source(name='MuniQuant demonstration dataset',publisher='MuniQuant fixtures',source_type='synthetic',url='https://example.org/muniquant-demo',access_status='synthetic',notes='Fictional facilities and prices for software testing. Not market data.')
        s.add(source);s.flush()
        company=Entity(name='Example Metals Group',kind='company',country='DE',region='Europe',aliases=[])
        s.add(company);s.flush()
        facilities=[('Nordhaven Smelter','NO','Europe','smelter',420),('Riverton Aluminium','CA','North America','smelter',310),('Coastal Alumina Works','AU','Oceania','refinery',1800),('Highland Bauxite Mine','GN','Africa','bauxite_mine',2400),('East Bay Smelter','CN','Asia','smelter',560),('Gulf Aluminium Works','AE','Middle East','smelter',720)]
        content='SYNTHETIC DEMONSTRATION ONLY\n'+ '\n'.join(f'{name}: {capacity} kt/year, 2025-01-01' for name,_,_,_,capacity in facilities)
        doc,_=acquire(s,os.getenv('SNAPSHOT_DIR','data/snapshots'),DocumentIn(source_id=source.id,title='Fictional industrial capacity register 2025',original_url='https://example.org/muniquant-demo/industrial-2025',published_at='2025-01-01',content=content))
        created=[]
        for name,country,region,kind,capacity in facilities:
            e=Entity(name=name,kind='facility',facility_type=kind,country=country,region=region,commodity='alumina' if kind=='refinery' else ('bauxite' if kind=='bauxite_mine' else 'aluminium'),aliases=[name.replace('Smelter','Works')] if 'Smelter' in name else [])
            s.add(e);s.flush();created.append(e)
            add_observation(s,ObservationIn(entity_id=e.id,document_id=doc.id,reported_value=str(capacity),reported_unit='kt/year',valid_from='2025-01-01',evidence_reference=f'Synthetic register: {name}'))
            s.add(Relationship(company_id=company.id,facility_id=e.id,role='OWNS',percentage=100,valid_from='2025-01-01',document_id=doc.id))
        s.add(Review(raw_name='Bay aluminium',candidate_ids=[created[4].id,created[5].id],status='pending'))
        series=[('LME_AL_CASH','LME','benchmark','Global','USD',2470,None,None),('LME_AL_3M','LME','futures','Global','USD',2512,'LME-AL-20260102','2026-01-02'),('LME_AL_6M','LME','futures','Global','USD',2536,'LME-AL-20260402','2026-04-02'),('SHFE_AL_FRONT','SHFE','futures','China','CNY',20480,'AL2511','2025-11-17'),('SHFE_AL_ACTIVE','SHFE','futures','China','CNY',20520,'AL2512','2025-12-15'),('EUROPE_DUTY_PAID_PREMIUM','ASSESSMENT','physical_premium','Europe','USD',290,None,None),('EUROPE_DUTY_UNPAID_PREMIUM','ASSESSMENT','physical_premium','Europe','USD',225,None,None),('US_MIDWEST_PREMIUM','ASSESSMENT','physical_premium','US','USD',440,None,None),('JAPAN_PREMIUM','ASSESSMENT','physical_premium','Japan','USD',185,None,None)]
        market_doc,_=acquire(s,os.getenv('SNAPSHOT_DIR','data/snapshots'),DocumentIn(source_id=source.id,title='Fictional market observations — not live quotes',original_url='https://example.org/muniquant-demo/market',published_at='2025-10-02',content='SYNTHETIC PRICES; NOT FOR INVESTMENT USE\n'+'\n'.join(f'{a}: {e} {d}/tonne' for a,_,_,_,d,e,_,_ in series)))
        for instrument,exchange,market,region,currency,value,contract,prompt in series:
            s.add(MarketObservation(instrument=instrument,exchange=exchange,market=market,region=region,currency=currency,value=str(value),unit='tonne',contract_code=contract,prompt_date=prompt,commodity='aluminium',grade='primary',price_type='settlement' if market=='futures' else 'assessment',effective_at='2025-10-02T16:00:00+00:00',published_at='2025-10-02T17:00:00+00:00',data_status='synthetic',document_id=market_doc.id,evidence_reference='Synthetic fixture: '+instrument))
        s.commit()
    print('Loaded fictional demonstration data.')
if __name__=='__main__': seed()
