from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Column, String, Integer, BigInteger, Float, Text, ForeignKey, JSON, CheckConstraint, UniqueConstraint
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
    superseded_by_id = Column(String, ForeignKey("entities.id"))
    __table_args__ = (CheckConstraint("kind IN ('company','facility')"),)

class Source(Base):
    __tablename__ = "sources"
    id = Column(String, primary_key=True, default=uid)
    name = Column(String, nullable=False)
    publisher = Column(String, nullable=False)
    source_type = Column(String, nullable=False)
    url = Column(String, nullable=False)
    access_status = Column(String, nullable=False)
    access_method = Column(String, nullable=False, default="manual")
    coverage = Column(Text, nullable=False, default="")
    update_frequency = Column(String, nullable=False, default="unknown")
    licence_notes = Column(Text, nullable=False, default="")
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
    superseded_by_id = Column(String, ForeignKey("observations.id"))
    supersession_reason = Column(Text)
    superseded_at = Column(String)
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
    evidence_reference = Column(Text, nullable=False, default="")
    superseded_by_id = Column(String, ForeignKey("relationships.id"))
    supersession_reason = Column(Text)
    superseded_at = Column(String)
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
    superseded_by_id = Column(String, ForeignKey("market_observations.id"))
    supersession_reason = Column(Text)
    superseded_at = Column(String)
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
    normalized_name = Column(String, nullable=False, default="")
    match_method = Column(String, nullable=False, default="NONE")
    resolver_version = Column(String, nullable=False, default="1.0.0")
    context = Column(JSON, nullable=False, default=dict)
    document_id = Column(String, ForeignKey("documents.id"))

class Run(Base):
    __tablename__ = "runs"
    id = Column(String, primary_key=True, default=uid)
    started_at = Column(String, nullable=False, default=now)
    pipeline_version = Column(String, nullable=False, default="0.1.0")
    status = Column(String, nullable=False)
    manifest = Column(JSON, nullable=False)
    finished_at = Column(String)

class Audit(Base):
    __tablename__ = "audit"
    id = Column(String, primary_key=True, default=uid)
    created_at = Column(String, nullable=False, default=now)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    record_id = Column(String, nullable=False)
    detail = Column(JSON, nullable=False)


class SourceAccess(Base):
    __tablename__ = "source_access"
    id = Column(String, primary_key=True, default=uid)
    source_id = Column(String, ForeignKey("sources.id"), nullable=False, index=True)
    credential_ref = Column(String)
    terms_url = Column(String)
    rate_limit_notes = Column(Text, nullable=False, default="")
    notes = Column(Text, nullable=False, default="")


class RetrievalAttempt(Base):
    __tablename__ = "retrieval_attempts"
    id = Column(String, primary_key=True, default=uid)
    run_id = Column(String, ForeignKey("runs.id"), nullable=False, index=True)
    source_id = Column(String, ForeignKey("sources.id"), nullable=False, index=True)
    document_id = Column(String, ForeignKey("documents.id"))
    requested_url = Column(String, nullable=False)
    attempted_at = Column(String, nullable=False, default=now)
    http_status = Column(Integer)
    outcome = Column(String, nullable=False)
    error_message = Column(Text)
    __table_args__ = (CheckConstraint("outcome IN ('SUCCESS','UNCHANGED','FAILED')"),)


class ResolutionMatch(Base):
    __tablename__ = "resolution_matches"
    review_id = Column(String, ForeignKey("reviews.id"), primary_key=True)
    entity_id = Column(String, ForeignKey("entities.id"), primary_key=True)
    method = Column(String, nullable=False)
    score = Column(Float, nullable=False)
    matched_text = Column(String, nullable=False)
    __table_args__ = (CheckConstraint("score >= 0 AND score <= 1"),)


class QualityRun(Base):
    __tablename__ = "quality_runs"
    id = Column(String, primary_key=True, default=uid)
    ruleset_version = Column(String, nullable=False)
    started_at = Column(String, nullable=False, default=now)
    finished_at = Column(String)
    status = Column(String, nullable=False)
    summary = Column(JSON, nullable=False, default=dict)


class QualityCheckResult(Base):
    __tablename__ = "quality_check_results"
    id = Column(String, primary_key=True, default=uid)
    quality_run_id = Column(String, ForeignKey("quality_runs.id"), nullable=False, index=True)
    check_code = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    subject_type = Column(String, nullable=False)
    subject_id = Column(String, nullable=False, index=True)
    message = Column(Text, nullable=False)
    details = Column(JSON, nullable=False, default=dict)
    __table_args__ = (CheckConstraint("severity IN ('INFO','WARN','ERROR','BLOCK')"),)

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
