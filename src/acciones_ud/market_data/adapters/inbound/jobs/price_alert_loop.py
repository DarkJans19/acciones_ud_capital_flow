"""RF-26: alert engine loop. One snapshot call per interval, conditional trigger."""

import asyncio
import logging
from decimal import Decimal

from acciones_ud.market_data.application.notifier import Notifier
from acciones_ud.market_data.domain.alerts import evaluate
from acciones_ud.market_data.domain.entities import PriceAlert, Recipient
from acciones_ud.market_data.domain.ports import (
    AlertWorkFactory,
    AlpacaDataPort,
    DirectoryFactory,
)
from acciones_ud.shared.domain.alpaca_errors import AlpacaError
from acciones_ud.shared.domain.clock import Clock

logger = logging.getLogger(__name__)


class PriceAlertLoop:
    def __init__(
        self,
        uow: AlertWorkFactory,
        data: AlpacaDataPort,
        directory: DirectoryFactory,
        notifier: Notifier,
        clock: Clock,
        interval_seconds: int,
    ) -> None:
        self.uow = uow
        self.data = data
        self.directory = directory
        self.notifier = notifier
        self.clock = clock
        self.interval_seconds = interval_seconds
        self._task: asyncio.Task[None] | None = None

    async def run_once(self) -> None:
        async with self.uow() as work:
            grouped = await work.alerts.active_grouped()
        if not grouped:
            return
        try:
            quotes = await self.data.snapshots(sorted(grouped))
        except AlpacaError:
            return
        triggered: list[tuple[PriceAlert, Decimal]] = []
        for symbol, alerts in grouped.items():
            quote = quotes.get(symbol)
            price = None if quote is None else quote.last_trade_price
            if price is None:
                continue
            for alert in alerts:
                pending = await self._evaluate(alert, price)
                if pending is not None:
                    triggered.append((pending, price))
        for alert, price in triggered:
            if alert.user_id is None:
                continue
            recipients = await self._recipients("price_changes")
            owner = [
                recipient
                for recipient in recipients
                if recipient.user_id == alert.user_id
            ] or [Recipient(user_id=alert.user_id, channels=frozenset({"in_app"}))]
            await self.notifier.notify(
                owner,
                "price_changes",
                {
                    "alert_id": str(alert.id),
                    "symbol": alert.symbol,
                    "comparator": alert.comparator.value,
                    "threshold": str(alert.threshold),
                    "observed_price": str(price),
                    "observed_at": self.clock.now().isoformat(),
                },
            )

    async def _recipients(self, event_type: str) -> list[Recipient]:
        async with self.directory() as directory:
            return await directory.recipients(event_type)

    async def _evaluate(self, alert: PriceAlert, price: Decimal) -> PriceAlert | None:
        async with self.uow() as work:
            current = await work.alerts.lock_active(alert.id)
            if current is None:
                return None
            _, _, triggered = evaluate(
                current.status,
                current.comparator,
                current.threshold,
                current.last_evaluated_price,
                price,
            )
            if not triggered:
                await work.alerts.record_price(alert.id, price)
                return None
            if await work.alerts.trigger(alert.id, price, self.clock.now()):
                return current
            return None

    async def run(self) -> None:
        while True:
            try:
                await self.run_once()
            except Exception:
                logger.exception("price alert evaluation failed")
            await asyncio.sleep(self.interval_seconds)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
