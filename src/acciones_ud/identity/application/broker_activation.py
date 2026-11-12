"""Broker activation grants the broker and investor roles atomically (D5, R2.12-2.17)."""

from uuid import UUID

from acciones_ud.identity.application.rbac_admin import assignment_out
from acciones_ud.identity.domain.admin_ports import AdminWorkFactory
from acciones_ud.identity.domain.audit import AuditAction, build_entry
from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.shared.domain.clock import Clock


class BrokerActivationService:
    def __init__(self, uow: AdminWorkFactory, clock: Clock) -> None:
        self.uow, self.clock = uow, clock

    async def activate(self, actor_id: UUID | None, user_id: UUID) -> Record:
        """One unit of work: conditional status change plus both Role_Assignments.

        The conditional ``UPDATE`` takes the users row lock, so a concurrent request
        blocks, re-reads the status and gets 409 before inserting anything (2.14).
        The RBAC seed stays unchanged: ``kyc:submit`` arrives through the investor
        assignment (D5).
        """
        now = self.clock.now()
        async with self.uow() as work:
            repo = work.admin
            await repo.mark_broker_active(user_id, now)
            broker = await repo.save_assignment(user_id, "broker", now, None, None)
            investor = await repo.save_assignment(user_id, "investor", now, None, None)
            if actor_id is not None:
                await work.audit.append(
                    build_entry(
                        AuditAction.BROKER_ACTIVATED,
                        actor_id,
                        "user",
                        str(user_id),
                        {
                            "broker_assignment_id": broker["id"],
                            "investor_assignment_id": investor["id"],
                        },
                        now,
                    )
                )
        return {
            "user_id": user_id,
            "account_status": "active",
            "role_assignment": assignment_out({**broker, "account_status": "active"}, now),
            "investor_assignment": assignment_out({**investor, "account_status": "active"}, now),
        }
