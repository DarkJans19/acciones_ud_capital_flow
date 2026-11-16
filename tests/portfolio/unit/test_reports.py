from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal as D
from uuid import uuid4

import pytest

from acciones_ud.portfolio.adapters.outbound.brokers.null_broker_client import NullBrokerClient
from acciones_ud.portfolio.application.report_builder import ReportBuilder
from acciones_ud.portfolio.application.report_service import ReportService
from acciones_ud.portfolio.domain.model import Period, RawPosition
from acciones_ud.shared.domain.alpaca_errors import AlpacaUnavailable
from acciones_ud.shared.domain.errors import AppError
from tests.portfolio.fakes import Reports, portfolio
from tests.portfolio.property.test_pnl import records


def reporting():
    ps, source, alpaca = portfolio()
    repo = Reports()
    builder = ReportBuilder(ps, source, ps.commissions)
    return ReportService(builder, repo.work, source, ps.clock), source, alpaca, repo


async def test_null_broker_report_is_empty_with_zero_totals():
    service, source, alpaca, repo = reporting()
    service.brokers = NullBrokerClient()
    report = await service.create_broker(uuid4(), Period(date(2026, 1, 1), date(2026, 1, 31)))
    assert report.content["clients"] == []
    assert report.content["totals"]["volume"] == "0.00"
    assert report.content["totals"]["commissions_attributed"] == "0.00"
    assert report.content["totals"]["profitability"] is None
    assert len(repo.values) == 1 and alpaca.calls == 0


async def test_report_replays_prior_buys_but_sums_only_period_sales():
    service, source, alpaca, repo = reporting()
    owner = source.account.user_id
    trades = records([("buy", D(10), D(10)), ("sell", D(2), D(12)), ("sell", D(3), D(15))])
    source.rows = [
        replace(e, user_id=owner, executed_at=datetime(2026, month, 2, tzinfo=UTC))
        for e, month in zip(trades, [1, 2, 3], strict=True)
    ]
    alpaca.positions["private-account"] = [RawPosition("A", "NYSE", D(5), D(5), D(10), D(16))]
    report = await service.create_on_demand(owner, Period(date(2026, 3, 1), date(2026, 3, 31)))
    assert report.content["realized_pnl"] == {"gross": "15.00", "net": "14.10"}
    assert report.content["volume"] == "45.00"
    assert report.content["profitability"] == "56.25"
    assert report.content["asset_summary"]["position_count"] == 1
    assert len(report.content["executions"]) == 1
    report.content["volume"] = "tampered"
    assert (await service.get(owner, report.id)).content["volume"] == "45.00"
    with pytest.raises(AppError) as caught:
        await service.get(uuid4(), report.id)
    assert caught.value.code == "NOT_FOUND"


async def test_broker_attribution_uses_signer_and_alpaca_failure_stores_nothing():
    service, source, alpaca, repo = reporting()
    owner, broker = source.account.user_id, uuid4()
    source.links.add((broker, owner))
    source.rows = [
        replace(e, user_id=owner, signed_by_broker_id=signer)
        for e, signer in zip(
            records([("buy", D(1), D(10)), ("buy", D(1), D(10))]), [broker, uuid4()], strict=True
        )
    ]
    period = Period(date(2025, 12, 31), date(2026, 1, 31))
    report = await service.create_broker(broker, period)
    assert report.content["totals"]["commissions_attributed"] == "0.20"
    assert report.content["totals"]["commissions"] == "0.40"
    alpaca.error = AlpacaUnavailable()
    with pytest.raises(AppError) as caught:
        await service.create_on_demand(owner, period)
    assert caught.value.status == 502 and len(repo.values) == 1
