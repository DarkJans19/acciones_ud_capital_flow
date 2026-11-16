"""Additive MOD-06 contract: RF-20/RF-30, no additional HTTP entry point."""

from uuid import UUID

from acciones_ud.brokers.domain.ports import (
    OrderCreated,
    OrderFilters,
    OrderRejected,
    ProposalOrderCommand,
)
from acciones_ud.orders.application.order_service import OrderService
from acciones_ud.orders.domain.idempotency import request_hash
from acciones_ud.orders.domain.model import OrderRequest, Raw
from acciones_ud.shared.domain.errors import AppError, ErrorCode


def request_from_proposal(command: ProposalOrderCommand) -> OrderRequest:
    return OrderRequest(
        command.symbol,
        command.side,
        command.qty,
        command.type,
        limit_price=command.limit_price,
        order_class="simple",
        time_in_force="day",
        schedule_if_closed=True,
        confirmed=True,
    )


class ProposalOrders:
    def __init__(self, service: OrderService) -> None:
        self.service = service

    async def create(self, command: ProposalOrderCommand) -> OrderCreated | OrderRejected:
        return await self.create_from_proposal(command)

    async def create_from_proposal(
        self, command: ProposalOrderCommand
    ) -> OrderCreated | OrderRejected:
        request = request_from_proposal(command)
        key = f"proposal:{command.proposal_id}"
        try:
            order = await self.service._create(
                command.investor_id,
                request,
                key,
                signature=command.broker_id,
                proposal_reason=key,
            )
        except AppError as exc:
            if exc.code == ErrorCode.IDEMPOTENCY_CONFLICT:
                return OrderRejected(exc.code)
            # A provider failure after commit belongs to the Order's lifecycle (D2).
            async with self.service.ctx.uow() as work:
                persisted = await work.keys.get(user_id=command.investor_id, idempotency_key=key)
            if persisted:
                return OrderCreated(persisted.order_id)
            if exc.status >= 500 or exc.code.startswith("DATABASE_"):
                raise
            return OrderRejected(exc.code)
        return OrderCreated(order.id)


class OrderQueries:
    def __init__(self, service: OrderService) -> None:
        self.service = service

    async def list_for_investor(self, investor_id: UUID, filters: OrderFilters) -> Raw:
        return await self.service.list(
            investor_id,
            filters.status,
            filters.symbol,
            filters.start,
            filters.end,
            filters.page_size,
            filters.cursor,
        )

    async def find_by_idempotency_key(
        self, investor_id: UUID, key: str, expected: ProposalOrderCommand | None = None
    ) -> UUID | None:
        async with self.service.ctx.uow() as work:
            entry = await work.keys.get(user_id=investor_id, idempotency_key=key)
        if entry is None or (
            expected is not None
            and entry.request_hash != request_hash(request_from_proposal(expected))
        ):
            return None
        return entry.order_id
