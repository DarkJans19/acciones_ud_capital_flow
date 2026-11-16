from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from acciones_ud.portfolio.adapters.outbound.persistence.report_repository import ReportRepository
from acciones_ud.portfolio.domain.ports import ReportRepository as ReportRepositoryPort


@dataclass
class ReportWork:
    reports: ReportRepositoryPort


@asynccontextmanager
async def report_uow() -> AsyncIterator[ReportWork]:
    from acciones_ud.shared.infrastructure.db import unit_of_work

    async with unit_of_work() as session:
        yield ReportWork(ReportRepository(session))
