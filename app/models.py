"""Workspace records: licensed lead feeds, research, investigations, the map and the old trading screens.

Plants, companies, sources, documents and facts live in the Data Core. A column marked "Core
reference" holds a Data Core ID: a plain field, never a database link. Details are read through
the Core API (app.core_client).
"""
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Column, String, Integer, BigInteger, Text, ForeignKey, JSON, CheckConstraint, UniqueConstraint, Index, func, literal_column
from sqlalchemy.orm import declarative_base

Base = declarative_base()
def uid(): return str(uuid4())
def now(): return datetime.now(timezone.utc).isoformat()

class MarketObservation(Base):
    __tablename__ = "market_observations"
    id = Column(String, primary_key=True, default=uid)
    instrument = Column(String, nullable=False, index=True)
    exchange = Column(String, nullable=False)
    market = Column(String, nullable=False)
    contract_code = Column(String)
    prompt_date = Column(String)
    commodity = Column(String, nullable=False)
    grade = Column(String)
    region = Column(String, nullable=False)
    price_type = Column(String, nullable=False)
    value = Column(String, nullable=False)
    currency = Column(String(3), nullable=False)
    unit = Column(String, nullable=False)
    effective_at = Column(String, nullable=False, index=True)
    published_at = Column(String)
    volume = Column(Integer)
    open_interest = Column(Integer)
    data_status = Column(String, nullable=False)
    document_id = Column(String, nullable=False)  # Core reference
    evidence_reference = Column(String, nullable=False)
    __table_args__ = (CheckConstraint("volume IS NULL OR volume >= 0"),
                      CheckConstraint("open_interest IS NULL OR open_interest >= 0"))

class Audit(Base):
    __tablename__ = "audit"
    id = Column(String, primary_key=True, default=uid)
    created_at = Column(String, nullable=False, default=now)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    record_id = Column(String, nullable=False)
    detail = Column(JSON, nullable=False)

class PaperAccount(Base):
    __tablename__ = 'paper_accounts'
    id = Column(String, primary_key=True)
    cash_cents = Column(BigInteger, nullable=False)
    cursor = Column(Integer, nullable=False)
    version = Column(Integer, nullable=False)
    __table_args__ = (CheckConstraint('cash_cents >= 0'), CheckConstraint('cursor >= 0 AND cursor < 120'))

class PaperOrder(Base):
    __tablename__ = 'paper_orders'
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String, nullable=False, unique=True)
    instrument = Column(String, nullable=False)
    side = Column(String, nullable=False)
    order_type = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    limit_cents = Column(Integer)
    fill_cents = Column(Integer)
    status = Column(String, nullable=False)
    created_at = Column(String, nullable=False, default=now)
    filled_at = Column(String)
    session_index = Column(Integer, nullable=False)
    actor = Column(String, nullable=False)
    __table_args__ = (CheckConstraint('quantity > 0'),CheckConstraint("side IN ('buy','sell')"),
                     CheckConstraint("status IN ('open','filled','cancelled','expired','settled')"))

# Lead feed store: licensed vendor responses that carry leads. They are preserved like evidence,
# with access decisions, exact bytes and attempt logs, but they are never evidence (ADR 0003).
class LeadSource(Base):
    __tablename__ = "lead_source"
    id = Column(String, primary_key=True, default=uid)
    name = Column(String, nullable=False)
    publisher = Column(String, nullable=False)
    source_type = Column(String, nullable=False)
    url = Column(String, nullable=False)
    access_status = Column(String, nullable=False)
    notes = Column(Text, nullable=False, default="")

