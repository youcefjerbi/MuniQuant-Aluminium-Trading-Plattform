from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Column, String, Integer, Float, Text, ForeignKey, JSON, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()
def uid(): return str(uuid4())
def now(): return datetime.now(timezone.utc).isoformat()

class Entity(Base):
    __tablename__ = "entities"
    id = Column(String, primary_key=True, default=uid)
    name = Column(String(256), nullable=False)
    kind = Column(String, nullable=False)
    facility_type = Column(String)
    country = Column(String(2))
    region = Column(String)
    commodity = Column(String, nullable=False, default="aluminium")
    aliases = Column(JSON, nullable=False, default=list)
    __table_args__ = (CheckConstraint("kind IN ('company','facility')"),)

class Source(Base):
    __tablename__ = "sources"
    id = Column(String, primary_key=True, default=uid)
    name = Column(String, nullable=False)
    publisher = Column(String, nullable=False)
    source_type = Column(String, nullable=False)
    url = Column(String, nullable=False)
    access_status = Column(String, nullable=False)
    notes = Column(Text, nullable=False, default="")

class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True, default=uid)
    source_id = Column(String, ForeignKey("sources.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    original_url = Column(String, nullable=False)
    published_at = Column(String)
    retrieved_at = Column(String, nullable=False, default=now)
    media_type = Column(String, nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint("source_id", "original_url", "content_hash"),
                      UniqueConstraint("source_id", "original_url", "version"), CheckConstraint("version > 0"))

class Observation(Base):
    __tablename__ = "observations"
    id = Column(String, primary_key=True, default=uid)
    entity_id = Column(String, ForeignKey("entities.id"), nullable=False, index=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    attribute = Column(String, nullable=False)
    reported_value = Column(String, nullable=False)
    reported_unit = Column(String, nullable=False)
    normalized_value = Column(Float)
    normalized_unit = Column(String)
    valid_from = Column(String, nullable=False)
    valid_to = Column(String)
    evidence_reference = Column(String, nullable=False)
    quality_status = Column(String, nullable=False)
    quality_messages = Column(JSON, nullable=False, default=list)
    parser_version = Column(String, nullable=False, default="manual-v1")
    recorded_at = Column(String, nullable=False, default=now)
    __table_args__ = (CheckConstraint("valid_to IS NULL OR valid_to >= valid_from"),
                      CheckConstraint("normalized_value IS NULL OR normalized_value >= 0"))

class Relationship(Base):
    __tablename__ = "relationships"
    id = Column(String, primary_key=True, default=uid)
    company_id = Column(String, ForeignKey("entities.id"), nullable=False)
    facility_id = Column(String, ForeignKey("entities.id"), nullable=False)
    role = Column(String, nullable=False)
    percentage = Column(Float)
    valid_from = Column(String, nullable=False)
    valid_to = Column(String)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    __table_args__ = (CheckConstraint("role IN ('OWNS','OPERATES')"),
                      CheckConstraint("percentage IS NULL OR (percentage >= 0 AND percentage <= 100)"),
                      CheckConstraint("valid_to IS NULL OR valid_to >= valid_from"))

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
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    evidence_reference = Column(String, nullable=False)
    __table_args__ = (CheckConstraint("volume IS NULL OR volume >= 0"),
                      CheckConstraint("open_interest IS NULL OR open_interest >= 0"))

class Review(Base):
    __tablename__ = "reviews"
    id = Column(String, primary_key=True, default=uid)
    raw_name = Column(String, nullable=False)
    candidate_ids = Column(JSON, nullable=False)
    status = Column(String, nullable=False, default="pending")
    selected_entity_id = Column(String, ForeignKey("entities.id"))
    reviewer = Column(String)
    reason = Column(Text)
    decided_at = Column(String)

class Run(Base):
    __tablename__ = "runs"
    id = Column(String, primary_key=True, default=uid)
    started_at = Column(String, nullable=False, default=now)
    pipeline_version = Column(String, nullable=False, default="0.1.0")
    status = Column(String, nullable=False)
    manifest = Column(JSON, nullable=False)

class Audit(Base):
    __tablename__ = "audit"
    id = Column(String, primary_key=True, default=uid)
    created_at = Column(String, nullable=False, default=now)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    record_id = Column(String, nullable=False)
    detail = Column(JSON, nullable=False)
