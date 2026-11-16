from uuid import UUID

from acciones_ud.portfolio.application import dtos
from acciones_ud.portfolio.domain import model as m
from acciones_ud.portfolio.domain.period import parse
from acciones_ud.portfolio.domain.ports import ExecutionQueryPort, InstrumentPort
from acciones_ud.portfolio.domain.statistics import summarize


class StatisticsService:
    def __init__(self, executions: ExecutionQueryPort, instruments: InstrumentPort) -> None:
        self.executions, self.instruments = executions, instruments

    async def statistics(self, user_id: UUID, period: m.Period) -> m.Statistics:
        since, until = parse(period.from_, period.to).bounds()
        executions = await self.executions.list(user_id, until=until, since=since)
        info = await self.instruments.classify({e.symbol for e in executions})
        return dtos.statistics(summarize(executions, info))
