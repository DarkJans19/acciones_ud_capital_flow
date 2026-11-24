import asyncio
import logging
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal, localcontext
from typing import TypedDict, Unpack
from uuid import UUID, uuid4

from acciones_ud.orders.application.reservation_ledger import ReservationLedger
from acciones_ud.orders.domain import ports as p
from acciones_ud.orders.domain.errors import InvalidTransitionError, OrderDomainError
from acciones_ud.orders.domain.estimates import (
    base_price,
    estimated_amount,
    requires_extra_authorization,
)
from acciones_ud.orders.domain.model import (
    LinkedAccount,
    Order,
    OrderConfig,
    OrderControls,
    OrderEvent,
    OrderRequest,
    OrderStatus,
    SessionWindow,
    TradableAsset,
)
from acciones_ud.orders.domain.state_machine import transition
from acciones_ud.orders.domain.validation import validate
from acciones_ud.shared.domain.alpaca_errors import AlpacaError, AlpacaRateLimited
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import ErrorCode
from acciones_ud.shared.domain.trading import CommissionTerms

logger = logging.getLogger(__name__)


def provider_error(error: AlpacaError) -> OrderDomainError:
    limited = isinstance(error, AlpacaRateLimited)
    return OrderDomainError(
        503 if limited else 502,
        ErrorCode.ALPACA_RATE_LIMITED if limited else ErrorCode.ALPACA_UNAVAILABLE,
        "Alpaca is unavailable.",
    )


def is_unsent(order: Order) -> bool:
    return (
        order.alpaca_order_id is None
        and order.submit_attempted_at is None
        and order.status
        in {OrderStatus.PENDING, OrderStatus.IN_REVIEW, OrderStatus.BROKER_SIGNED, OrderStatus.HELD}
    )


class OrderChanges(TypedDict, total=False):
    submit_attempted_at: datetime | None
    broker_id: UUID | None
    broker_signed_at: datetime | None
    scheduled_for: datetime | None
    scheduled_session_end: datetime | None
    returned_for_changes: bool


@dataclass(frozen=True)
class Prepared:
    request: OrderRequest
    account: LinkedAccount
    asset: TradableAsset
    controls: OrderControls
    reference_price: Decimal
    amount: Decimal
    authorization: str
    buying_power: Decimal
    qty_available: Decimal
    market_open: bool
    session: SessionWindow | None
    terms: CommissionTerms


def restored_price(value: Decimal | None) -> Decimal | None:
    """Remove SQL NUMERIC padding when reconstructing an already stored price."""
    if value is None:
        return None
    with localcontext() as context:
        context.prec = max(context.prec, len(value.as_tuple().digits))
        return value.normalize()


def request_from(order: Order) -> OrderRequest:
    return OrderRequest(
        order.symbol,
        order.side,
        order.qty,
        order.type,
        order.order_class,
        order.time_in_force,
        restored_price(order.limit_price),
        restored_price(order.stop_price),
        restored_price(order.trail_price),
        order.trail_percent,
        restored_price(order.take_profit_limit_price),
        restored_price(order.stop_loss_stop_price),
        order.schedule_if_closed,
        True,
    )


async def change(
    work: p.OrderWork,
    order: Order,
    target: OrderStatus,
    cause: str,
    now: datetime,
    *,
    actor_type: str = "system",
    actor_id: UUID | None = None,
    metadata: dict[str, object] | None = None,
    **changes: Unpack[OrderChanges],
) -> Order:
    transition(order.status, target, order.fully_filled)
    updated = replace(order, status=target, status_cause=cause, updated_at=now, **changes)
    event = OrderEvent(
        uuid4(), order.id, order.status, target, cause, actor_type, actor_id, now, metadata or {}
    )
    if not await work.orders.change(updated, order, event):
        raise InvalidTransitionError()
    return updated


