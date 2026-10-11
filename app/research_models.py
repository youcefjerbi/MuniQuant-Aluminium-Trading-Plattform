"""Separate experimental research and paper ledger; never exported as evidence."""
from sqlalchemy import Column, String, Integer, Text, ForeignKey, JSON, CheckConstraint
from .models import Base, uid, now


class ResearchEvent(Base):
    __tablename__ = 'research_event'
    id = Column(String, primary_key=True, default=uid)
    external_key = Column(String(256), nullable=False, unique=True)
    instrument = Column(String(64), nullable=False, index=True)
    kind = Column(String(32), nullable=False)
    occurred_at = Column(String, nullable=False)
    known_at = Column(String, nullable=False, index=True)
    recorded_at = Column(String, nullable=False, default=now)
    historical = Column(Integer, nullable=False)
    payload = Column(JSON, nullable=False)
    chain = Column(JSON, nullable=False)
    features = Column(JSON, nullable=False)


class ResearchQuote(Base):
    __tablename__ = 'research_quote'
    id = Column(String, primary_key=True, default=uid)
    external_key = Column(String(256), nullable=False, unique=True)
    instrument = Column(String(64), nullable=False, index=True)
    price = Column(Text, nullable=False)
    observed_at = Column(String, nullable=False)
    known_at = Column(String, nullable=False)
    recorded_at = Column(String, nullable=False, default=now)
    source_reference = Column(Text, nullable=False)
    historical = Column(Integer, nullable=False)
    __table_args__ = (CheckConstraint('CAST(price AS NUMERIC) > 0', name='ck_research_quote_positive'),)


class ResearchOutcome(Base):
    __tablename__ = 'research_outcome'
    id = Column(String, primary_key=True, default=uid)
    event_id = Column(String, ForeignKey('research_event.id'), nullable=False, unique=True)
    entry_quote_id = Column(String, ForeignKey('research_quote.id'), nullable=False)
    exit_quote_id = Column(String, ForeignKey('research_quote.id'), nullable=False)
    return_fraction = Column(Text, nullable=False)
    available_at = Column(String, nullable=False)
    recorded_at = Column(String, nullable=False, default=now)


class PaperPolicy(Base):
    __tablename__ = 'paper_policy'
    id = Column(String, primary_key=True, default=uid)
    settings = Column(JSON, nullable=False)
    actor = Column(String, nullable=False)
    created_at = Column(String, nullable=False, default=now)


class PaperAccount(Base):
    __tablename__ = 'research_paper_account'
    id = Column(String, primary_key=True)
    policy_id = Column(String, ForeignKey('paper_policy.id'), nullable=False)
    instrument = Column(String(64), nullable=False)
    cash = Column(Text, nullable=False)
    quantity = Column(Text, nullable=False)
    peak_equity = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)


class PaperDecision(Base):
    __tablename__ = 'research_paper_decision'
    id = Column(String, primary_key=True, default=uid)
    event_id = Column(String, ForeignKey('research_event.id'), nullable=False, unique=True)
    policy_id = Column(String, ForeignKey('paper_policy.id'), nullable=False)
    quote_id = Column(String, ForeignKey('research_quote.id'))
    action = Column(String(8), nullable=False)
    reason = Column(Text, nullable=False)
    details = Column(JSON, nullable=False)
    actor = Column(String, nullable=False)
    created_at = Column(String, nullable=False, default=now)
    __table_args__ = (CheckConstraint("action IN ('BUY','SELL','HOLD')", name='ck_research_action'),)
