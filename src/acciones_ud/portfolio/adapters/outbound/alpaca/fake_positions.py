from acciones_ud.portfolio.domain.model import RawPosition


class FakePositions:
    def __init__(self) -> None:
        self.positions: dict[str, list[RawPosition]] = {}
        self.calls = 0
        self.error: Exception | None = None

    async def list(self, alpaca_account_id: str) -> list[RawPosition]:
        self.calls += 1
        if self.error:
            raise self.error
        return list(self.positions.get(alpaca_account_id, []))

    async def get(self, alpaca_account_id: str, symbol: str) -> RawPosition | None:
        return next((p for p in await self.list(alpaca_account_id) if p.symbol == symbol), None)
