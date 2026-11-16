from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from acciones_ud.portfolio.adapters.outbound.alpaca.fake_positions import FakePositions
from acciones_ud.portfolio.adapters.outbound.commissions.reference_commission import (
    ReferenceCommission,
)
from acciones_ud.portfolio.application.portfolio_service import PortfolioService
from acciones_ud.portfolio.domain.model import LinkedAccount, Page, ViewSettings
from acciones_ud.portfolio.domain.pagination import decode, encode
from tests.support.clock import FakeClock


class Sources:
    def __init__(self):
        self.account = LinkedAccount(uuid4(), "private-account", "ACTIVE")
        self.rows = []
        self.reserved = {}
        self.prices = {}
        self.info = {}
        self.settings = ViewSettings()
        self.links = set()

    async def get(self, user_id):
        return self.account

    async def list(self, user_id, until=None, since=None, symbol=None):
        return [
            e
            for e in self.rows
            if e.user_id == user_id
            and (until is None or e.executed_at < until)
            and (since is None or e.executed_at >= since)
            and (symbol is None or e.symbol == symbol)
        ]

    async def list_page(self, user_id, since, until, symbol, cursor, size):
        rows = sorted(
            await self.list(user_id, until, since, symbol),
            key=lambda e: (e.executed_at, e.execution_id),
            reverse=True,
        )
        if cursor:
            rows = [e for e in rows if (e.executed_at, e.execution_id) < decode(cursor)]
        items = rows[:size]
        return Page(
            items,
            encode(items[-1].executed_at, items[-1].execution_id) if len(rows) > size else None,
        )

    async def active_share_reservations(self, user_id):
        return self.reserved

    async def last_price(self, symbol):
        return self.prices.get(symbol)

    async def classify(self, symbols):
        return {k: v for k, v in self.info.items() if k in symbols}

    async def is_linked(self, broker_id, investor_id):
        return (broker_id, investor_id) in self.links

    async def linked_investors(self, broker_id):
        return [i for b, i in self.links if b == broker_id]


class Views:
    def __init__(self, source):
        self.source = source

    async def get(self, user_id):
        return self.source.settings


def portfolio():
    source, alpaca, clock = Sources(), FakePositions(), FakeClock()
    # All generated ledger fixtures precede this snapshot.
    clock.set(datetime(2026, 6, 15, tzinfo=UTC))
    service = PortfolioService(
        source,
        alpaca,
        source,
        source,
        source,
        source,
        Views(source),
        ReferenceCommission(),
        source,
        clock,
    )
    return service, source, alpaca


class Reports:
    def __init__(self):
        self.values = {}

    async def add(self, report):
        if report.type in {"daily_summary", "monthly"} and await self.scheduled(
            report.owner_id, report.type, report.period
        ):
            return False
        self.values[report.id] = deepcopy(report)
        return True

    async def get(self, owner_id, id):
        value = self.values.get(id)
        return deepcopy(value) if value and value.owner_id == owner_id else None

    async def scheduled(self, owner_id, type, period):
        return next(
            (
                deepcopy(r)
                for r in self.values.values()
                if (r.owner_id, r.type, r.period) == (owner_id, type, period)
            ),
            None,
        )

    async def list_page(self, owner_id, type, cursor, size):
        rows = sorted(
            [
                deepcopy(r)
                for r in self.values.values()
                if r.owner_id == owner_id and (type is None or r.type == type)
            ],
            key=lambda r: (r.generated_at, str(r.id)),
            reverse=True,
        )
        if cursor:
            rows = [r for r in rows if (r.generated_at, str(r.id)) < decode(cursor)]
        selected = rows[:size]
        return Page(
            selected,
            encode(selected[-1].generated_at, str(selected[-1].id)) if len(rows) > size else None,
        )

    async def pending_notification(self):
        return [
            deepcopy(r)
            for r in self.values.values()
            if r.type in {"daily_summary", "monthly"} and r.notified_at is None
        ]

    async def mark_notified(self, id, at):
        self.values[id] = replace(self.values[id], notified_at=at)

    @asynccontextmanager
    async def work(self):
        yield self

    @property
    def reports(self):
        return self
