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
    attribute: Literal['capacity', 'status'] = 'capacity'
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
    company_id: str
    facility_id: str
    role: Literal['OWNS', 'OPERATES']
    percentage: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    valid_from: date
    valid_to: date | None = None
    document_id: str
    @model_validator(mode='after')
    def dates(self):
        if self.valid_to and self.valid_to < self.valid_from: raise ValueError('Invalid validity interval')
        return self

class MarketIn(Input):
    instrument: str = Field(min_length=1, max_length=100)
    exchange: str = Field(min_length=1, max_length=100)
    market: Literal['benchmark', 'futures', 'physical_premium', 'upstream']
    contract_code: str | None = None
    prompt_date: date | None = None
    commodity: str = 'aluminium'
    grade: str | None = None
    region: str = Field(min_length=1, max_length=100)
    price_type: Literal['bid','ask','open','high','low','close','settlement','assessment']
    value: Decimal = Field(allow_inf_nan=False, max_digits=20, decimal_places=6)
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    unit: Literal['tonne','lb']
    effective_at: datetime
    published_at: datetime | None = None
    volume: int | None = Field(default=None, ge=0)
    open_interest: int | None = Field(default=None, ge=0)
    data_status: Literal['synthetic','reported','preliminary','revised']
    document_id: str
    evidence_reference: str = Field(min_length=1, max_length=1000)
    @model_validator(mode='after')
    def identity(self):
        if self.market == 'futures' and (not self.contract_code or not self.prompt_date):
            raise ValueError('Futures require a concrete contract code and prompt date')
        for dt in [self.effective_at, self.published_at]:
            if dt and (dt.tzinfo is None or dt.utcoffset() is None): raise ValueError('Timestamp must include timezone')
        return self

class ResolveIn(Input):
    name: str = Field(min_length=1, max_length=256)
    country: str | None = Field(default=None, pattern=r'^[A-Z]{2}$')

class DecisionIn(Input):
    selected_entity_id: str | None = None
    reason: str = Field(min_length=3, max_length=2000)

class CsvIn(Input):
    document_id: str
