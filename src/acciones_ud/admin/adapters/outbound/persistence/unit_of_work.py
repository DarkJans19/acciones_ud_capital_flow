from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.admin.adapters.outbound.persistence import repositories as r
from acciones_ud.admin.adapters.outbound.persistence.dispatch_repository import DispatchRepository
from acciones_ud.admin.domain import ports as p
from acciones_ud.admin.domain.ports import AdminWork


@dataclass
class SqlWork:
    fees: p.FeeRepository
    halts: p.HaltRepository
    restrictions: p.RestrictionRepository
    audit: p.AuditWriter
    reports: p.ReportRepository
    snapshots: p.SnapshotRepository
    dispatches: p.DispatchRepository


def build_work(session: AsyncSession) -> SqlWork:
    return SqlWork(
        r.FeeRepository(session),
        r.HaltRepository(session),
        r.RestrictionRepository(session),
        r.AuditWriter(session),
        r.ReportRepository(session),
        r.SnapshotRepository(session),
        DispatchRepository(session),
    )


@asynccontextmanager
async def admin_uow() -> AsyncIterator[AdminWork]:
    from acciones_ud.shared.infrastructure.db import unit_of_work

    async with unit_of_work() as session:
        yield build_work(session)
