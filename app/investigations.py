"""Analyst-led cases independent of API event ingestion and trading.

Affected assets and evidence documents are Data Core records: a case stores their Core IDs (a
document ID is one exact document version) and the Core API confirms they exist."""
from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, Field, ConfigDict, model_validator
from sqlalchemy import Column, String, Integer, JSON, ForeignKey, UniqueConstraint, CheckConstraint, select, update
from .models import Base, uid, now

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
    stance: Literal['supports','contradicts','context'] = 'context'
    hypothesis_id: str | None = Field(default=None,max_length=100)
    passage: str = Field(default='',max_length=10000)
    published_at: str | None = Field(default=None,max_length=40)
    @model_validator(mode='after')
    def evidence_source(self):
        if self.kind == 'evidence' and not (self.document_id or self.source_url):
            raise ValueError('Evidence requires a registered document or source URL')
        if self.source_url:
            parsed=urlsplit(self.source_url)
            if parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('Use an HTTP(S) source URL without credentials')
        return self

class TaskIn(BaseModel):
    model_config = ConfigDict(extra='forbid',str_strip_whitespace=True)
    id: str | None = Field(default=None,max_length=100)
    question: str = Field(min_length=1,max_length=2000)
    assignee: str = Field(default='',max_length=200)
    due_at: str | None = Field(default=None,max_length=40)
    status: Literal['open','in_progress','answered','cancelled'] = 'open'
    answer: str = Field(default='',max_length=10000)
    evidence_entry_ids: list[str] = Field(default_factory=list,max_length=100)

class RevisionIn(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    expected_version: int = Field(ge=1)
    status: Status | None = None
    owner: str | None = Field(default=None,max_length=200)
    review_at: str | None = None
    entry: EntryIn | None = None
    task: TaskIn | None = None

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


def create(s, data, actor, core):
    payload=data.model_dump()
    payload['asset_ids']=list(dict.fromkeys(payload['asset_ids']))
    for identifier in payload['asset_ids']:
        if not core.entity(identifier):
            raise ValueError('Affected asset is not registered')
    payload['review_at']=review_time(payload['review_at'])
    payload.update(status='investigating',entries=[],tasks=[])
    case=Investigation(title=data.title,status='investigating',version=1,snapshot=payload)
    s.add(case);s.flush()
    s.add(InvestigationRevision(case_id=case.id,version=1,actor=actor,snapshot=payload))
    return case


def revise(s, case, data, actor, core):
    import copy
    snapshot=copy.deepcopy(case.snapshot)
    if data.entry:
        if len(snapshot['entries']) >= 1000:
            raise ValueError('A case supports at most 1,000 entries')
        entry=data.entry.model_dump()
        if entry['document_id'] and not core.document(entry['document_id']):
            raise ValueError('Evidence document is not registered')
        if entry['hypothesis_id'] and not any(e['id']==entry['hypothesis_id'] and e['kind']=='hypothesis' for e in snapshot['entries']):
            raise ValueError('Hypothesis must belong to this investigation')
        if entry['published_at']: entry['published_at']=review_time(entry['published_at'])
        entry.update(id=uid(),actor=actor,recorded_at=now())
        snapshot['entries'].append(entry)
    if data.task:
        task=data.task.model_dump()
        task['due_at']=review_time(task['due_at'])
        task['evidence_entry_ids']=list(dict.fromkeys(task['evidence_entry_ids']))
        evidence={e['id'] for e in snapshot['entries'] if e['kind']=='evidence'}
        if any(i not in evidence for i in task['evidence_entry_ids']):
            raise ValueError('Task evidence must reference evidence in this case')
        if task['status']=='answered' and (not task['answer'] or not task['evidence_entry_ids']):
            raise ValueError('Answered tasks require an answer and case evidence')
        tasks=snapshot.setdefault('tasks',[])
        task.update(updated_by=actor,updated_at=now())
        if task['id']:
            old=next((t for t in tasks if t['id']==task['id']),None)
            if not old: raise ValueError('Task does not belong to this case')
            task.update(created_by=old['created_by'],created_at=old['created_at'])
            tasks[tasks.index(old)]=task
        else:
            if len(tasks)>=200: raise ValueError('A case supports at most 200 tasks')
            task.update(id=uid(),created_by=actor,created_at=now())
            tasks.append(task)
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
    persist_notebook(s,case.id,snapshot)
    s.flush();s.refresh(case)
    return case

class InvestigationEntry(Base):
    __tablename__='investigation_entry'
    id=Column(String,primary_key=True)
    case_id=Column(String,ForeignKey('investigation.id'),nullable=False,index=True)
    kind=Column(String(32),nullable=False,index=True)
    text=Column(String,nullable=False)
    document_id=Column(String)  # Core reference: one exact document version
    hypothesis_id=Column(String,ForeignKey('investigation_entry.id'))
    stance=Column(String(16),nullable=False)
    source_url=Column(String)
    passage=Column(String,nullable=False)
    published_at=Column(String)
    actor=Column(String,nullable=False)
    recorded_at=Column(String,nullable=False)

class InvestigationTask(Base):
    __tablename__='investigation_task'
    id=Column(String,primary_key=True)
    case_id=Column(String,ForeignKey('investigation.id'),nullable=False,index=True)
    question=Column(String,nullable=False)
    assignee=Column(String,nullable=False,index=True)
    due_at=Column(String,index=True)
    status=Column(String(16),nullable=False,index=True)
    answer=Column(String,nullable=False)
    created_by=Column(String,nullable=False)
    created_at=Column(String,nullable=False)
    updated_by=Column(String,nullable=False)
    updated_at=Column(String,nullable=False)

class InvestigationTaskEvidence(Base):
    __tablename__='investigation_task_evidence'
    task_id=Column(String,ForeignKey('investigation_task.id'),primary_key=True)
    entry_id=Column(String,ForeignKey('investigation_entry.id'),primary_key=True)


def persist_notebook(s,case_id,snapshot):
    """Transactional normalized current records; revisions remain historical snapshots."""
    from sqlalchemy import delete
    for entry in snapshot['entries']:
        if not s.get(InvestigationEntry,entry['id']):
            values={k:entry.get(k) for k in ['id','kind','text','document_id','hypothesis_id','source_url','published_at','actor','recorded_at']}
            values.update(case_id=case_id,stance=entry.get('stance','context'),passage=entry.get('passage',''))
            s.add(InvestigationEntry(**values));s.flush()
    for task in snapshot.get('tasks',[]):
        values={k:v for k,v in task.items() if k!='evidence_entry_ids'}
        values['case_id']=case_id
        row=s.get(InvestigationTask,task['id'])
        if row:
            for key,value in values.items():setattr(row,key,value)
        else:s.add(InvestigationTask(**values))
        s.flush()
        s.execute(delete(InvestigationTaskEvidence).where(InvestigationTaskEvidence.task_id==task['id']))
        for identifier in task['evidence_entry_ids']:
            s.add(InvestigationTaskEvidence(task_id=task['id'],entry_id=identifier))
    s.flush()
