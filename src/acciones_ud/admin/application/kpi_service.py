import logging
from datetime import datetime

from acciones_ud.admin.domain.kpis import KPI_DEFINITIONS_VERSION, compute
from acciones_ud.admin.domain.model import KpiSnapshot, Raw
from acciones_ud.admin.domain.periods import Period
from acciones_ud.admin.domain.ports import AdminWorkFactory, KpiSourcePort, PlatformLedgerPort
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import AppError, ErrorCode


class KpiService:
    def __init__(
        self,
        uow: AdminWorkFactory,
        source: KpiSourcePort,
        ledger: PlatformLedgerPort,
        clock: Clock,
        ttl: int,
    ) -> None:
        self.uow, self.source, self.ledger, self.clock, self.ttl = uow, source, ledger, clock, ttl

    def _out(self, snapshot: KpiSnapshot, hit: bool, stale: bool, at: datetime) -> Raw:
        return {
            "period": {
                "from": snapshot.period_from,
                "to": snapshot.period_to,
                "time_zone": "America/New_York",
            },
            "definitions_version": snapshot.definitions_version,
            "computed_at": snapshot.computed_at,
            "cache_hit": hit,
            "stale": stale,
            "as_of": min(
                Period(snapshot.period_from, snapshot.period_to).bounds()[1], snapshot.computed_at
            ),
            "metrics": snapshot.payload,
        }

    async def dashboard(self, period: Period, refresh: bool = False) -> Raw:
        now = self.clock.now()
        async with self.uow() as work:
            snapshot = await work.snapshots.get(period, KPI_DEFINITIONS_VERSION)
        if (
            snapshot
            and not refresh
            and 0 <= (now - snapshot.computed_at).total_seconds() < self.ttl
        ):
            return self._out(snapshot, True, False, now)
        try:
            inputs = await self.source.inputs(period, now)
            start, end = period.bounds()
            executions = [e async for e in self.ledger.iterate(start, end)]
            payload = compute(inputs, executions)
            updated = KpiSnapshot(period.from_, period.to, KPI_DEFINITIONS_VERSION, payload, now)
            async with self.uow() as work:
                await work.snapshots.upsert(updated)
            return self._out(updated, False, False, now)
        except AppError as exc:
            if exc.code != ErrorCode.DATABASE_UNAVAILABLE:
                raise
            if snapshot:
                logging.getLogger(__name__).warning("Serving stale admin KPI snapshot")
                return self._out(snapshot, True, True, now)
            raise
