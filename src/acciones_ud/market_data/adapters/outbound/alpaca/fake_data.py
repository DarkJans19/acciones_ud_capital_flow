"""Scriptable Alpaca Market Data double. Tests never reach the network."""

from datetime import datetime
from decimal import Decimal

from acciones_ud.market_data.domain.entities import Bar, BarsPage, LatestQuoteDoc, Snapshot


class FakeAlpacaData:
    def __init__(self) -> None:
        self.snapshot_value: Snapshot | None = None
        self.snapshots_value: dict[str, Snapshot] = {}
        self.bars_page = BarsPage()
        self.quote_value = LatestQuoteDoc()
        self.errors: dict[str, list[Exception | None]] = {}
        self.calls: list[str] = []

    def fail(self, method: str, error: Exception, times: int = 1) -> None:
        self.errors.setdefault(method, []).extend([error] * times)

    def _raise_scripted(self, method: str) -> None:
        self.calls.append(method)
        queue = self.errors.get(method)
        if queue:
            error = queue.pop(0)
            if error is not None:
                raise error

    async def snapshot(self, symbol: str) -> Snapshot:
        self._raise_scripted("snapshot")
        if self.snapshot_value is None:
            raise AssertionError("FakeAlpacaData.snapshot_value was not configured")
        return self.snapshot_value

    async def snapshots(self, symbols: list[str]) -> dict[str, Snapshot]:
        self._raise_scripted("snapshots")
        return {
            symbol: self.snapshots_value[symbol]
            for symbol in symbols
            if symbol in self.snapshots_value
        }

    async def bars(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        page_size: int,
        page_token: str | None,
    ) -> BarsPage:
        self._raise_scripted("bars")
        return self.bars_page

    async def latest_quote(self, symbol: str) -> LatestQuoteDoc:
        self._raise_scripted("latest_quote")
        return self.quote_value


def bar(day: str, close: str = "100") -> Bar:
    return Bar(
        timestamp=datetime.fromisoformat(day),
        open=Decimal(close),
        high=Decimal(close),
        low=Decimal(close),
        close=Decimal(close),
        volume=1000,
    )
