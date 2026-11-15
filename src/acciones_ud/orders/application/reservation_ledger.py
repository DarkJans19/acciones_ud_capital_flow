from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from acciones_ud.orders.domain.errors import InvalidTransitionError
from acciones_ud.orders.domain.model import Order, Reservation
from acciones_ud.orders.domain.ports import OrderWork
from acciones_ud.orders.domain.reservations import check_buy, check_sell, next_state


class ReservationLedger:
    """Each mutation belongs to the caller's investor-locked transaction."""

    async def active_usd(self, work: OrderWork, user_id: UUID) -> Decimal:
        return sum(
            (
                r.amount
                for r in await work.reservations.list(user_id=user_id, kind="usd", status="active")
            ),
            Decimal(0),
        )

    async def active_shares(self, work: OrderWork, user_id: UUID, symbol: str) -> Decimal:
        return sum(
            (
                r.amount
                for r in await work.reservations.list(
                    user_id=user_id, symbol=symbol, kind="shares", status="active"
                )
            ),
            Decimal(0),
        )

    async def reserve(
        self,
        work: OrderWork,
        order: Order,
        buying_power: Decimal,
        qty_available: Decimal,
        now: datetime,
    ) -> Reservation:
        if await work.reservations.get(order_id=order.id) is not None:
            raise InvalidTransitionError()
        await self._check(work, order, buying_power, qty_available, Decimal(0))
        reservation = Reservation(
            order.id,
            order.user_id,
            "usd" if order.side == "buy" else "shares",
            order.symbol,
            order.estimated_amount if order.side == "buy" else order.qty,
            "active",
            now,
        )
        if not await work.reservations.insert(reservation):
            raise InvalidTransitionError()
        return reservation

    async def adjust(
        self,
        work: OrderWork,
        order: Order,
        buying_power: Decimal,
        qty_available: Decimal,
        now: datetime,
    ) -> Reservation:
        own = await work.reservations.get(order_id=order.id)
        if own is None or own.status != "active":
            raise InvalidTransitionError()
        await self._check(work, order, buying_power, qty_available, own.amount)
        updated = replace(
            own, amount=order.estimated_amount if order.side == "buy" else order.qty, updated_at=now
        )
        await work.reservations.save(updated, status="active")
        return updated

    async def _check(
        self,
        work: OrderWork,
        order: Order,
        buying_power: Decimal,
        qty_available: Decimal,
        own: Decimal,
    ) -> None:
        if order.side == "buy":
            check_buy(
                order.estimated_amount,
                buying_power,
                await self.active_usd(work, order.user_id),
                own,
            )
        else:
            check_sell(
                order.qty,
                qty_available,
                await self.active_shares(work, order.user_id, order.symbol),
                own,
            )

    async def _move(
        self,
        work: OrderWork,
        order_id: UUID,
        target: Literal["transferred", "released"],
        now: datetime,
    ) -> None:
        stored = await work.reservations.get(order_id=order_id)
        if stored is None:
            raise InvalidTransitionError()
        state = next_state(stored.status, target)
        if stored.status != state:
            await work.reservations.save(
                replace(stored, status=state, updated_at=now), status=stored.status
            )

    async def transfer(self, work: OrderWork, order_id: UUID, now: datetime) -> None:
        await self._move(work, order_id, "transferred", now)

    async def release(self, work: OrderWork, order_id: UUID, now: datetime) -> None:
        await self._move(work, order_id, "released", now)
