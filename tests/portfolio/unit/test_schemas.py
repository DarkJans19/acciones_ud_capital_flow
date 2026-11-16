from datetime import date

from acciones_ud.portfolio.adapters.inbound.http.schemas.positions import PositionsResponse
from acciones_ud.portfolio.adapters.inbound.http.schemas.reports import ReportResponse
from acciones_ud.portfolio.domain.model import Period
from tests.portfolio.fakes import portfolio
from tests.portfolio.unit.test_reports import reporting


async def test_output_contracts_and_period_alias():
    ps, source, _ = portfolio()
    view = PositionsResponse.model_validate(await ps.positions(source.account.user_id))
    assert view.model_dump(mode="json")["totals"]["market_value"] == "0.00"
    service, source, _, _ = reporting()
    report = await service.create_on_demand(
        source.account.user_id, Period(date(2026, 1, 1), date(2026, 1, 31))
    )
    serialized = ReportResponse.model_validate(report).model_dump(mode="json", by_alias=True)
    assert serialized["period"] == {"from": "2026-01-01", "to": "2026-01-31"}
