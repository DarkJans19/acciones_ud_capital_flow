"""MOD-06 RF-13--23: immutable business records, independent of infrastructure."""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

Role = Literal["investor", "broker", "system"]
EventType = Literal["broker_link_updates", "proposal_updates"]


class LinkStatus(StrEnum):
    REQUESTED = "requested"
    ACTIVE = "active"
    DECLINED = "declined"
    CANCELED = "canceled"
    EXPIRED = "expired"
    ENDED = "ended"


class LinkAction(StrEnum):
    ACCEPT = "accept"
    DECLINE = "decline"
    CANCEL = "cancel"
    EXPIRE = "expire"
    END = "end"


@dataclass(frozen=True)
class Link:
    id: UUID
    investor_id: UUID
    broker_id: UUID
    status: LinkStatus
    requested_at: datetime
    expires_at: datetime
    consent_version: str
    consent_accepted_at: datetime
    responded_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    decline_reason: str | None = None
    end_reason: str | None = None
    order_review_enabled: bool = False


@dataclass(frozen=True)
class TradingAuthorization:
    id: UUID
    link_id: UUID
    consent_version: str
    granted_at: datetime
    revoked_at: datetime | None = None
    revoke_reason: str | None = None


class ProposalStatus(StrEnum):
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    APPROVED = "approved"
    DECLINED_BY_BROKER = "declined_by_broker"
    CONVERSION_FAILED = "conversion_failed"
    EXPIRED = "expired"


class ProposalAction(StrEnum):
    MODIFY = "modify"
    ACCEPT = "accept"
    REJECT = "reject"
    WITHDRAW = "withdraw"
    APPROVE = "approve"
    DECLINE = "decline"
    CONVERSION_FAIL = "conversion_fail"
    EXPIRE = "expire"


@dataclass(frozen=True)
class Proposal:
    id: UUID
    link_id: UUID
    broker_id: UUID
    investor_id: UUID
    status: ProposalStatus
    current_version: int
    created_at: datetime
    updated_at: datetime
    last_version_at: datetime
    expires_at: datetime
    status_reason: str | None = None
    accepted_version: int | None = None
    order_id: UUID | None = None
    failure_code: str | None = None


@dataclass(frozen=True)
class ProposalVersion:
    proposal_id: UUID
    version: int
    symbol: str
    side: Literal["buy", "sell"]
    qty: Decimal
    type: Literal["market", "limit"]
    limit_price: Decimal | None
    reference_price: Decimal
    estimated_cost: Decimal
    created_at: datetime
    time_in_force: Literal["day"] = "day"


@dataclass(frozen=True)
class ProposalDecision:
    id: UUID
    proposal_id: UUID
    version: int
    actor_id: UUID
    actor_role: Role
    decision: Literal["accept", "reject", "approve", "decline"]
    at: datetime
    comment: str = ""
    evidence_message_ids: tuple[UUID, ...] = ()
    evidence_text: str = ""


@dataclass(frozen=True)
class ProposalMessage:
    id: UUID
    proposal_id: UUID
    author_id: UUID
    body: str
    created_at: datetime


@dataclass(frozen=True)
class BrokerProfile:
    broker_id: UUID
    specialty: str
    years_experience: int
    certifications: tuple[str, ...]
    description: str
    updated_at: datetime


@dataclass(frozen=True)
class Rating:
    link_id: UUID
    investor_id: UUID
    broker_id: UUID
    stars: int
    comment: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Reputation:
    broker_id: UUID
    name: str
    average: Decimal | None
    reviews_count: int
    converted_proposals: int
    distinct_investors: int
    years_experience: int
    broker_since: datetime


@dataclass(frozen=True)
class BrokerEvent:
    id: UUID
    entity_type: Literal["link", "trading_authorization", "proposal"]
    entity_id: UUID
    from_status: str | None
    to_status: str
    actor_type: Role
    actor_id: UUID | None
    reason: str | None
    at: datetime
    details: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerIdentity:
    user_id: UUID
    name: str
    firm_name: str
    license_number: str
    broker_since: datetime


@dataclass(frozen=True)
class Period:
    start: date
    end: date


@dataclass(frozen=True)
class BrokersConfig:
    link_ttl_days: int = 7
    proposal_ttl_hours: int = 72
    link_consent_version: str = "v1"
    trading_consent_version: str = "v1"
    commission_rate: Decimal = Decimal("0.02")
