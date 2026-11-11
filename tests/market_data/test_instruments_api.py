from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from acciones_ud.config.settings import Settings
from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.main import create_app
from acciones_ud.market_data.adapters.outbound.alpaca.fake_broker import (
    FakeAlpacaBrokerMarket,
    instrument,
)
from acciones_ud.market_data.application.asset_detail import AssetDetailService
from acciones_ud.market_data.application.catalog import CatalogService
from acciones_ud.market_data.application.exchanges import ExchangesService
from acciones_ud.market_data.application.search import SearchService
from acciones_ud.shared.domain.alpaca_errors import AlpacaNotFound
from tests.support.clock import FakeClock
from tests.support.market_fakes import MemoryInstruments, catalog_uow

NOW = datetime(2026, 1, 2, tzinfo=UTC)


def build_app(
    api_settings: Settings, repository: MemoryInstruments
) -> tuple[object, FakeAlpacaBrokerMarket]:
    app = create_app(api_settings)
    broker = FakeAlpacaBrokerMarket()
    user = CurrentUser(
        uuid4(),
        uuid4(),
        "ana@example.com",
        "active",
        True,
        frozenset({"investor"}),
        frozenset({"market:read"}),
    )
    app.dependency_overrides[get_current_user] = lambda: user
    catalog = CatalogService(catalog_uow(repository), broker, FakeClock(NOW), 24)
    app.state.catalog_service = catalog
    app.state.search_service = SearchService(catalog_uow(repository), catalog)
    app.state.exchanges_service = ExchangesService(catalog_uow(repository), catalog)
    app.state.asset_detail_service = AssetDetailService(
        catalog_uow(repository), broker, FakeClock(NOW)
    )
    return app, broker


@pytest.fixture
def repository() -> MemoryInstruments:
    return MemoryInstruments(
        [
            instrument("AAPL", name="Apple Inc.", exchange="NASDAQ", sector="Technology"),
            instrument("MSFT", name="Microsoft Corporation", exchange="NASDAQ"),
            instrument("XOM", name="Exxon Mobil", exchange="NYSE", tradable=False),
        ],
        last_reload=NOW,
    )


def test_requires_authentication(api_settings: Settings) -> None:
    client = TestClient(create_app(api_settings))
    assert client.get("/api/v1/instruments/search", params={"q": "AA"}).status_code == 401


def test_search_returns_paged_results(
    api_settings: Settings, repository: MemoryInstruments
) -> None:
    app, _ = build_app(api_settings, repository)
    response = TestClient(app).get("/api/v1/instruments/search", params={"q": "AA"})
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 50
    assert body["total"] == 1
    assert body["results"][0]["symbol"] == "AAPL"
    assert body["results"][0]["classification"] == "tradable"


def test_search_classification_filter(
    api_settings: Settings, repository: MemoryInstruments
) -> None:
    app, _ = build_app(api_settings, repository)
    response = TestClient(app).get(
        "/api/v1/instruments/search", params={"q": "X", "classification": "view_only"}
    )
    assert response.status_code == 200
    assert [item["symbol"] for item in response.json()["results"]] == ["XOM"]


def test_blank_query_is_rejected(
    api_settings: Settings, repository: MemoryInstruments
) -> None:
    app, _ = build_app(api_settings, repository)
    response = TestClient(app).get("/api/v1/instruments/search", params={"q": "   "})
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_markets_list(api_settings: Settings, repository: MemoryInstruments) -> None:
    app, _ = build_app(api_settings, repository)
    response = TestClient(app).get("/api/v1/markets")
    assert response.status_code == 200
    assert response.json() == [
        {"code": "NASDAQ", "name": "NASDAQ"},
        {"code": "NYSE", "name": "NYSE"},
    ]


def test_symbol_with_slash_reaches_the_validator(
    api_settings: Settings, repository: MemoryInstruments
) -> None:
    app, broker = build_app(api_settings, repository)
    broker.fail("get_asset", AlpacaNotFound())
    response = TestClient(app).get("/api/v1/instruments/BRK/B")
    assert response.status_code == 404
    assert response.json()["code"] == "SYMBOL_NOT_FOUND"
    assert broker.calls == ["get_asset"]


def test_invalid_symbol_is_rejected_before_alpaca(
    api_settings: Settings, repository: MemoryInstruments
) -> None:
    app, broker = build_app(api_settings, repository)
    response = TestClient(app).get("/api/v1/instruments/BAD$X")
    assert response.status_code == 422
    assert broker.calls == []
