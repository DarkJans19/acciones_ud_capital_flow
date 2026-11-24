from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from acciones_ud.orders.adapters.inbound.http.schemas import orders as order_schemas


class AdminInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class AdminDecisionIn(AdminInput):
    reason: str = Field(min_length=1, max_length=500)
    totp_code: str | None = Field(default=None, max_length=64, repr=False, exclude=True)

    @field_validator("reason")
    @classmethod
    def meaningful_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Reason required")
        return value


class FeeIn(AdminDecisionIn):
    commission_rate_pct: Decimal = Field(ge=0, le=10, decimal_places=4, allow_inf_nan=False)
    platform_share_pct: Decimal = Field(ge=0, le=100, decimal_places=2, allow_inf_nan=False)
    expected_latest_version: int = Field(ge=0)
    effective_from: AwareDatetime | None = None


class HaltIn(AdminDecisionIn):
    scope: str = Field(min_length=1, max_length=32)
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None


class EvidenceRef(AdminInput):
    source: Literal["admin", "orders", "brokers", "auth", "execution"]
    id: str = Field(min_length=1, max_length=256)


class AdminEvidenceIn(AdminDecisionIn):
    evidence_text: str = Field(default="", max_length=2000)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list, max_length=20)


class RestrictIn(AdminEvidenceIn):
    user_id: UUID
    restriction_type: Literal["trading"] = "trading"


class ComplianceReportIn(AdminInput):
    from_: date = Field(alias="from")
    to: date


class AdminOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AdminPageOut[T](AdminOutput):
    items: list[T]
    next_cursor: str | None = None


class TermsOut(AdminOutput):
    fee_version_id: UUID | None
    commission_rate_pct: Decimal
    platform_share_pct: Decimal


class FeeOut(AdminOutput):
    id: UUID
    scope: str
    version_no: int
    commission_rate_pct: Decimal
    platform_share_pct: Decimal
    broker_share_pct: Decimal
    effective_from: datetime
    status: Literal["scheduled", "in_force", "superseded", "canceled"]
    reason: str
    created_by: UUID | None
    created_at: datetime
    canceled_at: datetime | None = None
    canceled_by: UUID | None = None
    cancel_reason: str | None = None


class MatrixRow(AdminOutput):
    scope: str
    terms: TermsOut
    current: FeeOut
    origin: str
    scheduled: list[dict[str, Any]]


class MatrixOut(AdminOutput):
    items: list[MatrixRow]


class Breakdown(AdminOutput):
    gross_amount: Decimal
    commission: Decimal | None
    platform_share: Decimal | None
    broker_share: Decimal | None
    total: Decimal | None
    net: Decimal | None


class CommissionQuoteOut(Breakdown, TermsOut):
    symbol: str
    market: str
    binding: Literal[False]
    quoted_at: datetime


class CommissionExecutionOut(Breakdown):
    execution_id: str
    order_id: UUID
    user_id: UUID
    symbol: str
    exchange: str
    side: Literal["buy", "sell"]
    qty: Decimal
    price: Decimal
    executed_at: datetime
    signed_by_broker_id: UUID | None
    fee_version_id: UUID | None
    commission_rate_pct: Decimal | None
    platform_share_pct: Decimal | None
    commission_status: Literal["official", "historical_terms_unknown"]
    investor_name: str = ""


class CommissionTotals(AdminOutput):
    commission: Decimal
    platform_share: Decimal
    broker_share: Decimal


class CommissionPeriodTotals(CommissionTotals):
    gross_amount: Decimal
    historical_terms_unknown_count: int
    complete: bool


class CommissionPage(AdminPageOut[CommissionExecutionOut]):
    totals: CommissionPeriodTotals
    by_market: dict[str, CommissionTotals]
    by_broker: dict[str, CommissionTotals]


class HaltOut(AdminOutput):
    id: UUID
    scope: str
    status: Literal["scheduled", "active", "released", "expired"]
    reason: str
    starts_at: datetime
    ends_at: datetime | None
    created_by: UUID
    created_at: datetime
    released_at: datetime | None
    released_by: UUID | None
    release_reason: str | None


class PublicHaltOut(AdminOutput):
    scope: str
    starts_at: datetime
    ends_at: datetime | None


class RestrictionOut(AdminOutput):
    id: UUID
    user_id: UUID
    restriction_type: Literal["trading"]
    status: Literal["active", "lifted"]
    reason: str
    evidence_text: str
    evidence_refs: list[EvidenceRef]
    restricted_by: UUID
    restricted_at: datetime
    lifted_at: datetime | None
    lifted_by: UUID | None
    lift_reason: str | None
    lift_evidence_text: str | None
    lift_evidence_refs: list[EvidenceRef] | None


class ComplianceReportOut(AdminOutput):
    id: UUID
    user_id: UUID
    period_from: date
    period_to: date
    rules_version: str
    content: dict[str, Any]
    content_sha256: str
    generated_by: UUID
    generated_at: datetime


class TrailEventOut(AdminOutput):
    source: Literal["admin", "orders", "brokers", "auth"]
    event_id: str
    occurred_at: datetime
    actor_type: str
    actor_id: UUID | None
    subject_user_id: UUID | None
    related_user_id: UUID | None
    action: str
    entity_type: str
    entity_id: str | None
    from_state: str | None
    to_state: str | None
    details: dict[str, Any]
    ip_address: str | None


class AdminMarketOut(AdminOutput):
    code: str
    name: str
    timezone: str
    default_schedule: dict[str, Any] | None
    overrides: list[dict[str, Any]]
    commission_terms: TermsOut
    fee_origin: str
    trading_halts: list[HaltOut]


class AtypicalOut(AdminOutput):
    event_id: str
    user_id: UUID
    at: datetime
    reasons: list[str]
    observed: dict[str, Any]
    references: list[str]
    rules_version: str
    configuration: dict[str, Any]


class AtypicalPage(AdminPageOut[AtypicalOut]):
    rules_version: str
    configuration: dict[str, Any]


class KpiOut(AdminOutput):
    period: dict[str, Any]
    definitions_version: str
    computed_at: datetime
    as_of: datetime
    cache_hit: bool
    stale: bool
    metrics: dict[str, Any]


class CustodyOrderOut(order_schemas.OrderSummary):
    user_id: UUID
    client_order_id: str
    fee_version_id: UUID | None
    commission_rate_pct: Decimal | None
    platform_share_pct: Decimal | None
    submit_attempted_at: datetime | None
    scheduled_session_end: datetime | None


class CustodyProposalOut(AdminOutput):
    id: UUID
    investor_id: UUID
    broker_id: UUID
    accepted_version: int | None


class OrderCustodyOut(AdminOutput):
    order: CustodyOrderOut
    events: list[order_schemas.EventOut]
    executions: list[order_schemas.ExecutionOut]
    cancel_requests: list[order_schemas.CancelOut]
    reauthorizations: list[order_schemas.ReauthorizationOut]
    proposals: list[CustodyProposalOut]
    created_by: UUID | None
    authorization_method: str | None
    signed_by: UUID | None
    signed_at: datetime | None
    first_submitted_at: datetime | None


class ScheduleChangeOut(AdminOutput):
    id: UUID
    actor_user_id: UUID
    action: str
    target_id: str
    occurred_at: datetime
    override_id: UUID | None
    effective_from: date
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    payload: dict[str, Any]
    dispatch_status: Literal["pending", "dispatched"]
    dispatched_at: datetime | None
    affected_orders: int | None
    notified_users: int | None
