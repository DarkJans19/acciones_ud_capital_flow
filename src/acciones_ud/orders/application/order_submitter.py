import asyncio
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from time import monotonic
from uuid import UUID, uuid4

from acciones_ud.orders.application.context import OrderContext, change, request_from
from acciones_ud.orders.application.reservation_ledger import ReservationLedger
from acciones_ud.orders.domain.errors import (
    AlpacaRejectedError,
    OrderDomainError,
    OrderSubmissionNotReceived,
    OrderSubmissionUnknown,
    not_found,
)
from acciones_ud.orders.domain.model import Order, OrderEvent, Raw, ReauthorizationRequest
from acciones_ud.orders.domain.model import OrderStatus as S
from acciones_ud.orders.domain.ports import OrderWork
from acciones_ud.orders.domain.reauthorization import requires_reauthorization
from acciones_ud.shared.domain.alpaca_errors import AlpacaError
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from acciones_ud.shared.domain.trading import CommissionTerms


class OrderSubmitter:
    def __init__(self, context: OrderContext) -> None:
        self.ctx, self.ledger = context, ReservationLedger()

    async def submit(self, order_id: UUID, waited: bool) -> Order:
        async with self.ctx.uow() as work:
            order = await work.orders.get(id=order_id)
        if order is None:
            raise not_found()
        if (
            order.status not in {S.PENDING, S.BROKER_SIGNED}
            or order.submit_attempted_at is not None
        ):
            return order
        try:
            await self.ctx.check_gate(order.user_id, order.exchange)
        except AppError as exc:
            if exc.code in {ErrorCode.TRADING_HALTED, ErrorCode.ACCOUNT_TRADING_RESTRICTED}:
                return await self._defer(order, exc.code.value.lower())
            raise
        if not await self.ctx.sessions.is_open(order.exchange, self.ctx.clock.now()):
            session = await self.ctx.sessions.next_open(order.exchange, self.ctx.clock.now())
            async with self.ctx.uow() as work:
                await work.lock_user(order.user_id)
                current = await work.orders.get(id=order.id)
                if current is None or current.status not in {S.PENDING, S.BROKER_SIGNED}:
                    return current or order
                order = replace(
                    current,
                    scheduled_for=session.opens_at,
                    scheduled_session_end=session.closes_at,
                    updated_at=self.ctx.clock.now(),
                )
                await work.orders.save(order, status=current.status)
            await self.ctx.notify(order, "scheduled", scheduled_for=session.opens_at.isoformat())
            return order
        prepared = None
        if waited:
            try:
                prepared = await self.ctx.prepare(
                    order.user_id,
                    request_from(order),
                    authorize=False,
                    check_session=False,
                    terms=CommissionTerms(
                        order.fee_version_id,
                        order.commission_rate_pct
                        if order.commission_rate_pct is not None
                        else self.ctx.config.commission_rate * 100,
                        order.platform_share_pct
                        if order.platform_share_pct is not None
                        else Decimal("60.00"),
                    ),
                )
            except AppError as exc:
                if exc.code in {ErrorCode.TRADING_HALTED, ErrorCode.ACCOUNT_TRADING_RESTRICTED}:
                    return await self._defer(order, exc.code.value.lower())
                if exc.code not in {
                    ErrorCode.ORDER_ACCOUNT_NOT_ACTIVE,
                    ErrorCode.ASSET_NOT_TRADABLE,
                    ErrorCode.VALIDATION_ERROR,
                }:
                    raise
                return await self._reject_waiting(order, str(exc.code))
        held = False
        try:
            async with self.ctx.uow() as work:
                await work.lock_user(order.user_id)
                current = await work.orders.get(id=order.id)
                if current is None:
                    raise not_found()
                if (
                    current.status not in {S.PENDING, S.BROKER_SIGNED}
                    or current.submit_attempted_at
                ):
                    return current
                order = current
                if prepared is not None:
                    pending = await work.reauthorizations.get(order_id=order.id, decision=None)
                    held = pending is not None or requires_reauthorization(
                        order.type,
                        waited,
                        order.reference_price,
                        prepared.reference_price,
                        self.ctx.config.reauth_deviation_pct,
                    )
                    candidate = (
                        order
                        if held
                        else replace(
                            order,
                            reference_price=prepared.reference_price,
                            estimated_amount=prepared.amount,
                        )
                    )
                    await self.ledger.adjust(
                        work,
                        candidate,
                        prepared.buying_power,
                        prepared.qty_available,
                        self.ctx.clock.now(),
                    )
                    if held:
                        if pending is None:
                            pending = ReauthorizationRequest(
                                uuid4(),
                                order.id,
                                order.reference_price,
                                prepared.reference_price,
                                self.ctx.clock.now()
                                + timedelta(minutes=self.ctx.config.reauth_window_minutes),
                                resume_status=order.status,
                            )
                            await work.reauthorizations.insert(pending)
                        order = await change(
                            work, order, S.HELD, "price_changed", self.ctx.clock.now()
                        )
                    else:
                        order = candidate
                if not held:
                    order = await self.stage(work, order)
        except OrderDomainError as exc:
            if exc.code not in {
                ErrorCode.INSUFFICIENT_BUYING_POWER,
                ErrorCode.INSUFFICIENT_POSITION,
            }:
                raise
            return await self._reject_waiting(order, str(exc.code))
        if held:
            await self.ctx.notify(order, "price_changed")
            return order
        return await self._dispatch(order)

    async def _defer(self, order: Order, cause: str) -> Order:
        now, notify = self.ctx.clock.now(), False
        window = (
            await self.ctx.sessions.current_window(order.exchange, now)
            if order.scheduled_session_end is None
            else None
        )
        async with self.ctx.uow() as work:
            await work.lock_user(order.user_id)
            current = await work.orders.get(id=order.id)
            if (
                current is None
                or current.status not in {S.PENDING, S.BROKER_SIGNED}
                or current.submit_attempted_at is not None
            ):
                return current or order
            events = await work.events.list(order_id=order.id)
            notify = not any(e.metadata.get("deferred_by") == cause for e in events)
            order = replace(
                current,
                scheduled_for=current.scheduled_for or now,
                updated_at=now,
                scheduled_session_end=current.scheduled_session_end
                or (window.closes_at if window else None),
            )
            await work.orders.save(order, status=current.status)
            if notify:
                await work.events.insert(
                    OrderEvent(
                        uuid4(),
                        order.id,
                        order.status,
                        order.status,
                        cause,
                        "system",
                        None,
                        now,
                        {"deferred_by": cause},
                    )
                )
        if notify:
            await self.ctx.notify(order, cause)
        return order

    async def stage(self, work: OrderWork, order: Order) -> Order:
        return await change(
            work,
            order,
            S.SUBMITTED,
            "submission_started",
            self.ctx.clock.now(),
            submit_attempted_at=self.ctx.clock.now(),
        )

    async def _dispatch(self, order: Order) -> Order:
        # Only the transaction that wins stage() calls this method, after commit (D1).
        started = monotonic()
        try:
            async with asyncio.timeout(self.ctx.config.submit_timeout_seconds):
                raw = await self.ctx.alpaca.create(
                    order.alpaca_account_id,
                    self._payload(order),
                    self.ctx.config.submit_timeout_seconds,
                )
        except (TimeoutError, OrderSubmissionUnknown) as exc:
            if not isinstance(exc, OrderSubmissionUnknown) or not exc.server_error:
                return order
            try:
                async with asyncio.timeout(max(0.001, 5 - (monotonic() - started))):
                    found = await self.ctx.alpaca.get_by_client_order_id(
                        order.alpaca_account_id, order.client_order_id
                    )
            except (AlpacaError, TimeoutError):
                return order
            if found is None:
                return await self._failure(order, OrderSubmissionNotReceived(), S.FAILED)
            raw = found
        except AlpacaRejectedError as exc:
            return await self._failure(order, exc, S.REJECTED)
        except OrderSubmissionNotReceived as exc:
            return await self._failure(order, exc, S.FAILED)
        async with self.ctx.uow() as work:
            await work.lock_user(order.user_id)
            current = await work.orders.get(id=order.id)
            assert current is not None
            order = replace(
                current,
                alpaca_order_id=str(raw["id"]),
                provider_status=str(raw.get("status") or "accepted"),
                updated_at=self.ctx.clock.now(),
            )
            await work.orders.save(order, status=current.status)
            await self.ledger.transfer(work, order.id, self.ctx.clock.now())
        return order

    async def _reject_waiting(self, order: Order, reason: str) -> Order:
        async with self.ctx.uow() as work:
            await work.lock_user(order.user_id)
            current = await work.orders.get(id=order.id)
            if current is None or current.status not in {S.PENDING, S.BROKER_SIGNED}:
                return current or order
            order = await change(work, current, S.REJECTED, reason, self.ctx.clock.now())
            await self.ctx.release_unsent(work, order)
        await self.ctx.notify(order, reason)
        code = ErrorCode(reason)
        status = 422 if code in {ErrorCode.ASSET_NOT_TRADABLE, ErrorCode.VALIDATION_ERROR} else 409
        raise OrderDomainError(
            status,
            code,
            "Order failed revalidation.",
            {"order_id": str(order.id), "reason": reason},
        )

    async def _failure(self, order: Order, error: AppError, target: S) -> Order:
        async with self.ctx.uow() as work:
            await work.lock_user(order.user_id)
            current = await work.orders.get(id=order.id)
            assert current is not None
            order = await change(
                work,
                current,
                target,
                str(error.code),
                self.ctx.clock.now(),
                metadata=error.details or {},
            )
            await self.ctx.release_unsent(work, order)
        await self.ctx.notify(order, str(error.code))
        raise OrderDomainError(
            error.status,
            error.code,
            error.message,
            {**(error.details or {}), "order_id": str(order.id)},
        )

    @staticmethod
    def _payload(order: Order) -> Raw:
        result: Raw = {
            "symbol": order.symbol,
            "qty": str(order.qty),
            "side": order.side,
            "type": order.type,
            "order_class": order.order_class,
            "time_in_force": order.time_in_force,
            "client_order_id": order.client_order_id,
            "extended_hours": False,
        }
        for name in ("limit_price", "stop_price", "trail_price", "trail_percent"):
            value = getattr(order, name)
            if value is not None:
                result[name] = str(value)
        if order.order_class == "bracket":
            result["take_profit"] = {"limit_price": str(order.take_profit_limit_price)}
            result["stop_loss"] = {"stop_price": str(order.stop_loss_stop_price)}
        return result
