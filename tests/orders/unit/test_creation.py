from dataclasses import replace
from decimal import Decimal

import pytest

from acciones_ud.orders.application.order_service import OrderService
from acciones_ud.orders.domain.model import OrderRequest
from acciones_ud.orders.domain.model import OrderStatus as S
from acciones_ud.shared.domain.errors import AppError
from tests.orders.support import make_context


async def test_preview_creation_and_scheduling() -> None:
    context, user = make_context()
    service = OrderService(context)
    request = OrderRequest("AAPL", "buy", Decimal(1), confirmed=True)
    preview = await service.preview(user, request)
    assert preview["estimated_amount"] == Decimal("10.20")
    assert not context.uow.work.orders.values and not context.uow.work.reservations.values
    order = await service.create(user, request, "key12345")
    assert order.status == S.SUBMITTED and order.alpaca_order_id
    assert [e.to_status for e in context.uow.work.events.values] == [S.PENDING, S.SUBMITTED]
    context.sessions.open = False
    with pytest.raises(AppError) as caught:
        await service.create(user, request, "key12346")
    assert caught.value.code == "MARKET_CLOSED"
    scheduled = await service.create(user, replace(request, schedule_if_closed=True), "key12347")
    assert scheduled.status == S.PENDING and scheduled.scheduled_for
    assert sum(context.alpaca.creations.values()) == 1


async def test_large_quantity_rejects_for_funds_before_persistence() -> None:
    context, user = make_context()
    with pytest.raises(AppError) as caught:
        await OrderService(context).create(
            user,
            OrderRequest("AAPL", "buy", Decimal("1e40"), confirmed=True),
            "key12345",
            totp_code="123456",
        )
    assert caught.value.code == "INSUFFICIENT_BUYING_POWER"
    assert not context.uow.work.orders.values and not context.alpaca.creations


@pytest.mark.parametrize(
    "change,code",
    [
        ("no_confirmation", "VALIDATION_ERROR"),
        ("no_account", "ORDER_ACCOUNT_NOT_ACTIVE"),
        ("no_asset", "ASSET_NOT_TRADABLE"),
        ("no_quote", "QUOTE_UNAVAILABLE"),
        ("daily_limit", "DAILY_ORDER_LIMIT_REACHED"),
        ("high_amount", "EXTRA_AUTHORIZATION_REQUIRED"),
        ("mfa_disabled", "MFA_ENROLLMENT_REQUIRED"),
        ("mfa_invalid", "EXTRA_AUTHORIZATION_INVALID"),
    ],
)
async def test_creation_failures_have_no_order(change, code) -> None:
    context, user = make_context()
    request = OrderRequest("AAPL", "buy", Decimal(1), confirmed=True)
    if change == "no_confirmation":
        request = replace(request, confirmed=False)
    elif change == "no_account":
        context.accounts.values.clear()
    elif change == "no_asset":
        context.assets.values.clear()
    elif change == "no_quote":
        context.quotes.price = None
    elif change == "daily_limit":
        context.controls.value = replace(context.controls.value, daily_order_limit=0)
    else:
        request = replace(request, qty=Decimal(1000))
        context.totp.active = change != "mfa_disabled"
        context.totp.valid = change != "mfa_invalid"
    with pytest.raises(AppError) as caught:
        await OrderService(context).create(
            user, request, "key12345", totp_code="123456" if change == "mfa_invalid" else None
        )
    assert caught.value.code == code
    assert not context.uow.work.orders.values and not context.uow.work.reservations.values
    assert not context.alpaca.creations
