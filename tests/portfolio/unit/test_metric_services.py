from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

from acciones_ud.portfolio.application.risk_profile_service import RiskProfileService
from acciones_ud.portfolio.application.statistics_service import StatisticsService
from acciones_ud.portfolio.domain.model import Period
from tests.portfolio.fakes import portfolio


async def test_empty_statistics_without_linked_account():
    service, source, _ = portfolio()
    owner = source.account.user_id
    source.account = None
    stats = await StatisticsService(source, source).statistics(
        owner, Period(date(2026, 1, 1), date(2026, 1, 31))
    )
    assert stats.execution_count == 0 and stats.volume == Decimal("0.00")
    assert stats.by_sector == []


async def test_empty_risk_and_missing_equity():
    service, source, _ = portfolio()
    risk = RiskProfileService(
        service,
        source,
        source,
        SimpleNamespace(equity=AsyncMock(return_value=None)),
        service.clock,
        90,
    )
    result = await risk.profile(source.account.user_id)
    assert result.equity_unavailable and result.classification == "insufficient_data"
    assert result.risk_score is None and result.metrics["asset_distribution"] == {}
