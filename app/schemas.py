from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class EntityIn(Input):
    name: str = Field(min_length=1, max_length=256)
    kind: Literal['company', 'facility'] = 'facility'
    facility_type: Literal['smelter', 'refinery', 'bauxite_mine'] | None = None
    country: str = Field(pattern=r'^[A-Z]{2}$')
    region: str = ''
    commodity: str = 'aluminium'
    aliases: list[str] = Field(default_factory=list, max_length=30)
    @field_validator('aliases')
    @classmethod
    def aliases_valid(cls, value):
        if any(not x.strip() or len(x)>256 for x in value): raise ValueError('Invalid alias')
        return [x.strip() for x in value]
    @model_validator(mode='after')
    def facility_required(self):
        if self.kind == 'facility' and not self.facility_type: raise ValueError('Facility type required')
        return self

class SourceIn(Input):
    name: str = Field(min_length=1, max_length=256)
    publisher: str = Field(min_length=1, max_length=256)
    source_type: Literal['company', 'government', 'regulator', 'industry', 'exchange', 'synthetic']
    url: str = Field(pattern=r'^https?://', max_length=2048)
    access_status: Literal['permitted', 'review_required', 'restricted', 'synthetic'] = 'review_required'
    notes: str = Field(default='', max_length=4000)

class DocumentIn(Input):
    source_id: str
    title: str = Field(min_length=1, max_length=256)
    original_url: str = Field(pattern=r'^https?://', max_length=2048)
    published_at: date | None = None
    media_type: Literal['text/plain', 'text/csv', 'text/html', 'application/json'] = 'text/plain'
    content: str = Field(min_length=1, max_length=2_000_000)

class ObservationIn(Input):
    entity_id: str
    document_id: str
    attribute: Literal['capacity', 'status', 'power', 'ownership_percentage'] = 'capacity'
    reported_value: str = Field(min_length=1, max_length=100)
    reported_unit: str = Field(min_length=1, max_length=40)
    valid_from: date
    valid_to: date | None = None
    evidence_reference: str = Field(min_length=1, max_length=1000)
    @model_validator(mode='after')
    def dates(self):
        if self.valid_to and self.valid_to < self.valid_from: raise ValueError('Invalid validity interval')
        return self

class RelationshipIn(Input):
    evidence_reference: str = Field(default='Document overall (legacy)',min_length=3,max_length=1000)
    company_id: str
    facility_id: str
    role: Literal['OWNS', 'OPERATES']
    percentage: Decimal | None = Field(default=None, ge=0, le=100, max_digits=9, decimal_places=6, allow_inf_nan=False)
    valid_from: date
    valid_to: date | None = None
    document_id: str
    @model_validator(mode='after')
    def dates(self):
        if self.valid_to and self.valid_to < self.valid_from: raise ValueError('Invalid validity interval')
        return self

class ResolveIn(Input):
    entity_kind: Literal['company','facility'] = 'facility'
    name: str = Field(min_length=1, max_length=256)
    country: str | None = Field(default=None, pattern=r'^[A-Z]{2}$')

class DecisionIn(Input):
    selected_entity_id: str | None = None
    reason: str = Field(min_length=3, max_length=2000)

class CsvIn(Input):
    document_id: str

class SourceAccessIn(Input):
    status: Literal['permitted','review_required','restricted']
    allowed_hosts: list[str] = Field(default_factory=list, max_length=10)
    basis: str = Field(min_length=10, max_length=4000)
    retention: str = Field(min_length=5, max_length=2000)
    @field_validator('allowed_hosts')
    @classmethod
    def hosts(cls, value):
        import re
        if any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?', h) or '..' in h for h in value):
            raise ValueError('Approved hosts must be exact lowercase DNS hostnames')
        return sorted(set(value))

class RetrievalIn(Input):
    source_id: str
    url: str = Field(min_length=10, max_length=2048)
    title: str = Field(min_length=1,max_length=256)
    published_at: date | None = None

class AliasIn(Input):
    name: str = Field(min_length=1,max_length=256)
    reason: str = Field(min_length=3,max_length=2000)

class SupersessionIn(Input):
    new_entity_id: str
    reason: str = Field(min_length=3,max_length=2000)

class ExtractionIn(Input):
    adapter: Literal['csv-v1','html-v1','pdf-v1']
    facility_name: str | None = Field(default=None,max_length=256)
    country: str | None = Field(default=None,pattern=r'^[A-Z]{2}$')
    valid_from: date
    valid_to: date | None = None
    unit: Literal['t/year','kt/year','Mt/year','MW','percentage'] = 't/year'
    attribute: Literal['capacity','power','ownership_percentage'] = 'capacity'
    # A literal contextual prefix/suffix avoids regex execution from user input.
    prefix: str | None = Field(default=None,max_length=300)
    suffix: str | None = Field(default=None,max_length=300)
    page: int | None = Field(default=None,ge=1,le=200)
    @model_validator(mode='after')
    def complete(self):
        if self.valid_to and self.valid_to<self.valid_from: raise ValueError('Invalid interval')
        if self.adapter!='csv-v1' and (not self.facility_name or not self.prefix or not self.suffix):
            raise ValueError('Text extraction requires facility name and literal value context')
        return self

class EntityEvidenceIn(Input):
    document_id: str
    evidence_reference: str = Field(min_length=3,max_length=1000)
    reason: str = Field(min_length=10,max_length=2000)

class ReviewCandidateIn(Input):
    entity_id: str
    reason: str = Field(min_length=10,max_length=2000)
