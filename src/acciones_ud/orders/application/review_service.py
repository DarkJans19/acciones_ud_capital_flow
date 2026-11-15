from uuid import UUID, uuid4

from acciones_ud.orders.application.context import OrderContext, change
from acciones_ud.orders.application.order_submitter import OrderSubmitter
from acciones_ud.orders.domain.errors import InvalidTransitionError, OrderDomainError, not_found
from acciones_ud.orders.domain.model import Order, OrderStatus, ReviewComment
from acciones_ud.orders.domain.ports import OrderWork
from acciones_ud.shared.domain.errors import ErrorCode


class ReviewService:
    def __init__(self, context: OrderContext, submitter: OrderSubmitter) -> None:
        self.ctx, self.submitter = context, submitter

    async def route_new_order(self, work: OrderWork, order: Order, broker_id: UUID) -> Order:
        return await change(
            work,
            order,
            OrderStatus.IN_REVIEW,
            "broker_review",
            self.ctx.clock.now(),
            metadata={"reviewing_broker_id": str(broker_id)},
        )

    async def queue(self, broker_id: UUID) -> list[Order]:
        linked = set(await self.ctx.brokers.linked_investors(broker_id))
        if not linked:
            return []
        async with self.ctx.uow() as work:
            return [
                order
                for order in await work.orders.list(status=OrderStatus.IN_REVIEW)
                if order.user_id in linked and order.status_cause == "broker_review"
            ]

    async def _linked_order(self, broker_id: UUID, order_id: UUID) -> Order:
        async with self.ctx.uow() as work:
            order = await work.orders.get(id=order_id)
        if order is None or not await self.ctx.brokers.is_linked(broker_id, order.user_id):
            raise not_found()
        return order

    async def return_for_changes(self, broker_id: UUID, order_id: UUID, comment: str) -> Order:
        if not 1 <= len(comment.strip()) <= 500:
            raise OrderDomainError(
                422, ErrorCode.VALIDATION_ERROR, "Invalid field: comment", {"fields": ["comment"]}
            )
        order = await self._linked_order(broker_id, order_id)
        async with self.ctx.uow() as work:
            await work.lock_user(order.user_id)
            current = await work.orders.get(id=order.id)
            if current is None or not await self.ctx.brokers.is_linked(broker_id, current.user_id):
                raise not_found()
            if current.status != OrderStatus.IN_REVIEW or current.status_cause != "broker_review":
                raise InvalidTransitionError()
            now = self.ctx.clock.now()
            order = await change(
                work,
                current,
                OrderStatus.PENDING,
                "returned_for_changes",
                now,
                actor_type="broker",
                actor_id=broker_id,
                returned_for_changes=True,
            )
            await work.comments.insert(ReviewComment(uuid4(), order.id, broker_id, comment, now))
        await self.ctx.notify(order, "returned_for_changes")
        return order

    async def approve(self, broker_id: UUID, order_id: UUID) -> Order:
        order = await self._linked_order(broker_id, order_id)
        async with self.ctx.uow() as work:
            await work.lock_user(order.user_id)
            current = await work.orders.get(id=order.id)
            if current is None or not await self.ctx.brokers.is_linked(broker_id, current.user_id):
                raise not_found()
            if current.status != OrderStatus.IN_REVIEW or current.status_cause != "broker_review":
                raise InvalidTransitionError()
            now = self.ctx.clock.now()
            order = await change(
                work,
                current,
                OrderStatus.BROKER_SIGNED,
                "broker_approved",
                now,
                actor_type="broker",
                actor_id=broker_id,
                broker_id=broker_id,
                broker_signed_at=now,
                returned_for_changes=False,
            )
        return await self.submitter.submit(order.id, waited=True)
