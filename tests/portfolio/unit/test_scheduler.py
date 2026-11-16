from datetime import UTC, date, datetime
from decimal import Decimal as D
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from acciones_ud.portfolio.application.report_scheduler import ReportScheduler
from acciones_ud.portfolio.domain.model import RawPosition
from tests.portfolio.unit.test_reports import reporting


def scheduler(service, source):
    return ReportScheduler(
        service,
        SimpleNamespace(
            daily_summary_investors=AsyncMock(return_value=[source.account.user_id]),
            monthly_report_investors=AsyncMock(return_value=[]),
        ),
        SimpleNamespace(last_closed_session=AsyncMock(return_value=date(2026, 6, 12))),
        SimpleNamespace(notify=AsyncMock(return_value=True)),
        service.clock,
    )


async def test_daily_empty_skipped_monthly_generated_and_period_uses_new_york():
    service, source, alpaca, repo = reporting()
    job = scheduler(service, source)
    now = datetime(2026, 6, 15, 12, tzinfo=UTC)
    await job.run_cycle(now)
    assert not repo.values
    job.preferences.monthly_report_investors.return_value = [source.account.user_id]
    await job.run_cycle(datetime(2026, 7, 1, 1, tzinfo=UTC))  # Still June in New York.
    report = next(iter(repo.values.values()))
    assert report.type == "monthly" and report.period.from_ == date(2026, 5, 1)


async def test_notification_only_retry_and_then_no_duplicates():
    service, source, alpaca, repo = reporting()
    alpaca.positions["private-account"] = [RawPosition("A", "NYSE", D(1), D(1), D(10), D(12))]
    job = scheduler(service, source)
    job.notifier.notify.side_effect = [RuntimeError("private-secret"), True]
    now = datetime(2026, 6, 15, 12, tzinfo=UTC)
    await job.run_cycle(now)
    report = next(iter(repo.values.values()))
    assert report.notified_at is None
    calls = alpaca.calls
    await job.run_cycle(now)
    assert len(repo.values) == 1 and alpaca.calls == calls
    assert repo.values[report.id].notified_at == now
    await job.run_cycle(now)
    assert job.notifier.notify.call_count == 2


async def test_failure_isolated_and_retried_without_secret_logs(caplog):
    service, source, alpaca, repo = reporting()
    alpaca.positions["private-account"] = [RawPosition("A", "NYSE", D(1), D(1), D(10), D(12))]
    job = scheduler(service, source)
    first, second = uuid4(), source.account.user_id
    job.preferences.daily_summary_investors.return_value = [first, second]
    build = service.builder.build

    async def sometimes_fails(user_id, period):
        if user_id == first:
            raise RuntimeError("private-secret")
        return await build(user_id, period)

    service.builder.build = sometimes_fails
    now = datetime(2026, 6, 15, 12, tzinfo=UTC)
    await job.run_cycle(now)
    assert len(repo.values) == 1
    assert "portfolio.report_failed" in caplog.text and "private-secret" not in caplog.text
    service.builder.build = build
    await job.run_cycle(now)
    assert len(repo.values) == 2
