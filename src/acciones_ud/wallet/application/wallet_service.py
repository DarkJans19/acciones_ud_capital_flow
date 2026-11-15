import asyncio
import logging
from datetime import datetime
from uuid import UUID

from acciones_ud.shared.domain.alpaca_errors import AlpacaError, to_app_error
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from acciones_ud.wallet.application.dtos import period
from acciones_ud.wallet.domain.model import ActivityPage, ActivityQuery, BalanceView, LinkedAccount
from acciones_ud.wallet.domain.money import exact_amount
from acciones_ud.wallet.domain.ports import (
    AccountStatusWriter,
    AlpacaFundingPort,
    WalletWorkFactory,
)

logger = logging.getLogger(__name__)


class WalletService:
    def __init__(
        self,
        uow: WalletWorkFactory,
        alpaca: AlpacaFundingPort,
        clock: Clock,
        status_writer: AccountStatusWriter,
    ) -> None:
        self.uow, self.alpaca, self.clock, self.status_writer = uow, alpaca, clock, status_writer

    async def linked(self, user_id: UUID) -> LinkedAccount:
        async with self.uow() as work:
            linked = await work.accounts.get(user_id)
        if linked is None:
            raise AppError(409, ErrorCode.WALLET_ACCOUNT_REQUIRED, "Linked account required.")
        return linked

    async def get_balances(self, user_id: UUID) -> BalanceView:
        linked, now = await self.linked(user_id), self.clock.now()
        names = (
            "cash",
            "cash_withdrawable",
            "buying_power",
            "equity",
            "portfolio_value",
            "long_market_value",
        )
        try:
            async with asyncio.timeout(5):
                raw = await self.alpaca.get_trading_account(linked.alpaca_account_id, timeout_s=5)
        except (AlpacaError, TimeoutError):
            return BalanceView(linked.status, "USD", None, None, None, None, None, None, now, True)
        status = str(raw["status"])
        if status != linked.status:
            try:
                async with asyncio.timeout(5):
                    await self.status_writer.update_status(user_id, status, now)
            except (AppError, TimeoutError, OSError):
                logger.warning("Account status could not be stored")
        currency = raw.get("currency")
        if not currency:
            logger.warning("Trading account currency absent; using USD")
        amounts = {name: exact_amount(raw.get(name)) for name in names}
        return BalanceView(
            status,
            currency or "USD",
            amounts["cash"],
            amounts["cash_withdrawable"],
            amounts["buying_power"],
            amounts["equity"],
            amounts["portfolio_value"],
            amounts["long_market_value"],
            now,
            False,
        )

    async def get_currencies(self, user_id: UUID) -> dict[str, object]:
        linked = await self.linked(user_id)
        try:
            raw = await self.alpaca.get_trading_account(linked.alpaca_account_id, timeout_s=5)
        except AlpacaError as exc:
            raise to_app_error(exc) from None
        return {"currencies": [raw.get("currency") or "USD"], "conversion_supported": False}

    async def list_activities(
        self,
        user_id: UUID,
        start: datetime | None = None,
        end: datetime | None = None,
        types: tuple[str, ...] = (),
        page_size: int = 50,
        cursor: str | None = None,
    ) -> ActivityPage:
        from acciones_ud.wallet.application.dtos import invalid

        if not 1 <= page_size <= 100:
            raise invalid("page_size")
        start, end = period(self.clock.now(), start, end)
        linked = await self.linked(user_id)
        try:
            page = await self.alpaca.list_activities(
                ActivityQuery(linked.alpaca_account_id, start, end, types, page_size, cursor)
            )
        except AlpacaError as exc:
            raise to_app_error(exc) from None
        return ActivityPage(
            [a for a in page.items if a.type not in {"FX", "FXC", "FX_CONVERSION"}],
            page.next_cursor,
        )
