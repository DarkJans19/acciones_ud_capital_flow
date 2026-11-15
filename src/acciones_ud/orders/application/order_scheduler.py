import logging

from acciones_ud.orders.application.context import OrderContext
from acciones_ud.orders.application.order_service import OrderService

logger = logging.getLogger(__name__)


class OrderScheduler:
    def __init__(self, context: OrderContext, service: OrderService) -> None:
        self.ctx, self.service = context, service

    async def run_once(self) -> None:
        # Expire a missed DAY session before considering the next day's open market.
        await self.service.expire_stale()
        async with self.ctx.uow() as work:
            orders = await work.orders.due(self.ctx.clock.now())
        for order in orders:
            try:
                if await self.ctx.sessions.is_open(order.exchange, self.ctx.clock.now()):
                    await self.service.submitter.submit(order.id, waited=True)
            except Exception:
                logger.warning(
                    "Scheduled order could not proceed", extra={"order_id": str(order.id)}
                )
