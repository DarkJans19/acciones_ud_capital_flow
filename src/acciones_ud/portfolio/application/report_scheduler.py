import logging
from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from acciones_ud.portfolio.application.report_service import ReportService
from acciones_ud.portfolio.domain.model import Period, Report, ReportType
from acciones_ud.portfolio.domain.ports import (
    MarketSessionPort,
    ReportNotifierPort,
    ReportPreferencesPort,
)
from acciones_ud.shared.domain.clock import Clock

logger = logging.getLogger(__name__)


class ReportScheduler:
    def __init__(
        self,
        reports: ReportService,
        preferences: ReportPreferencesPort,
        sessions: MarketSessionPort,
        notifier: ReportNotifierPort,
        clock: Clock,
    ) -> None:
        self.reports, self.preferences, self.sessions = reports, preferences, sessions
        self.notifier, self.clock = notifier, clock

    async def run_once(self) -> None:
        await self.run_cycle(self.clock.now())

    def _failed(self, user_id: UUID | None, type: str, period: Period | None) -> None:
        logger.warning(
            "portfolio.report_failed user_id=%s type=%s period=%s", user_id, type, period
        )

    async def _generate(self, user_id: UUID, type: ReportType, period: Period) -> None:
        try:
            await self.reports.create_scheduled(user_id, type, period)
        except Exception:
            self._failed(user_id, type, period)

    async def run_cycle(self, now: datetime) -> None:
        try:
            session = await self.sessions.last_closed_session(now)
            daily = await self.preferences.daily_summary_investors()
            if session is not None:
                for user_id in daily:
                    await self._generate(user_id, "daily_summary", Period(session, session))
        except Exception:
            self._failed(None, "daily_summary", None)
        today = now.astimezone(ZoneInfo("America/New_York")).date()
        end = today.replace(day=1) - timedelta(days=1)
        monthly = Period(date(end.year, end.month, 1), end)
        try:
            for user_id in await self.preferences.monthly_report_investors():
                await self._generate(user_id, "monthly", monthly)
        except Exception:
            self._failed(None, "monthly", monthly)
        async with self.reports.uow() as work:
            pending = await work.reports.pending_notification()
        for report in pending:
            try:
                if await self.notifier.notify(report.owner_id, self._payload(report)):
                    async with self.reports.uow() as work:
                        await work.reports.mark_notified(report.id, now)
            except Exception:
                self._failed(report.owner_id, report.type, report.period)

    def _payload(self, report: Report) -> dict[str, object]:
        keys = (
            "executions_count",
            "volume",
            "realized_pnl",
            "unrealized_pnl",
            "profitability",
            "commissions",
        )
        return {
            **{key: report.content.get(key) for key in keys},
            "report_id": str(report.id),
            "report_type": report.type,
            "period": {"from": report.period.from_.isoformat(), "to": report.period.to.isoformat()},
            "link": f"/portfolio/reports/{report.id}",
        }
