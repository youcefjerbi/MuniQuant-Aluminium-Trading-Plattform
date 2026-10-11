"""Analyst-led cases independent of API event ingestion and trading."""
from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, Field, ConfigDict, model_validator
from sqlalchemy import Column, String, Integer, JSON, ForeignKey, UniqueConstraint, CheckConstraint, select, update
from .models import Base, uid, now, Entity, Document

Status = Literal['investigating', 'confirmed', 'disproven', 'resolved', 'inconclusive']

class Investigation(Base):
    __tablename__ = 'investigation'
    id = Column(String, primary_key=True, default=uid)
    title = Column(String(200), nullable=False)
    status = Column(String(32), nullable=False)
    version = Column(Integer, nullable=False)
    snapshot = Column(JSON, nullable=False)
    created_at = Column(String, nullable=False, default=now)
    updated_at = Column(String, nullable=False, default=now)
    __table_args__ = (CheckConstraint("status IN ('investigating','confirmed','disproven','resolved','inconclusive')", name='ck_investigation_status'),)

class InvestigationRevision(Base):
    __tablename__ = 'investigation_revision'
    id = Column(String, primary_key=True, default=uid)
    case_id = Column(String, ForeignKey('investigation.id'), nullable=False)
    version = Column(Integer, nullable=False)
    actor = Column(String, nullable=False)
    snapshot = Column(JSON, nullable=False)
    created_at = Column(String, nullable=False, default=now)
    __table_args__ = (UniqueConstraint('case_id','version',name='uq_investigation_version'),)

class CaseIn(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title: str = Field(min_length=1,max_length=200)
    summary: str = Field(default='',max_length=10000)
    owner: str = Field(default='',max_length=200)
    region: str = Field(default='',max_length=200)
    asset_ids: list[str] = Field(default_factory=list,max_length=100)
    review_at: str | None = None

class EntryIn(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    kind: Literal['evidence','hypothesis','contradiction','question','note','conclusion']
    text: str = Field(min_length=1,max_length=10000)
    document_id: str | None = Field(default=None,max_length=100)
    source_url: str | None = Field(default=None,max_length=2000)
    @model_validator(mode='after')
    def evidence_source(self):
        if self.kind == 'evidence' and not (self.document_id or self.source_url):
            raise ValueError('Evidence requires a registered document or source URL')
        if self.source_url:
            parsed=urlsplit(self.source_url)
            if parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('Use an HTTP(S) source URL without credentials')
        return self

class RevisionIn(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    expected_version: int = Field(ge=1)
    status: Status | None = None
    owner: str | None = Field(default=None,max_length=200)
    review_at: str | None = None
    entry: EntryIn | None = None

class CaseConflict(Exception):
    pass


def review_time(value):
    if not value:
        return None
    from datetime import datetime, timezone
    date=datetime.fromisoformat(value.replace('Z','+00:00'))
    if date.tzinfo is None:
        raise ValueError('Review date must have a timezone')
    return date.astimezone(timezone.utc).isoformat()


def create(s, data, actor):
    payload=data.model_dump()
    payload['asset_ids']=list(dict.fromkeys(payload['asset_ids']))
    for identifier in payload['asset_ids']:
        if not s.get(Entity, identifier):
            raise ValueError('Affected asset is not registered')
    payload['review_at']=review_time(payload['review_at'])
    payload.update(status='investigating',entries=[])
    case=Investigation(title=data.title,status='investigating',version=1,snapshot=payload)
    s.add(case);s.flush()
    s.add(InvestigationRevision(case_id=case.id,version=1,actor=actor,snapshot=payload))
    return case


def revise(s, case, data, actor):
    import copy
    snapshot=copy.deepcopy(case.snapshot)
    if data.entry:
        if len(snapshot['entries']) >= 1000:
            raise ValueError('A case supports at most 1,000 entries')
        entry=data.entry.model_dump()
        if entry['document_id'] and not s.get(Document,entry['document_id']):
            raise ValueError('Evidence document is not registered')
        entry.update(id=uid(),actor=actor,recorded_at=now())
        snapshot['entries'].append(entry)
    if data.owner is not None: snapshot['owner']=data.owner
    if 'review_at' in data.model_fields_set: snapshot['review_at']=review_time(data.review_at)
    if data.status is not None: snapshot['status']=data.status
    if snapshot['status'] != 'investigating' and not any(e['kind']=='conclusion' for e in snapshot['entries']):
        raise ValueError('Record a conclusion before changing to a finding status')
    if snapshot['status']=='confirmed' and not any(e['kind']=='evidence' for e in snapshot['entries']):
        raise ValueError('Confirmed cases require sourced evidence')
    if snapshot==case.snapshot:
        raise ValueError('No changes submitted')
    version=data.expected_version+1
    result=s.execute(update(Investigation).where(Investigation.id==case.id,Investigation.version==data.expected_version)
        .values(snapshot=snapshot,status=snapshot['status'],version=version,updated_at=now()).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        raise CaseConflict('Case changed; refresh before saving your revision')
    s.add(InvestigationRevision(case_id=case.id,version=version,actor=actor,snapshot=snapshot))
    s.flush();s.refresh(case)
    return case
