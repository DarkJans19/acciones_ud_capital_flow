from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID

from acciones_ud.brokers.domain import entities as e
from acciones_ud.orders.domain.model import Raw


class CommissionTermsBySymbolPort(Protocol):
    async def rate_pct(self, symbol: str, at: datetime) -> Decimal: ...


@dataclass(frozen=True)
class ProposalOrderCommand:
    proposal_id: UUID
    investor_id: UUID
    broker_id: UUID
    symbol: str
    side: Literal["buy", "sell"]
    qty: Decimal
    type: Literal["market", "limit"]
    limit_price: Decimal | None
    time_in_force: Literal["day"] = "day"


@dataclass(frozen=True)
class OrderCreated:
    order_id: UUID


@dataclass(frozen=True)
class OrderRejected:
    code: str


@dataclass(frozen=True)
class OrderFilters:
    status: str | None = None
    symbol: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    page_size: int = 20
    cursor: str | None = None


class BrokerDirectoryPort(Protocol):
    async def get_broker(self, user_id: UUID) -> e.BrokerIdentity | None: ...
    async def search(
        self, text: str, exclude: UUID, cursor: str | None, limit: int
    ) -> list[e.BrokerIdentity]: ...
    async def all_active(self, exclude: UUID) -> list[e.BrokerIdentity]: ...
    async def has_role(self, user_id: UUID, role: Literal["investor", "broker"]) -> bool: ...
    async def display_name(self, user_id: UUID) -> str | None: ...


class BrokerRequestPort(Protocol):
    async def broker_requested(self, investor_id: UUID) -> bool: ...


class LinkedAccountPort(Protocol):
    async def has_linked_account(self, investor_id: UUID) -> bool: ...


class OrderControlsPort(Protocol):
    async def high_order_threshold_usd(self, investor_id: UUID) -> Decimal: ...


class TotpVerifierPort(Protocol):
    async def verify(self, user_id: UUID, code: str) -> bool: ...


class QuotePort(Protocol):
    async def tradable(self, symbol: str) -> bool: ...
    async def last_price(self, symbol: str) -> Decimal | None: ...


class OrderCreationPort(Protocol):
    async def create(self, command: ProposalOrderCommand) -> OrderCreated | OrderRejected: ...


class OrderQueryPort(Protocol):
    async def list_for_investor(self, investor_id: UUID, filters: OrderFilters) -> Raw: ...
    async def find_by_idempotency_key(
        self, investor_id: UUID, key: str, expected: ProposalOrderCommand | None = None
    ) -> UUID | None: ...


class BrokersNotifierPort(Protocol):
    async def notify(
        self, user_id: UUID, event_type: e.EventType, payload: Mapping[str, object]
    ) -> None: ...


class EvidenceRepository[T](Protocol):
    async def get(self, *, for_update: bool = False, **filters: object) -> T | None: ...
    async def list(self, **filters: object) -> list[T]: ...
    async def insert(self, value: T) -> bool: ...


class Repository[T](EvidenceRepository[T], Protocol):
    async def save(self, value: T, **expected: object) -> bool: ...


class LinkRepository(Repository[e.Link], Protocol):
    async def open_for(self, investor_id: UUID, *, for_update: bool = False) -> e.Link | None: ...
    async def page(
        self,
        investor_id: UUID,
        status: e.LinkStatus | None,
        start: datetime | None,
        end: datetime | None,
        now: datetime,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[e.Link], str | None]: ...
    async def expired_batch(self, now: datetime, limit: int) -> list[e.Link]: ...


class ProposalRepository(Repository[e.Proposal], Protocol):
    async def page(
        self,
        user_id: UUID,
        role: Literal["investor", "broker"],
        status: e.ProposalStatus | None,
        start: datetime | None,
        end: datetime | None,
        now: datetime,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[e.Proposal], str | None]: ...
    async def expired_batch(self, now: datetime, limit: int) -> list[e.Proposal]: ...


class RatingRepository(Repository[e.Rating], Protocol):
    async def upsert(self, value: e.Rating) -> e.Rating: ...
    async def page(
        self, broker_id: UUID, cursor: str | None, limit: int
    ) -> tuple[list[e.Rating], str | None]: ...


class ProfileRepository(Repository[e.BrokerProfile], Protocol):
    async def upsert(self, value: e.BrokerProfile) -> None: ...


class MessageRepository(Repository[e.ProposalMessage], Protocol):
    async def page(
        self, proposal_id: UUID, cursor: str | None, limit: int
    ) -> tuple[list[e.ProposalMessage], str | None]: ...


class BrokerWork(Protocol):
    links: LinkRepository
    authorizations: Repository[e.TradingAuthorization]
    proposals: ProposalRepository
    versions: Repository[e.ProposalVersion]
    decisions: Repository[e.ProposalDecision]
    messages: MessageRepository
    ratings: RatingRepository
    profiles: ProfileRepository
    events: EvidenceRepository[e.BrokerEvent]

    async def lock_investor(self, investor_id: UUID) -> None: ...


class BrokerWorkFactory(Protocol):
    def __call__(self) -> AbstractAsyncContextManager[BrokerWork]: ...
