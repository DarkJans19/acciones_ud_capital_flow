import re
from dataclasses import asdict, replace
from datetime import datetime, timedelta
from decimal import ROUND_UP, Decimal
from uuid import UUID, uuid4

from acciones_ud.orders.application.context import (
    OrderContext,
    change,
    is_unsent,
    provider_error,
    request_from,
)
from acciones_ud.orders.application.order_submitter import OrderSubmitter
from acciones_ud.orders.application.reservation_ledger import ReservationLedger
from acciones_ud.orders.application.review_service import ReviewService
from acciones_ud.orders.domain.errors import InvalidTransitionError, OrderDomainError, not_found
from acciones_ud.orders.domain.estimates import base_price, estimated_amount
from acciones_ud.orders.domain.idempotency import request_hash
from acciones_ud.orders.domain.model import (
    CancelRequest,
    IdempotencyEntry,
    Order,
    OrderEvent,
    OrderLeg,
    OrderRequest,
    Raw,
)
from acciones_ud.orders.domain.model import (
    OrderStatus as S,
)
from acciones_ud.orders.domain.reservations import check_buy, check_sell
from acciones_ud.orders.domain.state_machine import initial_status, is_terminal
from acciones_ud.shared.domain.alpaca_errors import AlpacaError
from acciones_ud.shared.domain.errors import ErrorCode
from acciones_ud.shared.domain.trading import CommissionTerms


