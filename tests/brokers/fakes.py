"""Transactional reference repositories and independent providers for MOD-06."""

import asyncio
import base64
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from acciones_ud.brokers.domain import entities as e
from acciones_ud.brokers.domain.errors import LinkAlreadyExistsError, ValidationError
from acciones_ud.brokers.domain.periods import link_overlaps
from acciones_ud.brokers.domain.ports import OrderCreated, OrderRejected


def page(values, at, ident, cursor, limit, ascending=False):
    if not 1 <= limit <= 100:
        raise ValidationError("page_size")

    def key(value):
        return getattr(value, at), getattr(value, ident)

    values = sorted(values, key=key, reverse=not ascending)
    if cursor:
        try:
            raw = base64.b64decode(cursor.encode(), altchars=b"-_", validate=True).decode()
            instant, identity = raw.split("|", 1)
            boundary = datetime.fromisoformat(instant), UUID(identity)
            if boundary[0].utcoffset() is None:
                raise ValueError()
        except (ValueError, UnicodeError):
            raise ValidationError("cursor") from None
        values = [v for v in values if (key(v) > boundary if ascending else key(v) < boundary)]
    selected = values[:limit]
    token = None
    if len(values) > limit:
        instant, identity = key(selected[-1])
        token = base64.urlsafe_b64encode(f"{instant.isoformat()}|{identity}".encode()).decode()
    return selected, token


class MemoryRepository:
    def __init__(self, keys=("id",), kind="", immutable=False):
        self.values = {}
        self.keys, self.kind, self.immutable = keys, kind, immutable
        self.fail_save = False

    def key(self, value):
        return tuple(getattr(value, key) for key in self.keys)

    async def get(self, *, for_update=False, **filters):
        return next(
            (
                v
                for v in self.values.values()
                if all(getattr(v, k) == expected for k, expected in filters.items())
            ),
            None,
        )

    async def list(self, **filters):
        return [
            v
            for v in self.values.values()
            if all(getattr(v, k) == expected for k, expected in filters.items())
        ]

    def validate(self, value):
        others = [v for k, v in self.values.items() if k != self.key(value)]
        if self.kind == "link" and value.status in {e.LinkStatus.REQUESTED, e.LinkStatus.ACTIVE}:
            if any(
                v.investor_id == value.investor_id
                and v.status
                in {
                    e.LinkStatus.REQUESTED,
                    e.LinkStatus.ACTIVE,
                }
                for v in others
            ):
                raise LinkAlreadyExistsError()
        if self.kind == "authorization" and value.revoked_at is None:
            if any(v.link_id == value.link_id and v.revoked_at is None for v in others):
                raise ValueError("Unique active authorization")
        if self.kind == "proposal":
            if (value.status == e.ProposalStatus.APPROVED) != (value.order_id is not None):
                raise ValueError("Approved requires an order")
            if value.order_id and any(v.order_id == value.order_id for v in others):
                raise ValueError("Unique proposal order")

    async def insert(self, value):
        if self.key(value) in self.values:
            raise ValueError("Duplicate key")
        self.validate(value)
        self.values[self.key(value)] = value
        return True

    async def save(self, value, **expected):
        if self.fail_save:
            raise RuntimeError("Injected repository failure")
        if self.immutable:
            raise ValueError("Immutable evidence")
        old = self.values.get(self.key(value))
        if old is None or any(getattr(old, k) != val for k, val in expected.items()):
            return False
        self.validate(value)
        self.values[self.key(value)] = value
        return True

    async def expired_batch(self, now, limit):
        expected = "requested" if self.kind == "link" else "sent"
        return sorted(
            (v for v in self.values.values() if v.status == expected and v.expires_at <= now),
            key=lambda v: (v.expires_at, v.id),
        )[:limit]


class MemoryLinks(MemoryRepository):
    def __init__(self):
        super().__init__(kind="link")

    async def open_for(self, investor_id, *, for_update=False):
        return next(
            (
                v
                for v in self.values.values()
                if v.investor_id == investor_id
                and v.status in {e.LinkStatus.REQUESTED, e.LinkStatus.ACTIVE}
            ),
            None,
        )

    async def page(self, investor_id, status, start, end, now, cursor, limit):
        values = []
        for v in self.values.values():
            effective = "expired" if v.status == "requested" and v.expires_at <= now else v.status
            if v.investor_id != investor_id or (status and effective != status):
                continue
            if start and end and not link_overlaps(v, start, end, now):
                continue
            values.append(v)
        return page(values, "requested_at", "id", cursor, limit)


class MemoryProposals(MemoryRepository):
    def __init__(self, links):
        super().__init__(kind="proposal")
        self.links = links

    async def page(self, user_id, role, status, start, end, now, cursor, limit):
        values = []
        for v in self.values.values():
            effective = "expired" if v.status == "sent" and v.expires_at <= now else v.status
            if getattr(v, f"{role}_id") != user_id or (status and effective != status):
                continue
            if role == "broker" and not any(
                link.id == v.link_id and link.status == "active"
                for link in self.links.values.values()
            ):
                continue
            if (start and v.created_at < start) or (end and v.created_at >= end):
                continue
            values.append(v)
        return page(values, "created_at", "id", cursor, limit)


