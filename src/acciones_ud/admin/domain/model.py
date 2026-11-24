from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from acciones_ud.shared.domain.trading import CommissionTerms

Raw = dict[str, Any]


@dataclass(frozen=True)
class Page[T]:
    items: list[T]
    next_cursor: str | None = None


@dataclass(frozen=True)
class FeeVersion:
    id: UUID
    market_code: str | None
    version_no: int
    commission_rate_pct: Decimal
    platform_share_pct: Decimal
    effective_from: datetime
    reason: str
    created_by: UUID | None
    created_at: datetime
    canceled_at: datetime | None = None
    canceled_by: UUID | None = None
    cancel_reason: str | None = None

    @property
    def scope(self) -> str:
        return self.market_code or "default"

    @property
    def terms(self) -> CommissionTerms:
        return CommissionTerms(self.id, self.commission_rate_pct, self.platform_share_pct)


@dataclass(frozen=True)
class CommissionBreakdown:
    gross_amount: Decimal
    commission: Decimal
    platform_share: Decimal
    broker_share: Decimal
    total: Decimal | None
    net: Decimal | None


@dataclass(frozen=True)
class TradingHalt:
    id: UUID
    market_code: str | None
    reason: str
    starts_at: datetime
    ends_at: datetime | None
    created_by: UUID
    created_at: datetime
    released_at: datetime | None = None
    released_by: UUID | None = None
    release_reason: str | None = None

    @property
    def scope(self) -> str:
        return self.market_code or "global"


@dataclass(frozen=True)
class AccountRestriction:
    id: UUID
    user_id: UUID
    restriction_type: str
    reason: str
    evidence_text: str
    evidence_refs: list[Raw]
    restricted_by: UUID
    restricted_at: datetime
    lifted_at: datetime | None = None
    lifted_by: UUID | None = None
    lift_reason: str | None = None
    lift_evidence_text: str | None = None
    lift_evidence_refs: list[Raw] | None = None


@dataclass(frozen=True)
class ComplianceReport:
    id: UUID
    user_id: UUID
    period_from: date
    period_to: date
    rules_version: str
    content: Raw
    content_sha256: str
    generated_by: UUID
    generated_at: datetime


@dataclass(frozen=True)
class KpiSnapshot:
    period_from: date
    period_to: date
    definitions_version: str
    payload: Raw
    computed_at: datetime


@dataclass(frozen=True)
class LedgerExecution:
    execution_id: str
    order_id: UUID
    user_id: UUID
    symbol: str
    exchange: str
    side: str
    qty: Decimal
    price: Decimal
    executed_at: datetime
    signed_by_broker_id: UUID | None
    fee_version_id: UUID | None = None
    commission_rate_pct: Decimal | None = None
    platform_share_pct: Decimal | None = None


@dataclass(frozen=True)
class BehaviorEvent:
    id: str
    user_id: UUID
    order_id: UUID
    at: datetime
    kind: str
    user_rejection: bool = False


@dataclass(frozen=True)
class AtypicalFlag:
    event_id: str
    user_id: UUID
    at: datetime
    reasons: tuple[str, ...]
    observed: Raw
    references: tuple[str, ...] = ()
    rules_version: str = "atypical-v2"
    configuration: Raw = field(default_factory=dict)
