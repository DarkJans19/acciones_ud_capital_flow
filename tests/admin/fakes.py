import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from acciones_ud.admin.domain.fees import SEED_ID
from acciones_ud.admin.domain.model import FeeVersion
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from tests.support.clock import FakeClock


class Fees:
    def __init__(self):
        self.rows = [
            FeeVersion(
                SEED_ID,
                None,
                1,
                Decimal("2.0000"),
                Decimal("60.00"),
                datetime(1970, 1, 1, tzinfo=UTC),
                "seed",
                None,
                datetime(1970, 1, 1, tzinfo=UTC),
            )
        ]

    async def lock_scope(self, scope):
        pass

    async def all_versions(self):
        return list(self.rows)

    async def insert(self, value):
        assert not any(
            v.scope == value.scope
            and (
                v.version_no == value.version_no
                or (v.effective_from == value.effective_from and v.canceled_at is None)
            )
            for v in self.rows
        )
        self.rows.append(value)

    async def get_for_update(self, ident):
        return next((v for v in self.rows if v.id == ident), None)

    async def cancel(self, ident, at, actor, reason):
        old = await self.get_for_update(ident)
        if old is None or old.canceled_at:
            return False
        self.rows[self.rows.index(old)] = replace(
            old, canceled_at=at, canceled_by=actor, cancel_reason=reason
        )
        return True


class Halts:
    def __init__(self):
        self.rows = []

    async def lock_scope(self, scope):
        pass

    async def all(self):
        return list(self.rows)

    async def insert(self, value):
        self.rows.append(value)

    async def get_for_update(self, ident):
        return next((v for v in self.rows if v.id == ident), None)

    async def release(self, ident, at, actor, reason):
        old = await self.get_for_update(ident)
        if old is None or old.released_at:
            return False
        self.rows[self.rows.index(old)] = replace(
            old, released_at=at, released_by=actor, release_reason=reason
        )
        return True


class Restrictions:
    def __init__(self):
        self.rows = []

    async def lock_user(self, user):
        pass

    async def all(self, user_id=None):
        return [r for r in self.rows if user_id is None or r.user_id == user_id]

    async def insert(self, value):
        assert not any(r.user_id == value.user_id and r.lifted_at is None for r in self.rows)
        self.rows.append(value)

    async def get_for_update(self, ident):
        return next((v for v in self.rows if v.id == ident), None)

    async def lift(self, value):
        old = await self.get_for_update(value.id)
        if old is None or old.lifted_at:
            return False
        self.rows[self.rows.index(old)] = value
        return True


class Audit:
    def __init__(self):
        self.rows, self.fail = [], False

    async def append(self, record):
        if self.fail:
            raise AppError(503, ErrorCode.DATABASE_UNAVAILABLE, "Audit write failed")
        self.rows.append(record)


class Reports:
    def __init__(self):
        self.rows = []

    async def insert(self, value):
        self.rows.append(deepcopy(value))

    async def get(self, ident):
        return next((r for r in self.rows if r.id == ident), None)

    async def for_user(self, user):
        return [r for r in self.rows if r.user_id == user]


class Snapshots:
    def __init__(self):
        self.rows = {}

    async def get(self, period, version):
        return self.rows.get((period.from_, period.to, version))

    async def upsert(self, value):
        self.rows[(value.period_from, value.period_to, value.definitions_version)] = deepcopy(value)


class Dispatches:
    def __init__(self):
        self.rows, self.sources = {}, {}

    async def lock(self, ident):
        pass

    async def get(self, ident):
        return self.rows.get(ident)

    async def source(self, ident):
        return self.sources.get(ident)

    async def insert(self, record):
        assert record["audit_entry_id"] not in self.rows
        self.rows[record["audit_entry_id"]] = record

    async def undispatched(self):
        return [i for i in self.sources if i not in self.rows]


class MemoryFactory:
    def __init__(self):
        self.work = SimpleNamespace(
            fees=Fees(),
            halts=Halts(),
            restrictions=Restrictions(),
            audit=Audit(),
            reports=Reports(),
            snapshots=Snapshots(),
            dispatches=Dispatches(),
        )
        self.lock = asyncio.Lock()

    @asynccontextmanager
    async def __call__(self):
        async with self.lock:
            before = deepcopy(self.work)
            try:
                yield self.work
            except BaseException:
                self.work = before
                raise


class Markets:
    async def markets(self):
        return [{"code": "NASDAQ"}, {"code": "NYSE"}]

    async def exchange_of(self, symbol):
        return "NASDAQ" if symbol == "AAPL" else None


class Totp:
    def __init__(self):
        self.enrolled, self.valid = True, True
        self.calls = 0

    async def has_active_totp(self, actor):
        return self.enrolled

    async def verify(self, actor, code, now):
        self.calls += 1
        return self.valid and code == "123456"


class Users:
    async def summary(self, user, at):
        return {"id": user, "created_at": at, "roles": ["investor"]}

    async def display_names(self, ids):
        return {ident: "Investor" for ident in ids}


class Ledger:
    def __init__(self, rows=()):
        self.rows = list(rows)

    async def iterate(self, start, end, filters=None):
        for row in self.rows:
            if start <= row.executed_at < end:
                yield row

    async def volume(self, start, end):
        groups = {}
        async for e in self.iterate(start, end):
            row = groups.setdefault(
                (e.exchange, e.side),
                {
                    "exchange": e.exchange,
                    "side": e.side,
                    "gross_amount": Decimal(0),
                    "executions_count": 0,
                },
            )
            row["gross_amount"] += e.qty * e.price
            row["executions_count"] += 1
        return list(groups.values())


def setup():
    from acciones_ud.admin.application.step_up import StepUp

    uow, clock, actor, totp = MemoryFactory(), FakeClock(), uuid4(), Totp()
    return uow, clock, actor, StepUp(totp, clock)
