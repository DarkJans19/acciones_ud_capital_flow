"""RF-26: price alert use cases."""

from decimal import Decimal
from uuid import UUID

from acciones_ud.market_data.domain.alerts import COMPARATORS, validate_threshold
from acciones_ud.market_data.domain.entities import AlertStatus, PriceAlert
from acciones_ud.market_data.domain.ports import AlertWorkFactory
from acciones_ud.market_data.domain.symbols import validate_symbol
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import AppError, ErrorCode


def _missing() -> AppError:
    return AppError(
        404, ErrorCode.NOT_FOUND, "Price alert not found.", {"resource": "alert"}
    )


class AlertService:
    def __init__(self, uow: AlertWorkFactory, clock: Clock) -> None:
        self.uow = uow
        self.clock = clock

    async def list_alerts(self, user_id: UUID) -> list[PriceAlert]:
        async with self.uow() as work:
            return await work.alerts.list_all(user_id)

    async def create(
        self, user_id: UUID, raw_symbol: str, comparator: str, threshold: Decimal
    ) -> PriceAlert:
        symbol = validate_symbol(raw_symbol)
        if comparator not in COMPARATORS:
            raise AppError(422, ErrorCode.VALIDATION_ERROR, "Invalid field: comparator")
        validate_threshold(threshold)
        async with self.uow() as work:
            if not await work.instruments.exists(symbol):
                raise AppError(404, ErrorCode.SYMBOL_NOT_FOUND, "Symbol not found.")
            return await work.alerts.create(
                user_id, symbol, comparator, threshold, self.clock.now()
            )

    async def set_status(
        self, user_id: UUID, alert_id: UUID, status: AlertStatus
    ) -> PriceAlert:
        async with self.uow() as work:
            alert = await work.alerts.set_status(user_id, alert_id, status.value)
            if alert is None:
                raise _missing()
            return alert

    async def delete(self, user_id: UUID, alert_id: UUID) -> None:
        async with self.uow() as work:
            if not await work.alerts.delete(user_id, alert_id):
                raise _missing()
