from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from acciones_ud.brokers.domain.entities import LinkStatus, ProposalStatus


class OutputModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Person(OutputModel):
    id: UUID
    name: str


class BrokerBrief(Person):
    firm_name: str


class ReputationResponse(OutputModel):
    broker_id: UUID
    name: str
    average: Decimal | None
    reviews_count: int
    converted_proposals: int
    distinct_investors: int
    years_experience: int
    broker_since: datetime


class BrokerSummary(OutputModel):
    id: UUID
    name: str
    firm_name: str
    specialty: str
    years_experience: int
    certifications: tuple[str, ...]
    reputation: ReputationResponse


class BrokerProfileResponse(BrokerSummary):
    description: str


class BrokerPage(OutputModel):
    items: list[BrokerSummary]
    next_cursor: str | None


class LinkResponse(OutputModel):
    id: UUID
    investor_id: UUID
    broker_id: UUID
    broker: BrokerBrief
    status: LinkStatus
    requested_at: datetime
    expires_at: datetime
    responded_at: datetime | None
    started_at: datetime | None
    ended_at: datetime | None
    decline_reason: str | None
    end_reason: str | None
    consent_version: str
    consent_accepted_at: datetime
    order_review_enabled: bool


class TradingAuthorizationResponse(OutputModel):
    id: UUID
    link_id: UUID
    consent_version: str
    granted_at: datetime
    revoked_at: datetime | None
    revoke_reason: Literal["investor", "link_ended"] | None


class CurrentLinkResponse(OutputModel):
    link: LinkResponse | None
    trading_authorization: TradingAuthorizationResponse | None
    pending_broker_selection: bool
    suggestions: list[BrokerSummary]


class LinkPage(OutputModel):
    items: list[LinkResponse]
    next_cursor: str | None


class LinkRequest(OutputModel):
    id: UUID
    investor_id: UUID
    investor_name: str
    requested_at: datetime


class ProposalVersion(OutputModel):
    proposal_id: UUID
    version: int
    symbol: str
    side: Literal["buy", "sell"]
    qty: Decimal
    type: Literal["market", "limit"]
    limit_price: Decimal | None
    time_in_force: Literal["day"]
    reference_price: Decimal
    estimated_cost: Decimal
    created_at: datetime


class ProposalDecision(OutputModel):
    id: UUID
    proposal_id: UUID
    version: int
    actor_id: UUID
    actor_role: Literal["investor", "broker"]
    decision: Literal["accept", "reject", "approve", "decline"]
    comment: str
    evidence_message_ids: tuple[UUID, ...]
    evidence_text: str
    at: datetime


class ProposalBase(OutputModel):
    id: UUID
    link_id: UUID
    status: ProposalStatus
    status_reason: str | None
    current_version: int
    accepted_version: int | None
    order_id: UUID | None
    failure_code: str | None
    broker: Person
    investor: Person
    created_at: datetime
    updated_at: datetime
    expires_at: datetime


class ProposalDetail(ProposalBase):
    versions: list[ProposalVersion]
    decisions: list[ProposalDecision]


class ProposalSummary(ProposalBase):
    symbol: str
    side: Literal["buy", "sell"]
    qty: Decimal
    type: Literal["market", "limit"]
    estimated_cost: Decimal


class ProposalPage(OutputModel):
    items: list[ProposalSummary]
    next_cursor: str | None


class Message(OutputModel):
    id: UUID
    proposal_id: UUID
    author_id: UUID
    body: str
    created_at: datetime


class MessagePage(OutputModel):
    items: list[Message]
    next_cursor: str | None


class RatingResponse(OutputModel):
    link_id: UUID
    investor_id: UUID
    broker_id: UUID
    stars: int
    comment: str
    created_at: datetime
    updated_at: datetime


class Review(OutputModel):
    stars: int
    comment: str
    created_at: datetime
    updated_at: datetime


class ReviewPage(OutputModel):
    items: list[Review]
    next_cursor: str | None


class ClientSummary(OutputModel):
    investor_id: UUID
    name: str
    link_id: UUID
    since: datetime
    trading_authorized: bool
    order_review_enabled: bool