@dataclass(frozen=True)
class OrderContext:
    uow: p.OrderWorkFactory
    accounts: p.AccountReader
    controls: p.OrderControlsReader
    totp: p.TotpVerifier
    quotes: p.QuoteReader
    assets: p.AssetReader
    sessions: p.MarketSessionPort
    buying_power: p.BuyingPowerPort
    positions: p.PositionPort
    alpaca: p.AlpacaOrdersPort
    brokers: p.BrokerLinkPort
    notifier: p.OrderNotifierPort
    clock: Clock
    config: OrderConfig
    commission_terms: p.CommissionTermsPort | None = None
    trading_gate: p.TradingGatePort | None = None

    async def check_gate(self, user_id: UUID, exchange: str) -> None:
        if self.trading_gate is not None:
            decision = await self.trading_gate.check(user_id, exchange, self.clock.now())
            if not decision.allowed:
                assert decision.code is not None
                raise OrderDomainError(
                    503 if decision.code == "TRADING_HALTED" else 403,
                    ErrorCode(decision.code),
                    "Trading is currently restricted.",
                    decision.details,
                )

    async def prepare(
        self,
        user_id: UUID,
        request: OrderRequest,
        *,
        authorize: bool,
        totp_code: str | None = None,
        preview: bool = False,
        check_session: bool = True,
        at: datetime | None = None,
        terms: CommissionTerms | None = None,
    ) -> Prepared:
        account = await self.accounts.get(user_id)
        if account is None or account.status != "ACTIVE":
            raise OrderDomainError(
                409, ErrorCode.ORDER_ACCOUNT_NOT_ACTIVE, "Active account required."
            )
        asset = await self.assets.get(request.symbol)
        if asset is None or not asset.active or not asset.tradable:
            raise OrderDomainError(422, ErrorCode.ASSET_NOT_TRADABLE, "Asset is not tradable.")
        await self.check_gate(user_id, asset.exchange)
        if terms is None:
            terms = (
                await self.commission_terms.terms(asset.exchange, at or self.clock.now())
                if self.commission_terms
                else CommissionTerms(None, self.config.commission_rate * 100, Decimal("60.00"))
            )
        # Independent reads use separate ports/transactions. Run them together
        # without sharing an AsyncSession or weakening the investor lock below.
        reference, controls = await asyncio.gather(
            self.quotes.current_price(request.symbol), self.controls.get(user_id)
        )
        if reference is None or not reference.is_finite() or reference <= 0:
            raise OrderDomainError(503, ErrorCode.QUOTE_UNAVAILABLE, "Quote is unavailable.")
        request = replace(request, type=request.type or controls.default_order_type)
        tentative_base = (
            request.limit_price
            if request.type in {"limit", "stop_limit"}
            else (request.stop_price if request.type == "stop" else reference)
        )
        errors = validate(
            request, asset, tentative_base if tentative_base is not None else reference
        )
        if errors:
            raise OrderDomainError(
                422,
                ErrorCode.VALIDATION_ERROR,
                "Invalid order fields.",
                {"fields": [error.field for error in errors]},
            )
        amount = estimated_amount(
            request.side,
            request.qty,
            base_price(request.type or "", request.limit_price, request.stop_price, reference),
            terms.commission_rate_pct / 100,
        )
        method = requires_extra_authorization(amount, controls)
        if authorize and method == "totp":
            if not await self.totp.has_active_totp(user_id):
                raise OrderDomainError(
                    409, ErrorCode.MFA_ENROLLMENT_REQUIRED, "MFA enrollment required."
                )
            if not totp_code:
                raise OrderDomainError(
                    409,
                    ErrorCode.EXTRA_AUTHORIZATION_REQUIRED,
                    "Extra authorization required.",
                    {"method": method},
                )
            if not await self.totp.verify(user_id, totp_code, self.clock.now()):
                raise OrderDomainError(
                    401, ErrorCode.EXTRA_AUTHORIZATION_INVALID, "Extra authorization is invalid."
                )
        elif authorize and method == "acknowledgement" and not request.high_amount_acknowledged:
            raise OrderDomainError(
                409,
                ErrorCode.EXTRA_AUTHORIZATION_REQUIRED,
                "Extra authorization required.",
                {"method": method},
            )
        open_now, session = True, None
        if check_session:
            open_now = await self.sessions.is_open(asset.exchange, self.clock.now())
            if not open_now:
                session = await self.sessions.next_open(asset.exchange, self.clock.now())
                if not preview and not request.schedule_if_closed:
                    raise OrderDomainError(
                        409,
                        ErrorCode.MARKET_CLOSED,
                        "Market is closed.",
                        {"next_open": session.opens_at.isoformat()},
                    )
        power, position = Decimal(0), Decimal(0)
        try:
            if request.side == "buy" or preview:
                async with asyncio.timeout(4):
                    power = await self.buying_power.buying_power(account.alpaca_account_id)
            if request.side == "sell":
                async with asyncio.timeout(4):
                    position = await self.positions.qty_available(
                        account.alpaca_account_id, request.symbol
                    )
        except (AlpacaError, TimeoutError):
            raise OrderDomainError(
                502, ErrorCode.ALPACA_UNAVAILABLE, "Account resources are unavailable."
            ) from None
        return Prepared(
            request,
            account,
            asset,
            controls,
            reference,
            amount,
            method,
            power,
            position,
            open_now,
            session,
            terms,
        )

    async def notify(self, order: Order, cause: str, **payload: object) -> None:
        try:
            await self.notifier.notify(
                order.user_id,
                "order_updates",
                {"order_id": str(order.id), "cause": cause, **payload},
            )
        except Exception:
            logger.warning("Order notification failed", extra={"order_id": str(order.id)})

    async def release_unsent(self, work: p.OrderWork, order: Order) -> None:
        if order.alpaca_order_id is None:
            reservation = await work.reservations.get(order_id=order.id)
            if reservation is not None and reservation.status == "active":
                await ReservationLedger().release(work, order.id, self.clock.now())
