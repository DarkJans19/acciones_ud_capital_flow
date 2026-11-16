from uuid import uuid4

from acciones_ud.brokers.application.context import BrokerContext
from acciones_ud.brokers.domain.entities import BrokersConfig
from tests.brokers import fakes as f


def context():
    clock, uow = f.Clock(), f.MemoryFactory()
    directory, orders = f.Directory(clock), f.Orders()
    return BrokerContext(
        uow,
        directory,
        f.Requests(),
        f.Accounts(),
        f.Controls(),
        f.Totp(),
        f.Quotes(),
        orders,
        orders,
        f.Notifier(),
        clock,
        BrokersConfig(),
    )


def actors(ctx):
    investor, broker = uuid4(), uuid4()
    ctx.directory.add(investor, "investor")
    ctx.directory.add(broker, "broker")
    ctx.accounts.linked.add(investor)
    return investor, broker
