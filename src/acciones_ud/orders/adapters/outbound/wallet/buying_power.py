import asyncio
from decimal import Decimal, InvalidOperation

from acciones_ud.shared.domain.alpaca_errors import AlpacaError
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from acciones_ud.wallet.domain.ports import AlpacaFundingPort


class WalletBuyingPowerAdapter:
    def __init__(self, funding: AlpacaFundingPort) -> None:
        self.funding = funding

    async def buying_power(self, alpaca_account_id: str) -> Decimal:
        try:
            async with asyncio.timeout(4):
                raw = await self.funding.get_trading_account(alpaca_account_id, timeout_s=4)
            amount = Decimal(raw["buying_power"])
            if not amount.is_finite():
                raise ValueError()
            return amount
        except (AlpacaError, TimeoutError, InvalidOperation, ValueError, KeyError, TypeError):
            raise AppError(
                502, ErrorCode.ALPACA_UNAVAILABLE, "Buying power is unavailable."
            ) from None