class MemoryMessages(MemoryRepository):
    def __init__(self):
        super().__init__(immutable=True)

    async def page(self, proposal_id, cursor, limit):
        return page(
            await self.list(proposal_id=proposal_id), "created_at", "id", cursor, limit, True
        )


class MemoryRatings(MemoryRepository):
    def __init__(self):
        super().__init__(keys=("link_id",))

    async def upsert(self, value):
        previous = self.values.get(self.key(value))
        if previous:
            value = replace(value, created_at=previous.created_at)
        self.values[self.key(value)] = value
        return value

    async def page(self, broker_id, cursor, limit):
        return page(await self.list(broker_id=broker_id), "updated_at", "link_id", cursor, limit)


class MemoryProfiles(MemoryRepository):
    def __init__(self):
        super().__init__(keys=("broker_id",))

    async def upsert(self, value):
        self.values[self.key(value)] = value


class MemoryWork:
    def __init__(self):
        self.links = MemoryLinks()
        self.authorizations = MemoryRepository(kind="authorization")
        self.proposals = MemoryProposals(self.links)
        self.versions = MemoryRepository(keys=("proposal_id", "version"), immutable=True)
        self.decisions = MemoryRepository(immutable=True)
        self.messages = MemoryMessages()
        self.ratings = MemoryRatings()
        self.profiles = MemoryProfiles()
        self.events = MemoryRepository(immutable=True)

    async def lock_investor(self, investor_id):
        pass


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


class Clock:
    def __init__(self):
        self.at = datetime(2026, 11, 16, 12, tzinfo=UTC)

    def now(self):
        return self.at

    def advance(self, **kwargs):
        self.at += timedelta(**kwargs)


class Directory:
    def __init__(self, clock):
        self.clock, self.roles, self.brokers, self.names = clock, {}, {}, {}

    def add(self, user_id, role):
        self.roles.setdefault(user_id, set()).add(role)
        self.names[user_id] = str(user_id)
        if role == "broker":
            self.brokers[user_id] = e.BrokerIdentity(
                user_id, str(user_id), "Firm", "License", self.clock.now()
            )

    async def get_broker(self, user_id):
        return self.brokers.get(user_id) if await self.has_role(user_id, "broker") else None

    async def has_role(self, user_id, role):
        return role in self.roles.get(user_id, set())

    async def display_name(self, user_id):
        return self.names.get(user_id)

    async def all_active(self, exclude):
        return [
            v
            for k, v in self.brokers.items()
            if k != exclude and "broker" in self.roles.get(k, set())
        ]

    async def search(self, text, exclude, cursor, limit):
        from acciones_ud.brokers.domain.pagination import read_search_cursor

        values = sorted(
            (
                b
                for b in await self.all_active(exclude)
                if text.lower() in (b.name + " " + b.firm_name).lower()
            ),
            key=lambda b: (b.name.lower(), b.user_id),
        )
        if cursor:
            boundary = read_search_cursor(cursor)
            values = [b for b in values if (b.name.lower(), b.user_id) > boundary]
        return values[:limit]


class Accounts:
    def __init__(self):
        self.linked = set()

    async def has_linked_account(self, investor_id):
        return investor_id in self.linked


class Controls:
    def __init__(self):
        self.threshold = Decimal("10000")

    async def high_order_threshold_usd(self, investor_id):
        return self.threshold


class Totp:
    def __init__(self):
        self.calls = []

    async def verify(self, user_id, code):
        self.calls.append(user_id)
        return code == "123456"


class Quotes:
    def __init__(self):
        self.price, self.allowed = Decimal("100"), True

    async def tradable(self, symbol):
        return self.allowed and symbol == "AAPL"

    async def last_price(self, symbol):
        return self.price


class Requests:
    def __init__(self):
        self.values = set()

    async def broker_requested(self, investor_id):
        return investor_id in self.values


class Notifier:
    def __init__(self):
        self.calls, self.fail = [], False

    async def notify(self, user_id, event_type, payload):
        if self.fail:
            raise RuntimeError("Injected notification failure")
        self.calls.append((user_id, event_type, dict(payload)))


class Orders:
    def __init__(self):
        self.orders, self.creation_calls, self.query_calls = {}, [], []
        self.commands = {}
        self.failure = None
        self.rejection = None
        self.after_create = None

    async def create(self, command):
        self.creation_calls.append(command)
        key = (command.investor_id, f"proposal:{command.proposal_id}")
        if key in self.orders:
            if self.commands[key] != command:
                return OrderRejected("IDEMPOTENCY_CONFLICT")
            return OrderCreated(self.orders[key])
        if self.failure:
            raise self.failure
        if self.rejection:
            return OrderRejected(self.rejection)
        identity = self.orders.setdefault(key, uuid4())
        self.commands[key] = command
        await asyncio.sleep(0)
        if self.after_create:
            await self.after_create()
        return OrderCreated(identity)

    async def list_for_investor(self, investor_id, filters):
        self.query_calls.append((investor_id, filters))
        return {"items": [], "next_cursor": None}

    async def find_by_idempotency_key(self, investor_id, key, expected=None):
        self.query_calls.append((investor_id, key))
        if expected is not None and self.commands.get((investor_id, key)) != expected:
            return None
        return self.orders.get((investor_id, key))
