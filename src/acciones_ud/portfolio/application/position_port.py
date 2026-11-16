from decimal import Decimal

from acciones_ud.portfolio.domain.ports import AlpacaPositionPort


class PortfolioPositionPort:
    def __init__(self, positions: AlpacaPositionPort) -> None:
        self.positions = positions

    async def qty_available(self, alpaca_account_id: str, symbol: str) -> Decimal:
        position = await self.positions.get(alpaca_account_id, symbol)
        return position.qty_available if position else Decimal(0)