class LeadDocument(Base):
    __tablename__ = "lead_document"
    id = Column(String, primary_key=True, default=uid)
    source_id = Column(String, ForeignKey("lead_source.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    original_url = Column(String, nullable=False)
    published_at = Column(String)
    retrieved_at = Column(String, nullable=False, default=now)
    media_type = Column(String, nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint("source_id", "original_url", "content_hash"),
                      UniqueConstraint("source_id", "original_url", "version"), CheckConstraint("version > 0"))

class LeadRun(Base):
    __tablename__ = "lead_run"
    id = Column(String, primary_key=True, default=uid)
    started_at = Column(String, nullable=False, default=now)
    pipeline_version = Column(String, nullable=False, default="0.1.0")
    status = Column(String, nullable=False)
    manifest = Column(JSON, nullable=False)

class LeadSourceAccess(Base):
    __tablename__ = 'lead_source_access'
    id = Column(String, primary_key=True, default=uid)
    source_id = Column(String, ForeignKey('lead_source.id'), nullable=False, index=True)
    status = Column(String, nullable=False)
    allowed_hosts = Column(JSON, nullable=False)
    basis = Column(Text, nullable=False)
    retention = Column(Text, nullable=False)
    reviewer = Column(String, nullable=False)
    decided_at = Column(String, nullable=False, default=now)
    # Name of the server environment variable holding an API credential; never the secret itself.
    credential_ref = Column(String(64))
    auth_header = Column(String(64))
    __table_args__ = (CheckConstraint("status IN ('permitted','review_required','restricted')", name='ck_source_access_status'),
                      CheckConstraint('(credential_ref IS NULL) = (auth_header IS NULL)', name='ck_source_access_credential'))

class LeadSnapshot(Base):
    __tablename__ = 'lead_snapshot'
    content_hash = Column(String(64), primary_key=True)
    storage_reference = Column(String, nullable=False)
    byte_size = Column(Integer)
    __table_args__ = (CheckConstraint('byte_size >= 0', name='ck_snapshot_size'),)

class LeadDocumentVersion(Base):
    __tablename__ = 'lead_document_version'
    document_id = Column(String, ForeignKey('lead_document.id'), primary_key=True)
    snapshot_hash = Column(String(64), ForeignKey('lead_snapshot.content_hash'), nullable=False)
    version = Column(Integer, nullable=False)
    __table_args__ = (CheckConstraint('version > 0', name='ck_document_version_positive'),)

class LeadSourceDocument(Base):
    __tablename__ = 'lead_source_document'
    source_id = Column(String, ForeignKey('lead_source.id'), primary_key=True)
    document_id = Column(String, ForeignKey('lead_document.id'), primary_key=True)

class LeadRetrievalAttempt(Base):
    __tablename__ = 'lead_retrieval_attempt'
    id = Column(String, primary_key=True, default=uid)
    run_id = Column(String, ForeignKey('lead_run.id'), nullable=False, index=True)
    url = Column(String, nullable=False)
    attempt = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    error = Column(String)
    http_status = Column(Integer)
    recorded_at = Column(String, nullable=False, default=now)

# Leads from licensed event feeds: curator work items, never exported evidence.
class Lead(Base):
    __tablename__ = 'lead'
    id = Column(String, primary_key=True)
    source_id = Column(String, ForeignKey('lead_source.id'), nullable=False, index=True)
    external_id = Column(String(128), nullable=False)
    ticker = Column(String(32), nullable=False)
    status = Column(String, nullable=False, default='new')
    first_seen_at = Column(String, nullable=False)
    last_seen_at = Column(String, nullable=False)
    # Current view of the newest vendor revision, kept for sorting and filtering only.
    event_date = Column(String, index=True)
    topic_name = Column(String)
    vendor_updated_at = Column(String)
    current_revision_hash = Column(String(64))
    matched_entity_count = Column(Integer, nullable=False, default=0, server_default='0')
    reviewer = Column(String)
    reason = Column(Text)
    decided_at = Column(String)
    primary_document_id = Column(String)  # Core reference: the confirming primary-source document
    observation_id = Column(String)  # Core reference: the fact that document supports
    # Search projection: factual event text, current Core plant names and headlines (app.permutable).
    search_text = Column(Text, nullable=False, default='', server_default='')
    __table_args__ = (Index('ix_lead_status_date', 'status', 'event_date', 'last_seen_at', 'id'),
                      Index('ix_lead_topic_date', 'topic_name', 'event_date', 'last_seen_at', 'id'),
                      Index('ix_lead_date_seen', 'event_date', 'last_seen_at', 'id'),
                      UniqueConstraint('source_id', 'external_id', name='uq_lead_source_external'),
                      CheckConstraint("status IN ('new','follow_up','dismissed','confirmed')", name='ck_lead_status'),
                      CheckConstraint("status <> 'confirmed' OR primary_document_id IS NOT NULL", name='ck_lead_confirmed_evidence'))

# Match the production expression index in schema metadata.
Index('ix_lead_search_gin',
      func.to_tsvector(literal_column("'simple'::regconfig"), Lead.search_text),
      postgresql_using='gin', _table=Lead.__table__).ddl_if(dialect='postgresql')

class LeadRevision(Base):
    """One distinct factual state of a vendor event, kept with the first snapshot that carried it."""
    __tablename__ = 'lead_revision'
    id = Column(String, primary_key=True)
    lead_id = Column(String, ForeignKey('lead.id'), nullable=False, index=True)
    document_id = Column(String, ForeignKey('lead_document.id'), nullable=False, index=True)
    content_hash = Column(String(64), nullable=False)
    parser_version = Column(String, nullable=False)
    event_name = Column(Text, nullable=False)
    event_date = Column(String)
    summary = Column(Text, nullable=False)
    topic_name = Column(String)
    event_type = Column(String)
    vendor_updated_at = Column(String)
    matched_entity_ids = Column(JSON, nullable=False, default=list)  # Core references
    recorded_at = Column(String, nullable=False, default=now)
    __table_args__ = (UniqueConstraint('lead_id', 'content_hash', name='uq_lead_revision_content'),)

class LeadHeadline(Base):
    __tablename__ = 'lead_headline'
    id = Column(String, primary_key=True)
    lead_id = Column(String, ForeignKey('lead.id'), nullable=False, index=True)
    document_id = Column(String, ForeignKey('lead_document.id'), nullable=False, index=True)
    content_hash = Column(String(64), nullable=False)
    parser_version = Column(String, nullable=False)
    headline = Column(Text, nullable=False)
    source_name = Column(String)
    link = Column(String(2048))
    published_at = Column(String)
    language = Column(String(16))
    recorded_at = Column(String, nullable=False, default=now)
    __table_args__ = (UniqueConstraint('lead_id', 'content_hash', name='uq_lead_headline_content'),)

# Import the isolated experimental models so Alembic sees the complete metadata.
from . import research_models  # noqa: E402,F401

from . import asset_map  # noqa: E402,F401

from . import investigations  # noqa: E402,F401
