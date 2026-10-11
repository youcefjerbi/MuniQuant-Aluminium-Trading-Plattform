from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

KINDS = ('sanction', 'conflict', 'policy', 'weather', 'energy', 'logistics', 'supply', 'demand', 'corporate', 'other')


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Timed(Strict):
    occurred_at: datetime
    known_at: datetime | None = None
    historical: bool = False

    @model_validator(mode='after')
    def timestamps(self):
        clock = datetime.now(timezone.utc)
        for value in (self.occurred_at, self.known_at):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError('Timestamps must include a timezone')
            if value is not None and value > clock:
                raise ValueError('Future timestamps are not allowed')
        if self.known_at is not None and self.known_at < self.occurred_at:
            raise ValueError('known_at cannot precede occurred_at')
        if not self.historical and self.known_at is not None:
            raise ValueError('Backdated availability requires historical=true; historical records cannot trigger trades')
        return self


class EventIn(Timed):
    external_key: str = Field(min_length=1, max_length=256)
    instrument: str = Field(default='ALUMINIUM_DEMO', min_length=1, max_length=64, pattern=r'^[A-Z0-9_.-]+$')
    kind: Literal['sanction', 'conflict', 'policy', 'weather', 'energy', 'logistics', 'supply', 'demand', 'corporate', 'other']
    title: str = Field(min_length=1, max_length=500)
    summary: str = Field(default='', max_length=10000)
    source_reference: str = Field(min_length=1, max_length=2048)
    entity_ids: list[str] = Field(default_factory=list, max_length=100)
    countries: list[str] = Field(default_factory=list, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=100)
    lead_id: str | None = None

    @field_validator('countries')
    @classmethod
    def country_codes(cls, values):
        if any(len(v) != 2 or not v.isascii() or not v.isalpha() for v in values):
            raise ValueError('Countries must be two-letter codes')
        return sorted(set(v.upper() for v in values))

    @field_validator('tags')
    @classmethod
    def bounded_tags(cls, values):
        if any(not v.strip() or len(v) > 100 for v in values):
            raise ValueError('Tags must contain 1–100 characters')
        return sorted(set(v.strip().casefold() for v in values))


class QuoteIn(Timed):
    external_key: str = Field(min_length=1, max_length=256)
    instrument: str = Field(default='ALUMINIUM_DEMO', min_length=1, max_length=64, pattern=r'^[A-Z0-9_.-]+$')
    price: Decimal = Field(gt=0, le=1000000000, max_digits=24, decimal_places=8)
    source_reference: str = Field(min_length=1, max_length=2048)


class OutcomeIn(Strict):
    event_id: str
    entry_quote_id: str
    exit_quote_id: str


class PolicyIn(Strict):
    enabled: bool = False
    instrument: str = Field(default='ALUMINIUM_DEMO', min_length=1, max_length=64, pattern=r'^[A-Z0-9_.-]+$')
    min_cases: int = Field(default=5, ge=3, le=100)
    min_similarity: float = Field(default=0.65, ge=0.1, le=1)
    edge_threshold_bps: int = Field(default=50, ge=1, le=10000)
    min_agreement: float = Field(default=0.8, ge=0.5, le=1)
    max_trade_notional: Decimal = Field(default=Decimal('1000'), gt=0, le=10000, decimal_places=2)
    max_exposure_fraction: Decimal = Field(default=Decimal('0.2'), gt=0, le=Decimal('0.5'), decimal_places=4)
    max_drawdown_fraction: Decimal = Field(default=Decimal('0.1'), gt=0, le=Decimal('0.25'), decimal_places=4)
    fee_bps: int = Field(default=5, ge=0, le=100)
    slippage_bps: int = Field(default=5, ge=0, le=100)
    cooldown_seconds: int = Field(default=3600, ge=60, le=86400)
    max_daily_trades: int = Field(default=5, ge=1, le=20)
    max_quote_age_seconds: int = Field(default=300, ge=1, le=900)
    max_event_age_seconds: int = Field(default=3600, ge=1, le=86400)
