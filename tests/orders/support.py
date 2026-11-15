from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

from acciones_ud.orders.domain.model import Order, OrderStatus
from tests.support.clock import FakeClock


def make_order(user_id=None, **changes):
    clock = FakeClock()
    ident = uuid4()
    order = Order(
        ident,
        user_id or uuid4(),
        "account",
        "AAPL",
        "NASDAQ",
        "buy",
        Decimal("1"),
        "market",
        "simple",
        "day",
        Decimal("10"),
        Decimal("10.20"),
        OrderStatus.PENDING,
        str(ident),
        clock.now(),
        clock.now(),
    )
    return replace(order, **changes)


def make_context():
    from acciones_ud.orders.adapters.outbound.alpaca.fake_orders import FakeOrders
    from acciones_ud.orders.application.context import OrderContext
    from acciones_ud.orders.domain.model import LinkedAccount, OrderConfig
    from tests.orders.fakes import (
        Accounts,
        Assets,
        BrokerLinks,
        BuyingPower,
        Controls,
        MemoryFactory,
        Notifications,
        Quotes,
        Sessions,
        Totp,
    )

    user_id, uow, accounts, alpaca = uuid4(), MemoryFactory(), Accounts(), FakeOrders()
    accounts.values[user_id] = LinkedAccount(user_id, "account", "ACTIVE")
    alpaca.positions[("account", "AAPL")] = Decimal("1000")
    context = OrderContext(
        uow,
        accounts,
        Controls(),
        Totp(),
        Quotes(),
        Assets(),
        Sessions(),
        BuyingPower(),
        alpaca,
        alpaca,
        BrokerLinks(),
        Notifications(),
        FakeClock(),
        OrderConfig(),
    )
    return context, user_id
