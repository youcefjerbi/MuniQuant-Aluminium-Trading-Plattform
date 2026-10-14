"""Workspace-only proposals. Core facts remain behind the Core API."""
from sqlalchemy import Column, String, Text, JSON, ForeignKey, CheckConstraint
from .models import Base, uid, now


class TradingAgentRun(Base):
    __tablename__ = 'trading_agent_run'
    id = Column(String, primary_key=True, default=uid)
    request_key = Column(String(64), nullable=False, unique=True)
    instrument = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False, default='queued')
    active_slot = Column(String(32), unique=True)
    actor = Column(String, nullable=False)
    created_at = Column(String, nullable=False, default=now, index=True)
    completed_at = Column(String)
    inputs = Column(JSON, nullable=False)
    result = Column(JSON)
    error = Column(Text)
    paper_decision_id = Column(String, ForeignKey('research_paper_decision.id'), unique=True)
    __table_args__ = (CheckConstraint("status IN ('queued','running','completed','failed','cancelled')", name='ck_trading_agent_run_status'),)
