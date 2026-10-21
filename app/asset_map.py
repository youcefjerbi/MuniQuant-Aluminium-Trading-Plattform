"""Asset map: Workspace locations and dependencies for Data Core plants.

Locations and links store Core plant and document IDs; plant details come from the Core API."""
from datetime import date
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator
from sqlalchemy import Column,String,Float,Integer,CheckConstraint,select
from .models import Base,uid,now

class AssetLocation(Base):
    __tablename__='asset_location'
    id=Column(String,primary_key=True,default=uid)
    entity_id=Column(String,nullable=False,index=True)  # Core reference
    latitude=Column(Float,nullable=False)
    longitude=Column(Float,nullable=False)
    document_id=Column(String,nullable=False)  # Core reference
    precision=Column(String(32),nullable=False)
    synthetic=Column(Integer,nullable=False)
    actor=Column(String,nullable=False)
    recorded_at=Column(String,nullable=False,default=now)
    __table_args__=(CheckConstraint('latitude BETWEEN -90 AND 90',name='ck_asset_latitude'),CheckConstraint('longitude BETWEEN -180 AND 180',name='ck_asset_longitude'))
class AssetDependency(Base):
    __tablename__='asset_dependency'
    id=Column(String,primary_key=True,default=uid)
    from_entity_id=Column(String,nullable=False,index=True)  # Core reference
    to_entity_id=Column(String,nullable=False,index=True)  # Core reference
    product=Column(String(32),nullable=False,index=True)
    kind=Column(String(32),nullable=False)
    document_id=Column(String,nullable=False)  # Core reference
    valid_from=Column(String,nullable=False)
    valid_to=Column(String)
    status=Column(String(16),nullable=False)
    note=Column(String,nullable=False)
    synthetic=Column(Integer,nullable=False)
    actor=Column(String,nullable=False)
    recorded_at=Column(String,nullable=False,default=now)
    __table_args__=(CheckConstraint('from_entity_id <> to_entity_id',name='ck_dependency_distinct'),CheckConstraint('valid_to IS NULL OR valid_to >= valid_from',name='ck_dependency_dates'))
class LocationIn(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    entity_id:str
    latitude:float=Field(ge=-90,le=90)
    longitude:float=Field(ge=-180,le=180)
    document_id:str
    precision:Literal['facility','approximate','country_centroid']='approximate'
    synthetic:bool=False
class DependencyIn(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    from_entity_id:str
    to_entity_id:str
    product:Literal['bauxite','alumina','primary_aluminium','electricity','other']
    kind:Literal['material_supply','power_supply','transport','ownership']
    document_id:str
    valid_from:date
    valid_to:date|None=None
    status:Literal['asserted','hypothesis']='asserted'
    note:str=Field(default='',max_length=5000)
    synthetic:bool=False
    @model_validator(mode='after')
    def dates(self):
        if self.from_entity_id==self.to_entity_id:raise ValueError('Choose two different assets')
        if self.valid_to and self.valid_to<self.valid_from:raise ValueError('Invalid validity interval')
        return self

def validate_references(core,data):
    for key in ('entity_id','from_entity_id','to_entity_id'):
        if key in data and not core.entity(data[key]):raise ValueError('Asset is not registered')
    if not core.document(data['document_id']):raise ValueError('Evidence document is not registered')

def graph(s,core,product=None,as_of=None):
    from .services import record
    day=(as_of or date.today()).isoformat()
    entities={e['id']:e for e in core.entities()}
    rows=s.scalars(select(AssetLocation).order_by(AssetLocation.recorded_at,AssetLocation.id).limit(10001)).all()
    if len(rows)>10000:raise ValueError('Map exceeds 10,000 locations')
    locations={r.entity_id:record(r) for r in rows}
    query=select(AssetDependency).where(AssetDependency.valid_from<=day,(AssetDependency.valid_to==None)|(AssetDependency.valid_to>=day))
    if product:query=query.where(AssetDependency.product==product)
    links=s.scalars(query.order_by(AssetDependency.id).limit(2001)).all()
    if len(links)>2000:raise ValueError('Map exceeds 2,000 dependencies; filter by product')
    linked={i for d in links for i in (d.from_entity_id,d.to_entity_id)}
    nodes=[{'entity':e,'location':locations.get(i)} for i,e in entities.items() if not product or i in linked]
    return {'nodes':nodes,'dependencies':[record(d) for d in links],'as_of':day,'missing_locations':sum(n['location'] is None for n in nodes)}
