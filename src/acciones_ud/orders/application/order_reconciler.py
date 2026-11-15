import logging
from dataclasses import replace
from decimal import ROUND_UP, Decimal, InvalidOperation

from acciones_ud.orders.application.context import OrderContext, change
from acciones_ud.orders.application.dtos import instant
from acciones_ud.orders.application.reservation_ledger import ReservationLedger
from acciones_ud.orders.domain.errors import InvalidTransitionError
from acciones_ud.orders.domain.model import ActivityCursor, Execution, Order, OrderLeg, Raw
from acciones_ud.orders.domain.model import OrderStatus as S
from acciones_ud.orders.domain.state_machine import is_terminal
from acciones_ud.orders.domain.status_mapping import map_alpaca

logger = logging.getLogger(__name__)


class OrderReconciler:
    def __init__(self, context: OrderContext) -> None:
        self.ctx, self.ledger = context, ReservationLedger()

    async def run_once(self) -> None:
        async with self.ctx.uow() as work:
            orders = await work.orders.list()
        # Activities can arrive after cancellation. Continue consuming each known account's
        # independent cursor, while polling order state only for nonterminal sent orders.
        accounts: dict[str, list[Order]] = {}
        for order in orders:
            accounts.setdefault(order.alpaca_account_id, []).append(order)
        for account_id, local in accounts.items():
            try:
                for order in local:
                    if order.status in {S.SUBMITTED, S.EXECUTING} and not order.fully_filled:
                        await self._poll(order)
                async with self.ctx.uow() as work:
                    cursor = await work.cursors.get(alpaca_account_id=account_id)
                fills = await self.ctx.alpaca.list_fills(
                    account_id, cursor.last_activity_id if cursor else None
                )
                for fill in fills:
                    await self._fill(account_id, local[0], fill)
            except Exception:
                logger.warning(
                    "Order reconciliation failed for account",
                    extra={"alpaca_account_id": account_id},
                )

    async def _poll(self, snapshot: Order) -> None:
        if snapshot.alpaca_order_id is None:
            raw = await self.ctx.alpaca.get_by_client_order_id(
                snapshot.alpaca_account_id, snapshot.client_order_id
            )
            failed = None
            async with self.ctx.uow() as work:
                await work.lock_user(snapshot.user_id)
                current = await work.orders.get(id=snapshot.id)
                if current is None or is_terminal(current.status, current.fully_filled):
                    return
                if current.alpaca_order_id is None:
                    if raw is None:
                        updated = replace(
                            current,
                            lookup_misses=current.lookup_misses + 1,
                            updated_at=self.ctx.clock.now(),
                        )
                        if updated.lookup_misses >= 2:
                            failed = await change(
                                work,
                                updated,
                                S.FAILED,
                                "provider_order_not_found",
                                self.ctx.clock.now(),
                            )
                            await self.ctx.release_unsent(work, failed)
                        else:
                            await work.orders.save(updated, status=current.status)
                    else:
                        current = replace(
                            current,
                            alpaca_order_id=str(raw["id"]),
                            provider_status=str(raw["status"]),
                            updated_at=self.ctx.clock.now(),
                        )
                        await work.orders.save(current)
                        await self.ledger.transfer(work, current.id, self.ctx.clock.now())
            if failed:
                await self.ctx.notify(failed, "provider_order_not_found")
            if raw is None:
                return
        else:
            raw = await self.ctx.alpaca.get(snapshot.alpaca_account_id, snapshot.alpaca_order_id)
        async with self.ctx.uow() as work:
            await work.lock_user(snapshot.user_id)
            current = await work.orders.get(id=snapshot.id)
            if current is None or is_terminal(current.status, current.fully_filled):
                return
            provider_status = str(raw["status"])
            target = map_alpaca(provider_status, current.filled_qty)
            candidate = replace(
                current, provider_status=provider_status, updated_at=self.ctx.clock.now()
            )
            if target is not None and target != current.status:
                try:
                    current = await change(
                        work, candidate, target, "provider_status", self.ctx.clock.now()
                    )
                except InvalidTransitionError:
                    logger.warning(
                        "Provider transition ignored", extra={"order_id": str(current.id)}
                    )
                    await work.orders.save(candidate, status=current.status)
            else:
                if target is None:
                    logger.warning("Unknown provider status", extra={"order_id": str(current.id)})
                await work.orders.save(candidate, status=current.status)
            for leg in raw.get("legs") or []:
                role = leg.get("group_role") or (
                    "take_profit" if leg.get("type") == "limit" else "stop_loss"
                )
                if role not in {"take_profit", "stop_loss"}:
                    continue
                stored = await work.legs.get(order_id=current.id, role=role)
                price = leg.get("limit_price" if role == "take_profit" else "stop_price")
                if price is None:
                    if stored is None:
                        continue
                    leg_price = stored.price
                else:
                    leg_price = Decimal(str(price))
                item = OrderLeg(current.id, role, str(leg["id"]), leg_price, str(leg["status"]))
                if not await work.legs.save(item):
                    await work.legs.insert(item)
            pending = await work.cancels.list(order_id=current.id, outcome="pending")
            for cancellation in pending:
                if provider_status in {"filled", "canceled"}:
                    await work.cancels.save(
                        replace(
                            cancellation,
                            outcome="not_applied" if provider_status == "filled" else "applied",
                        )
                    )
        # A cancel requested while the external ID was missing is delivered once it is known.
        if (
            pending
            and provider_status not in {"filled", "canceled", "rejected", "expired"}
            and (current.alpaca_order_id is not None)
        ):
            await self.ctx.alpaca.cancel(current.alpaca_account_id, current.alpaca_order_id)

    async def _fill(self, account_id: str, account_order: Order, raw: Raw) -> None:
        execution_id = str(raw["id"])
        notification: tuple[Order, Execution] | None = None
        async with self.ctx.uow() as work:
            await work.lock_user(account_order.user_id)
            order = await work.orders.get(
                alpaca_account_id=account_id, alpaca_order_id=str(raw["order_id"])
            )
            if order and raw.get("type", "fill") in {"fill", "partial_fill"}:
                existing = await work.executions.get(alpaca_execution_id=execution_id)
                if existing is None:
                    try:
                        qty, price = Decimal(str(raw["qty"])), Decimal(str(raw["price"]))
                        if not qty.is_finite() or not price.is_finite() or qty <= 0 or price <= 0:
                            raise ValueError()
                        executions = await work.executions.list(order_id=order.id)
                        total = sum((v.qty for v in executions), Decimal(0)) + qty
                        if total > order.qty:
                            raise ValueError()
                    except (InvalidOperation, ValueError, TypeError):
                        logger.warning("Execution rejected", extra={"execution_id": execution_id})
                    else:
                        execution = Execution(
                            execution_id,
                            order.id,
                            qty,
                            price,
                            instant(str(raw["transaction_time"])),
                            self.ctx.clock.now(),
                        )
                        if await work.executions.insert(execution):
                            # Recompute exclusively from the committed execution ledger (D4).
                            executions = await work.executions.list(order_id=order.id)
                            total = sum((v.qty for v in executions), Decimal(0))
                            weighted = (
                                sum((v.qty * v.price for v in executions), Decimal(0)) / total
                            )
                            candidate = replace(
                                order,
                                filled_qty=total,
                                filled_avg_price=weighted,
                                fully_filled=total == order.qty,
                                updated_at=self.ctx.clock.now(),
                                completed_at=self.ctx.clock.now()
                                if total == order.qty
                                else order.completed_at,
                            )
                            if order.status == S.SUBMITTED:
                                order = await change(
                                    work,
                                    order,
                                    S.EXECUTING,
                                    "execution_recorded",
                                    self.ctx.clock.now(),
                                )
                            candidate = replace(
                                candidate, status=order.status, status_cause=order.status_cause
                            )
                            await work.orders.save(candidate, status=order.status)
                            if candidate.fully_filled:
                                for cancellation in await work.cancels.list(
                                    order_id=order.id, outcome="pending"
                                ):
                                    await work.cancels.save(
                                        replace(cancellation, outcome="not_applied")
                                    )
                            notification = candidate, execution
            cursor = await work.cursors.get(alpaca_account_id=account_id)
            if cursor is None:
                await work.cursors.insert(
                    ActivityCursor(account_id, execution_id, self.ctx.clock.now())
                )
            elif cursor.last_activity_id is None or execution_id > cursor.last_activity_id:
                await work.cursors.save(
                    ActivityCursor(account_id, execution_id, self.ctx.clock.now())
                )
        if notification:
            order, execution = notification
            commission = (
                execution.qty * execution.price * self.ctx.config.commission_rate
            ).quantize(Decimal("0.01"), rounding=ROUND_UP)
            try:
                await self.ctx.notifier.notify(
                    order.user_id,
                    "order_executions",
                    {
                        "order_id": str(order.id),
                        "instrument": order.symbol,
                        "side": order.side,
                        "qty": str(execution.qty),
                        "price": str(execution.price),
                        "reference_commission": str(commission),
                        "reference_commission_estimated": True,
                        "executed_at": execution.executed_at.isoformat(),
                    },
                )
            except Exception:
                logger.warning(
                    "Execution notification failed", extra={"execution_id": execution_id}
                )
