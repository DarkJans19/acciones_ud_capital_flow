from uuid import UUID

import sqlalchemy as sa

from acciones_ud.identity.adapters.outbound.persistence.tables import (
    effective_assignment,
    users,
)
from acciones_ud.identity.adapters.outbound.persistence.tables import (
    notification_preferences as p,
)
from acciones_ud.identity.adapters.outbound.persistence.tables import (
    role_assignments as r,
)
from acciones_ud.shared.domain.clock import Clock


class ReportPreferencesReader:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock

    async def _investors(self, monthly: bool) -> list[UUID]:
        from acciones_ud.shared.infrastructure.db import unit_of_work

        eligible = sa.exists(
            sa.select(r.c.id).where(
                r.c.user_id == users.c.id,
                r.c.role_code == "investor",
                effective_assignment(r, users, self.clock.now()),
            )
        )
        preference = (
            users.c.monthly_report.is_(True)
            if monthly
            else sa.exists(
                sa.select(p.c.user_id).where(
                    p.c.user_id == users.c.id,
                    p.c.event_type == "daily_summary",
                    p.c.enabled.is_(True),
                )
            )
        )
        async with unit_of_work() as session:
            return list(
                (
                    await session.execute(
                        sa.select(users.c.id).where(eligible, preference).order_by(users.c.id)
                    )
                ).scalars()
            )

    async def daily_summary_investors(self) -> list[UUID]:
        return await self._investors(False)

    async def monthly_report_investors(self) -> list[UUID]:
        return await self._investors(True)
