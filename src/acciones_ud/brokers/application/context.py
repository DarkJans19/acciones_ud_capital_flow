import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from acciones_ud.brokers.domain import entities as e
from acciones_ud.brokers.domain import ports as p
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import AppError, ErrorCode

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BrokerContext:
    uow: p.BrokerWorkFactory
    directory: p.BrokerDirectoryPort
    requests: p.BrokerRequestPort
    accounts: p.LinkedAccountPort
    controls: p.OrderControlsPort
    totp: p.TotpVerifierPort
    quotes: p.QuotePort
    order_creation: p.OrderCreationPort
    order_query: p.OrderQueryPort
    notifier: p.BrokersNotifierPort
    clock: Clock
    config: e.BrokersConfig

    async def require_role(self, user_id: UUID, role: Literal["broker", "investor"]) -> None:
        if not await self.directory.has_role(user_id, role):
            raise AppError(403, ErrorCode.FORBIDDEN, "Role required.")

    async def notify(self, user_id: UUID, event_type: e.EventType, **payload: object) -> None:
        try:
            await self.notifier.notify(user_id, event_type, payload)
        except Exception:
            logger.warning("Broker notification failed", extra={"event_type": event_type})

    async def event(
        self,
        work: p.BrokerWork,
        entity_type: Literal["link", "trading_authorization", "proposal"],
        ident: UUID,
        previous: str | None,
        target: str,
        role: e.Role,
        actor_id: UUID | None,
        reason: str | None = None,
        at: datetime | None = None,
        **details: object,
    ) -> None:
        await work.events.insert(
            e.BrokerEvent(
                uuid4(),
                entity_type,
                ident,
                previous,
                target,
                role,
                actor_id,
                reason,
                at or self.clock.now(),
                details,
            )
        )
