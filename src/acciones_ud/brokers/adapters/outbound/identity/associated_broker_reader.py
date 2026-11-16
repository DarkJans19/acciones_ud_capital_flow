from uuid import UUID

from acciones_ud.brokers.adapters.outbound.broker_link_adapter import BrokerLinkAdapter
from acciones_ud.brokers.adapters.outbound.identity.broker_directory import SessionFactory
from acciones_ud.brokers.adapters.outbound.persistence.models import links
from acciones_ud.identity.adapters.outbound.persistence.tables import users
from acciones_ud.identity.domain.associated_broker import AssociatedBroker
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.infrastructure.db import unit_of_work


class AssociatedBrokerReader:
    def __init__(self, sessions: SessionFactory = unit_of_work, clock: Clock | None = None) -> None:
        self.membership = BrokerLinkAdapter(sessions, clock)

    async def associated_broker(self, investor_id: UUID) -> AssociatedBroker | None:
        statement = (
            self.membership.query(
                links.c.broker_id,
                links.c.started_at,
                users.c.first_names,
                users.c.last_names,
                users.c.firm_name,
            )
            .where(links.c.investor_id == investor_id)
            .limit(1)
        )
        async with self.membership.sessions() as session:
            row = (await session.execute(statement)).mappings().first()
        if row is None or row["started_at"] is None:
            return None
        return AssociatedBroker(
            row["broker_id"],
            f"{row['first_names']} {row['last_names']}",
            row["firm_name"] or "",
            row["started_at"],
        )
