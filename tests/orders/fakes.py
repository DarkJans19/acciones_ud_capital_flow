import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from acciones_ud.orders.domain import model as m
from acciones_ud.orders.domain.pagination import decode, encode
from tests.wallet.fakes import MemoryRepository


class MemoryOrders(MemoryRepository):
    def __init__(self, events):
        super().__init__(unique=("client_order_id", "alpaca_order_id"))
        self.events = events

    async def change(self, value, previous, event):
        if not await self.save(value, status=previous.status, fully_filled=previous.fully_filled):
            return False
        await self.events.insert(event)
        return True

    async def daily_count(self, user_id, now):
        zone = ZoneInfo("America/New_York")
        today = now.astimezone(zone).date()
        return sum(
            v.user_id == user_id and v.created_at.astimezone(zone).date() == today
            for v in self.values
        )

    async def due(self, now):
        return [
            v
            for v in self.values
            if v.status in {m.OrderStatus.PENDING, m.OrderStatus.BROKER_SIGNED}
            and v.scheduled_for
            and v.scheduled_for <= now
            and not v.returned_for_changes
            and v.submit_attempted_at is None
        ][:100]

    async def page(self, user_id, status, symbol, start, end, page_size, cursor):
        values = [
            v
            for v in self.values
            if v.user_id == user_id
            and (status is None or v.status == status)
            and (symbol is None or v.symbol == symbol)
            and (start is None or v.created_at >= start)
            and (end is None or v.created_at <= end)
        ]
        values.sort(key=lambda v: (v.created_at, v.id), reverse=True)
        if cursor:
            at, ident = decode(cursor)
            values = [v for v in values if (v.created_at, v.id) < (at, ident)]
        selected = values[:page_size]
        return selected, encode(selected[-1].created_at, selected[-1].id) if len(
            values
        ) > page_size else None


class MemoryWork:
    def __init__(self):
        self.events = MemoryRepository()
        self.orders = MemoryOrders(self.events)
        self.legs = MemoryRepository(keys=("order_id", "role"))
        self.executions = MemoryRepository(keys=("alpaca_execution_id",))
        self.reservations = MemoryRepository(keys=("order_id",))
        self.reauthorizations = MemoryRepository()
        self.cancels = MemoryRepository()
        self.comments = MemoryRepository()
        self.keys = MemoryRepository(keys=("user_id", "idempotency_key"))
        self.schedule_changes = MemoryRepository(keys=("change_id",))
        self.cursors = MemoryRepository(keys=("alpaca_account_id",))

    async def lock_user(self, user_id):
        return None


class MemoryFactory:
    def __init__(self):
        self.work, self.lock = MemoryWork(), asyncio.Lock()

    @asynccontextmanager
    async def __call__(self):
        async with self.lock:
            snapshot = deepcopy(self.work.__dict__)
            try:
                yield self.work
            except BaseException:
                self.work.__dict__.update(snapshot)
                raise


class Accounts:
    def __init__(self):
        self.values = {}

    async def get(self, user_id):
        return self.values.get(user_id)


class Controls:
    def __init__(self):
        self.value = m.OrderControls()

    async def get(self, user_id):
        return self.value


class Assets:
    def __init__(self):
        self.values = {"AAPL": m.TradableAsset("AAPL", "NASDAQ", True, True, True)}

    async def get(self, symbol):
        return self.values.get(symbol)


class Quotes:
    def __init__(self):
        self.price = Decimal("10.00")

    async def current_price(self, symbol):
        return self.price


class Sessions:
    def __init__(self):
        self.open = True

    async def is_open(self, exchange, at):
        return self.open

    async def next_open(self, exchange, at):
        return m.SessionWindow(at + timedelta(hours=1), at + timedelta(hours=7))


class BuyingPower:
    def __init__(self):
        self.value = Decimal("1000.00")
        self.failure = None

    async def buying_power(self, account_id):
        if self.failure:
            raise self.failure
        return self.value


class Totp:
    def __init__(self):
        self.active, self.valid = True, True

    async def has_active_totp(self, user_id):
        return self.active

    async def verify(self, user_id, code, at):
        return self.valid


class Notifications:
    def __init__(self):
        self.values = []

    async def notify(self, user_id, event_type, payload):
        self.values.append((user_id, event_type, payload))


@dataclass
class BrokerLinks:
    links: dict[UUID, UUID] = field(default_factory=dict)

    async def reviewing_broker(self, investor_id):
        return self.links.get(investor_id)

    async def is_linked(self, broker_id, investor_id):
        return self.links.get(investor_id) == broker_id

    async def linked_investors(self, broker_id):
        return [investor for investor, broker in self.links.items() if broker == broker_id]
