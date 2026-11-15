import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from acciones_ud.wallet.domain.model import LinkedAccount


@dataclass
class MemoryRepository:
    keys: tuple[str, ...] = ("id",)
    unique: tuple[str, ...] = ()
    values: list[Any] = field(default_factory=list)

    async def get(self, **filters):
        return next(
            (v for v in self.values if all(getattr(v, k) == x for k, x in filters.items())), None
        )

    async def list(self, **filters):
        return [v for v in self.values if all(getattr(v, k) == x for k, x in filters.items())]

    async def insert(self, value):
        if await self.get(**{k: getattr(value, k) for k in self.keys}):
            return False
        for k in self.unique:
            if getattr(value, k) is not None and await self.get(**{k: getattr(value, k)}):
                return False
        self.values.append(value)
        return True

    async def save(self, value, **expected):
        current = await self.get(**{k: getattr(value, k) for k in self.keys})
        if current is None or not all(getattr(current, k) == x for k, x in expected.items()):
            return False
        self.values[self.values.index(current)] = value
        return True

    async def delete(self, **filters):
        self.values = [
            v for v in self.values if not all(getattr(v, k) == x for k, x in filters.items())
        ]


class Accounts:
    def __init__(self):
        self.values = {}

    async def get(self, user_id):
        return self.values.get(user_id)

    async def list_active(self):
        return [v for v in self.values.values() if v.is_active]


class Premium:
    def __init__(self):
        self.values = {}

    async def set_premium(self, user_id, value):
        self.values[user_id] = value


class MemoryWork:
    def __init__(self):
        self.banks = MemoryRepository(unique=("alpaca_relationship_id",))
        self.transfers = MemoryRepository(unique=("alpaca_transfer_id",))
        self.keys = MemoryRepository(keys=("user_id", "idempotency_key"))
        self.subscriptions = MemoryRepository(unique=("stripe_subscription_id",))
        self.payments = MemoryRepository(unique=("stripe_invoice_id",))
        self.events = MemoryRepository(keys=("event_id",))
        self.markers = MemoryRepository(keys=("source", "external_id"))
        self.cursors = MemoryRepository(keys=("alpaca_account_id",))
        self.accounts = Accounts()
        self.premium = Premium()

    async def lock_user(self, user_id):
        # The fake factory serializes transactions, including this investor's work.
        return None


class MemoryFactory:
    def __init__(self):
        self.work = MemoryWork()
        self.lock = asyncio.Lock()

    @asynccontextmanager
    async def __call__(self):
        async with self.lock:
            snapshot = deepcopy(self.work.__dict__)
            try:
                yield self.work
            except BaseException:
                self.work.__dict__.update(snapshot)
                raise

    def link(self, user_id, account_id="account", status="ACTIVE"):
        self.work.accounts.values[user_id] = LinkedAccount(user_id, account_id, status)


class Notifications:
    def __init__(self):
        self.values = []

    async def notify(self, user_id, payload):
        self.values.append((user_id, payload))
