from datetime import UTC, datetime, timedelta

import pytest

from acciones_ud.market_data.adapters.outbound.alpaca.fake_broker import (
    FakeAlpacaBrokerMarket,
    instrument,
)
from acciones_ud.market_data.application.asset_detail import AssetDetailService
from acciones_ud.market_data.application.catalog import CatalogService
from acciones_ud.shared.domain.alpaca_errors import AlpacaNotFound, AlpacaUnavailable
from acciones_ud.shared.domain.errors import AppError
from tests.support.clock import FakeClock
from tests.support.market_fakes import MemoryInstruments, catalog_uow


def build(
    repository: MemoryInstruments,
    broker: FakeAlpacaBrokerMarket,
    now: datetime,
) -> CatalogService:
    return CatalogService(catalog_uow(repository), broker, FakeClock(now), 24)


async def test_empty_catalog_reloads_from_alpaca() -> None:
    now = datetime(2026, 1, 2, tzinfo=UTC)
    repository = MemoryInstruments()
    broker = FakeAlpacaBrokerMarket()
    broker.assets = [instrument("AAPL"), instrument("MSFT")]
    service = build(repository, broker, now)

    await service.ensure_fresh()

    assert repository.items["AAPL"].listed
    assert repository.last_reload == now


async def test_failed_reload_uses_cache_when_populated() -> None:
    now = datetime(2026, 1, 2, tzinfo=UTC)
    stale = now - timedelta(hours=48)
    cached = instrument("AAPL")
    repository = MemoryInstruments([cached], last_reload=stale)
    broker = FakeAlpacaBrokerMarket()
    broker.fail("list_assets", AlpacaUnavailable())
    service = build(repository, broker, now)

    await service.ensure_fresh()

    assert repository.items["AAPL"] == cached
    assert repository.last_reload == stale


async def test_failed_reload_without_cache_raises_502() -> None:
    now = datetime(2026, 1, 2, tzinfo=UTC)
    broker = FakeAlpacaBrokerMarket()
    broker.fail("list_assets", AlpacaUnavailable())
    service = build(MemoryInstruments(), broker, now)

    with pytest.raises(AppError) as error:
        await service.ensure_fresh()
    assert error.value.status == 502


async def test_asset_detail_reads_alpaca_and_upserts() -> None:
    now = datetime(2026, 1, 2, tzinfo=UTC)
    repository = MemoryInstruments()
    broker = FakeAlpacaBrokerMarket()
    broker.asset = instrument("AAPL", name="Apple Inc.")
    service = AssetDetailService(catalog_uow(repository), broker, FakeClock(now))

    detail = await service.detail(" aapl ")

    assert detail.symbol == "AAPL"
    assert repository.items["AAPL"].name == "Apple Inc."


async def test_asset_detail_unknown_symbol_writes_nothing() -> None:
    now = datetime(2026, 1, 2, tzinfo=UTC)
    repository = MemoryInstruments()
    broker = FakeAlpacaBrokerMarket()
    broker.fail("get_asset", AlpacaNotFound())
    service = AssetDetailService(catalog_uow(repository), broker, FakeClock(now))

    with pytest.raises(AppError) as error:
        await service.detail("NOPE")
    assert error.value.status == 404
    assert error.value.code == "SYMBOL_NOT_FOUND"
    assert repository.upserts == 0