class OrderService:
    def __init__(self, context: OrderContext) -> None:
        self.ctx, self.ledger = context, ReservationLedger()
        self.submitter = OrderSubmitter(context)
        self.reviews = ReviewService(context, self.submitter)

    async def preview(self, user_id: UUID, request: OrderRequest) -> Raw:
        prepared = await self.ctx.prepare(
            user_id,
            replace(request, symbol=request.symbol.strip().upper()),
            authorize=False,
            preview=True,
        )
        async with self.ctx.uow() as work:
            active = await self.ledger.active_usd(work, user_id)
        price = base_price(
            prepared.request.type or "",
            request.limit_price,
            request.stop_price,
            prepared.reference_price,
        )
        commission = (request.qty * price * prepared.terms.commission_rate_pct / 100).quantize(
            Decimal("0.01"), rounding=ROUND_UP
        )
        return {
            "reference_price": prepared.reference_price,
            "estimated_amount": prepared.amount,
            "reference_commission": commission,
            "reference_commission_estimated": True,
            "available_buying_power": prepared.buying_power - active,
            "requires_extra_authorization": prepared.authorization != "none",
            "authorization_method": prepared.authorization,
            "market_open": prepared.market_open,
            "scheduled_for": prepared.session.opens_at if prepared.session else None,
        }

    async def create(
        self,
        user_id: UUID,
        request: OrderRequest,
        idempotency_key: str,
        totp_code: str | None = None,
    ) -> Order:
        return await self._create(user_id, request, idempotency_key, totp_code)

    async def _create(
        self,
        user_id: UUID,
        request: OrderRequest,
        idempotency_key: str,
        totp_code: str | None = None,
        *,
        signature: UUID | None = None,
        proposal_reason: str | None = None,
    ) -> Order:
        if not re.fullmatch(r"[\x20-\x7e]{8,128}", idempotency_key):
            raise OrderDomainError(
                422,
                ErrorCode.VALIDATION_ERROR,
                "Invalid Idempotency-Key.",
                {"fields": ["Idempotency-Key"]},
            )
        digest = request_hash(request)
        # Replays bypass account/quote/TOTP changes and return the stored current state.
        async with self.ctx.uow() as work:
            previous = await work.keys.get(user_id=user_id, idempotency_key=idempotency_key)
            if previous:
                if previous.request_hash != digest:
                    raise OrderDomainError(
                        409, ErrorCode.IDEMPOTENCY_CONFLICT, "Idempotency conflict."
                    )
                order = await work.orders.get(id=previous.order_id, user_id=user_id)
                if order is None:
                    raise not_found()
                return order
        if request.confirmed is not True:
            raise OrderDomainError(
                422,
                ErrorCode.VALIDATION_ERROR,
                "Explicit confirmation required.",
                {"fields": ["confirmed"]},
            )
        now = self.ctx.clock.now()
        prepared = await self.ctx.prepare(
            user_id,
            replace(request, symbol=request.symbol.strip().upper()),
            authorize=signature is None,
            totp_code=totp_code,
            at=now,
        )
        request = prepared.request
        broker_id = await self.ctx.brokers.reviewing_broker(user_id) if signature is None else None
        ident = uuid4()
        order = Order(
            ident,
            user_id,
            prepared.account.alpaca_account_id,
            request.symbol,
            prepared.asset.exchange,
            request.side,
            request.qty,
            request.type or "",
            request.order_class,
            request.time_in_force,
            prepared.reference_price,
            prepared.amount,
            initial_status(from_proposal=signature is not None),
            str(ident),
            now,
            now,
            limit_price=request.limit_price,
            stop_price=request.stop_price,
            trail_price=request.trail_price,
            trail_percent=request.trail_percent,
            take_profit_limit_price=request.take_profit_limit_price,
            stop_loss_stop_price=request.stop_loss_stop_price,
            scheduled_for=prepared.session.opens_at if prepared.session else None,
            scheduled_session_end=prepared.session.closes_at if prepared.session else None,
            schedule_if_closed=request.schedule_if_closed,
            broker_id=signature,
            broker_signed_at=now if signature else None,
            fee_version_id=prepared.terms.fee_version_id,
            commission_rate_pct=prepared.terms.commission_rate_pct,
            platform_share_pct=prepared.terms.platform_share_pct,
        )
        async with self.ctx.uow() as work:
            await work.lock_user(user_id)
            previous = await work.keys.get(user_id=user_id, idempotency_key=idempotency_key)
            if previous:
                if previous.request_hash != digest:
                    raise OrderDomainError(
                        409, ErrorCode.IDEMPOTENCY_CONFLICT, "Idempotency conflict."
                    )
                existing = await work.orders.get(id=previous.order_id, user_id=user_id)
                if existing is None:
                    raise not_found()
                return existing
            if await work.orders.daily_count(user_id, now) >= prepared.controls.daily_order_limit:
                raise OrderDomainError(
                    409, ErrorCode.DAILY_ORDER_LIMIT_REACHED, "Daily order limit reached."
                )
            if order.side == "buy":
                check_buy(
                    order.estimated_amount,
                    prepared.buying_power,
                    await self.ledger.active_usd(work, user_id),
                )
            else:
                check_sell(
                    order.qty,
                    prepared.qty_available,
                    await self.ledger.active_shares(work, user_id, order.symbol),
                )
            await work.orders.insert(order)
            await self.ledger.reserve(
                work, order, prepared.buying_power, prepared.qty_available, now
            )
            authorization: dict[str, object] = (
                {}
                if prepared.authorization == "none"
                else {
                    "authorization_method": prepared.authorization,
                    "authorized_at": now.isoformat(),
                }
            )
            if signature is not None:
                authorization = {
                    "authorization_method": "proposal_acceptance",
                    "reason": proposal_reason,
                }
            await work.events.insert(
                OrderEvent(
                    uuid4(),
                    ident,
                    None,
                    order.status,
                    proposal_reason or "created",
                    "broker" if signature else "investor",
                    signature or user_id,
                    now,
                    authorization,
                )
            )
            for role, price in (
                ("take_profit", request.take_profit_limit_price),
                ("stop_loss", request.stop_loss_stop_price),
            ):
                if price is not None:
                    await work.legs.insert(OrderLeg(ident, role, None, price))
            await work.keys.insert(IdempotencyEntry(user_id, idempotency_key, digest, ident, now))
            if broker_id is not None:
                order = await self.reviews.route_new_order(work, order, broker_id)
            elif prepared.market_open and signature is None:
                order = await self.submitter.stage(work, order)
        if signature is not None and prepared.market_open:
            return await self.submitter.submit(order.id, waited=False)
        if order.status == S.SUBMITTED:
            return await self.submitter._dispatch(order)
        return order

    async def get(self, user_id: UUID, order_id: UUID) -> Raw:
        async with self.ctx.uow() as work:
            order = await work.orders.get(id=order_id, user_id=user_id)
            if order is None:
                raise not_found()
            detail = asdict(order)
            for name in ("legs", "events", "executions", "cancels"):
                detail[name] = await getattr(work, name).list(order_id=order_id)
            detail["reservation"] = await work.reservations.get(order_id=order_id)
            detail["reauthorizations"] = await work.reauthorizations.list(order_id=order_id)
            detail["review_comments"] = await work.comments.list(order_id=order_id)
        price = base_price(order.type, order.limit_price, order.stop_price, order.reference_price)
        detail["reference_commission"] = (
            order.qty
            * price
            * (
                order.commission_rate_pct / 100
                if order.commission_rate_pct is not None
                else self.ctx.config.commission_rate
            )
        ).quantize(Decimal("0.01"), rounding=ROUND_UP)
        detail["reference_commission_estimated"] = True
        return detail

    async def list(
        self,
        user_id: UUID,
        status: str | None = None,
        symbol: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        page_size: int = 20,
        cursor: str | None = None,
    ) -> Raw:
        invalid = []
        if status is not None and status not in {value.value for value in S}:
            invalid.append("status")
        if not 1 <= page_size <= 100:
            invalid.append("page_size")
        if (
            (start and start.tzinfo is None)
            or (end and end.tzinfo is None)
            or (start and end and start > end)
        ):
            invalid.extend(["from", "to"])
        if invalid:
            raise OrderDomainError(
                422, ErrorCode.VALIDATION_ERROR, "Invalid query fields.", {"fields": invalid}
            )
        async with self.ctx.uow() as work:
            items, next_cursor = await work.orders.page(
                user_id,
                status,
                symbol.strip().upper() if symbol else None,
                start,
                end,
                page_size,
                cursor,
            )
        return {"items": items, "next_cursor": next_cursor}

    async def cancel(
        self, user_id: UUID, order_id: UUID, reason: str, reason_text: str | None, confirmed: bool
    ) -> tuple[Order, int]:
        fields = []
        if reason not in {"price_changed", "no_longer_needed", "input_error", "other"}:
            fields.append("reason")
        if confirmed is not True:
            fields.append("confirmed")
        if (reason == "other" or reason_text is not None) and (
            reason_text is None or not 1 <= len(reason_text.strip()) <= 500
        ):
            fields.append("reason_text")
        if fields:
            raise OrderDomainError(
                422, ErrorCode.VALIDATION_ERROR, "Invalid cancellation fields.", {"fields": fields}
            )
        now = self.ctx.clock.now()
        async with self.ctx.uow() as work:
            await work.lock_user(user_id)
            order = await work.orders.get(id=order_id, user_id=user_id)
            if order is None:
                raise not_found()
            if is_terminal(order.status, order.fully_filled):
                raise OrderDomainError(
                    409, ErrorCode.ORDER_NOT_CANCELLABLE, "Order cannot be canceled."
                )
            local = is_unsent(order)
            cancellation = CancelRequest(
                uuid4(),
                order.id,
                order.status,
                reason,
                reason_text,
                True,
                now,
                "applied" if local else "pending",
            )
            await work.cancels.insert(cancellation)
            if local:
                order = await change(
                    work,
                    order,
                    S.CANCELED,
                    "user_canceled",
                    now,
                    actor_type="investor",
                    actor_id=user_id,
                )
                await self.ctx.release_unsent(work, order)
                pending = await work.reauthorizations.get(order_id=order.id, decision=None)
                if pending:
                    await work.reauthorizations.save(
                        replace(pending, decision="rejected", answered_at=now)
                    )
        if local:
            return order, 200
        try:
            if order.alpaca_order_id is None:
                found = await self.ctx.alpaca.get_by_client_order_id(
                    order.alpaca_account_id, order.client_order_id
                )
                if found is not None:
                    async with self.ctx.uow() as work:
                        await work.lock_user(user_id)
                        current = await work.orders.get(id=order.id)
                        assert current is not None
                        order = replace(
                            current,
                            alpaca_order_id=str(found["id"]),
                            provider_status=str(found["status"]),
                            updated_at=self.ctx.clock.now(),
                        )
                        await work.orders.save(order, status=current.status)
                        await self.ledger.transfer(work, order.id, self.ctx.clock.now())
            if order.alpaca_order_id is not None:
                outcome = await self.ctx.alpaca.cancel(
                    order.alpaca_account_id, order.alpaca_order_id
                )
                if outcome == "not_cancelable":
                    async with self.ctx.uow() as work:
                        await work.cancels.save(replace(cancellation, outcome="not_applied"))
        except AlpacaError as exc:
            raise provider_error(exc) from None
        return order, 202

    async def answer_reauthorization(self, user_id: UUID, order_id: UUID, decision: str) -> Order:
        if decision not in {"accept", "reject"}:
            raise OrderDomainError(
                422, ErrorCode.VALIDATION_ERROR, "Invalid decision.", {"fields": ["decision"]}
            )
        async with self.ctx.uow() as work:
            order = await work.orders.get(id=order_id, user_id=user_id)
            if order is None:
                raise not_found()
            initial = await work.reauthorizations.get(order_id=order_id, decision=None)
        if order.status != S.HELD or initial is None:
            raise InvalidTransitionError()
        prepared, session, open_now = None, None, False
        if decision == "accept" and self.ctx.clock.now() < initial.deadline:
            prepared = await self.ctx.prepare(
                user_id,
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
            open_now = await self.ctx.sessions.is_open(order.exchange, self.ctx.clock.now())
            if not open_now:
                session = await self.ctx.sessions.next_open(order.exchange, self.ctx.clock.now())
        late = False
        async with self.ctx.uow() as work:
            await work.lock_user(user_id)
            current = await work.orders.get(id=order_id, user_id=user_id)
            pending = await work.reauthorizations.get(order_id=order_id, decision=None)
            if current is None:
                raise not_found()
            if current.status != S.HELD or pending is None or pending.id != initial.id:
                raise InvalidTransitionError()
            now = self.ctx.clock.now()
            if now >= pending.deadline:
                late = True
                await work.reauthorizations.save(
                    replace(pending, decision="no_response", answered_at=now)
                )
                order = await change(work, current, S.EXPIRED, "reauthorization_timeout", now)
                await self.ctx.release_unsent(work, order)
            elif decision == "reject":
                await work.reauthorizations.save(
                    replace(pending, decision="rejected", answered_at=now)
                )
                order = await change(
                    work,
                    current,
                    S.CANCELED,
                    "reauthorization_rejected",
                    now,
                    actor_type="investor",
                    actor_id=user_id,
                )
                await self.ctx.release_unsent(work, order)
            else:
                assert prepared is not None
                amount = estimated_amount(
                    current.side,
                    current.qty,
                    base_price(
                        current.type, current.limit_price, current.stop_price, pending.updated_price
                    ),
                    current.commission_rate_pct / 100
                    if current.commission_rate_pct is not None
                    else self.ctx.config.commission_rate,
                )
                candidate = replace(
                    current,
                    reference_price=pending.updated_price,
                    estimated_amount=amount,
                    scheduled_for=session.opens_at if session else current.scheduled_for,
                    scheduled_session_end=session.closes_at
                    if session
                    else current.scheduled_session_end,
                )
                await self.ledger.adjust(
                    work, candidate, prepared.buying_power, prepared.qty_available, now
                )
                await work.reauthorizations.save(
                    replace(pending, decision="accepted", answered_at=now)
                )
                target = S.BROKER_SIGNED if pending.resume_status == S.BROKER_SIGNED else S.PENDING
                order = await change(
                    work,
                    candidate,
                    target,
                    "reauthorization_accepted",
                    now,
                    actor_type="investor",
                    actor_id=user_id,
                )
                if open_now:
                    order = await self.submitter.stage(work, order)
        if late:
            await self.ctx.notify(order, "reauthorization_timeout")
            raise InvalidTransitionError()
        if order.status == S.SUBMITTED:
            return await self.submitter._dispatch(order)
        if order.status == S.CANCELED:
            await self.ctx.notify(order, "reauthorization_rejected")
        return order

    async def expire_stale(self) -> None:
        async with self.ctx.uow() as work:
            candidates = [o for o in await work.orders.list() if is_unsent(o)]
        for candidate in candidates:
            expired = None
            async with self.ctx.uow() as work:
                await work.lock_user(candidate.user_id)
                order = await work.orders.get(id=candidate.id)
                if order is None or not is_unsent(order):
                    continue
                now = self.ctx.clock.now()
                pending = await work.reauthorizations.get(order_id=order.id, decision=None)
                cause = None
                if pending and now >= pending.deadline:
                    cause = "reauthorization_timeout"
                elif order.created_at < now - timedelta(days=self.ctx.config.local_max_age_days):
                    cause = "local_max_age"
                elif (
                    order.time_in_force == "day"
                    and order.scheduled_session_end is not None
                    and (now >= order.scheduled_session_end)
                ):
                    cause = "scheduled_session_expired"
                if cause:
                    if pending:
                        await work.reauthorizations.save(
                            replace(pending, decision="no_response", answered_at=now)
                        )
                    expired = await change(work, order, S.EXPIRED, cause, now)
                    await self.ctx.release_unsent(work, expired)
            if expired:
                await self.ctx.notify(expired, expired.status_cause or "expired")

    async def resubmit(
        self, user_id: UUID, order_id: UUID, changes: Raw, totp_code: str | None = None
    ) -> Order:
        allowed = {
            "qty",
            "limit_price",
            "stop_price",
            "trail_price",
            "trail_percent",
            "time_in_force",
            "take_profit_limit_price",
            "stop_loss_stop_price",
            "high_amount_acknowledged",
        }
        fields = [name for name in changes if name not in allowed]
        for name, value in changes.items():
            if name == "qty" and not isinstance(value, Decimal):
                fields.append(name)
            elif name == "time_in_force" and not isinstance(value, str):
                fields.append(name)
            elif name == "high_amount_acknowledged" and type(value) is not bool:
                fields.append(name)
            elif name not in {"qty", "time_in_force", "high_amount_acknowledged"} and (
                value is not None and not isinstance(value, Decimal)
            ):
                fields.append(name)
        if fields:
            raise OrderDomainError(
                422, ErrorCode.VALIDATION_ERROR, "Invalid fields.", {"fields": fields}
            )
        async with self.ctx.uow() as work:
            order = await work.orders.get(id=order_id, user_id=user_id)
        if order is None:
            raise not_found()
        if order.status != S.PENDING or not order.returned_for_changes:
            raise InvalidTransitionError()
        prepared = await self.ctx.prepare(
            user_id,
            replace(request_from(order), **changes),
            authorize=True,
            totp_code=totp_code,
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
        broker_id = await self.ctx.brokers.reviewing_broker(user_id)
        if broker_id is None:
            raise InvalidTransitionError()
        async with self.ctx.uow() as work:
            await work.lock_user(user_id)
            current = await work.orders.get(id=order_id, user_id=user_id)
            if current is None:
                raise not_found()
            if current.status != S.PENDING or not current.returned_for_changes:
                raise InvalidTransitionError()
            request = prepared.request
            candidate = replace(
                current,
                qty=request.qty,
                limit_price=request.limit_price,
                stop_price=request.stop_price,
                trail_price=request.trail_price,
                trail_percent=request.trail_percent,
                time_in_force=request.time_in_force,
                take_profit_limit_price=request.take_profit_limit_price,
                stop_loss_stop_price=request.stop_loss_stop_price,
                reference_price=prepared.reference_price,
                estimated_amount=prepared.amount,
                returned_for_changes=False,
            )
            await self.ledger.adjust(
                work, candidate, prepared.buying_power, prepared.qty_available, self.ctx.clock.now()
            )
            for role, price in (
                ("take_profit", request.take_profit_limit_price),
                ("stop_loss", request.stop_loss_stop_price),
            ):
                if price is not None:
                    leg = OrderLeg(order_id, role, None, price)
                    if not await work.legs.save(leg):
                        await work.legs.insert(leg)
            return await change(
                work,
                candidate,
                S.IN_REVIEW,
                "broker_review",
                self.ctx.clock.now(),
                actor_type="investor",
                actor_id=user_id,
                metadata={
                    "reviewing_broker_id": str(broker_id),
                    "authorization_method": prepared.authorization,
                    "authorized_at": self.ctx.clock.now().isoformat(),
                },
            )

    async def resume(self, user_id: UUID, order_id: UUID) -> Order:
        async with self.ctx.uow() as work:
            order = await work.orders.get(id=order_id, user_id=user_id)
        if order is None:
            raise not_found()
        if order.status != S.IN_REVIEW or order.status_cause != "schedule_change":
            raise InvalidTransitionError()
        broker = await self.ctx.brokers.reviewing_broker(user_id)
        open_now = await self.ctx.sessions.is_open(order.exchange, self.ctx.clock.now())
        session = (
            None
            if open_now
            else await self.ctx.sessions.next_open(order.exchange, self.ctx.clock.now())
        )
        queued = False
        async with self.ctx.uow() as work:
            await work.lock_user(user_id)
            current = await work.orders.get(id=order_id, user_id=user_id)
            if current is None:
                raise not_found()
            if current.status != S.IN_REVIEW or current.status_cause != "schedule_change":
                raise InvalidTransitionError()
            order = await change(
                work,
                current,
                S.PENDING,
                "schedule_resumed",
                self.ctx.clock.now(),
                actor_type="investor",
                actor_id=user_id,
                scheduled_for=session.opens_at if session else current.scheduled_for,
                scheduled_session_end=session.closes_at
                if session
                else current.scheduled_session_end,
            )
            # A calendar edit cannot replace a missing Broker approval (RF-30).
            if broker is not None and (
                order.broker_signed_at is None or order.returned_for_changes
            ):
                order = await self.reviews.route_new_order(work, order, broker)
                queued = True
        if queued:
            await self.ctx.notify(
                order,
                "broker_review",
                scheduled_for=order.scheduled_for.isoformat() if order.scheduled_for else None,
            )
            return order
        if open_now:
            return await self.submitter.submit(order.id, waited=True)
        await self.ctx.notify(
            order,
            "scheduled",
            scheduled_for=order.scheduled_for.isoformat() if order.scheduled_for else None,
        )
        return order
