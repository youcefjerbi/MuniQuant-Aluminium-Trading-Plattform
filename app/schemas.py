from datetime import date
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class SourceAccessIn(Input):
    status: Literal['permitted','review_required','restricted']
    allowed_hosts: list[str] = Field(default_factory=list, max_length=10)
    basis: str = Field(min_length=10, max_length=4000)
    retention: str = Field(min_length=5, max_length=2000)
    # Environment variable NAME holding a licensed API credential; the secret never enters the database.
    credential_ref: str | None = Field(default=None, pattern=r'^[A-Z][A-Z0-9_]{2,63}$')
    auth_header: Literal['x-api-key', 'authorization'] | None = None
    @field_validator('allowed_hosts')
    @classmethod
    def hosts(cls, value):
        import re
        if any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?', h) or '..' in h for h in value):
            raise ValueError('Approved hosts must be exact lowercase DNS hostnames')
        return sorted(set(value))
    @model_validator(mode='after')
    def credential_pair(self):
        if (self.credential_ref is None) != (self.auth_header is None): raise ValueError('Credential reference and header name must be set together')
        return self

class RetrievalIn(Input):
    source_id: str
    url: str = Field(min_length=10, max_length=2048)
    title: str = Field(min_length=1,max_length=256)
    published_at: date | None = None

class PermutableSourceIn(Input):
    credential_ref: str = Field(default='PERMUTABLE_API_KEY', pattern=r'^[A-Z][A-Z0-9_]{2,63}$')
    basis: str = Field(default='Commercial Permutable AI licence held by MuniQuant; factual event and headline feeds used as curator leads', min_length=10, max_length=4000)
    retention: str = Field(default='Raw API responses retained locally as fingerprinted snapshots; not redistributed and never exported as evidence', min_length=5, max_length=2000)

class PermutableCaptureIn(Input):
    feed: Literal['events', 'event_headlines', 'ticker_info', 'event_topics']
    mode: Literal['live', 'historical'] = 'live'
    ticker: str = Field(default='ALI_COM', pattern=r'^[A-Z0-9]{2,12}_[A-Z]{3}$')
    start_date: date | None = None
    end_date: date | None = None
    max_pages: int = Field(default=10, ge=1, le=100)
    @model_validator(mode='after')
    def window(self):
        if self.feed in ('ticker_info', 'event_topics') and self.mode != 'live': raise ValueError('Reference responses have no history')
        if self.mode == 'live' and (self.start_date or self.end_date): raise ValueError('Live capture takes no date window')
        if self.start_date and self.end_date and self.end_date < self.start_date: raise ValueError('Invalid capture window')
        return self

class LeadDecisionIn(Input):
    status: Literal['follow_up', 'dismissed', 'confirmed']
    reason: str = Field(min_length=3, max_length=2000)
    primary_document_id: str | None = None
    observation_id: str | None = None
    @model_validator(mode='after')
    def evidence(self):
        if self.status == 'confirmed' and not self.primary_document_id: raise ValueError('Confirming a lead requires the primary-source document')
        if self.status != 'confirmed' and (self.primary_document_id or self.observation_id): raise ValueError('Only confirmed leads link evidence')
        return self

class ProposalIn(Input):
    """A candidate fact for the Data Core: a Core document and how to find the value in its saved copy.

    extraction is the Core's extraction request (adapter, facility_name, country, valid_from,
    attribute, unit, prefix, suffix, page); the Core validates it and runs its own checks."""
    document_id: str = Field(min_length=1, max_length=100)
    extraction: dict[str, Any]
