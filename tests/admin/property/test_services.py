import asyncio
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from acciones_ud.admin.application.fee_service import FeeService
from acciones_ud.admin.application.halt_service import HaltService
from acciones_ud.admin.application.restriction_service import RestrictionService
from acciones_ud.admin.application.schedule_change_dispatcher import ScheduleChangeDispatcher
from acciones_ud.admin.domain import fees, halts
from acciones_ud.shared.domain.audit_entry import RequestMeta
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from tests.admin.fakes import Markets, Users, setup

META = RequestMeta("127.0.0.1", "test-request-id")


class FeeMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.uow, self.clock, self.actor, step = setup()
        self.service = FeeService(self.uow, Markets(), step, self.clock)
        self.created, self.latest, self.audit_count = [], 0, 0

    @rule(offset=st.integers(1, 1000), correct=st.booleans())
    def create(self, offset, correct):
        expected = self.latest if correct else self.latest + 1
        at = self.clock.now() + timedelta(seconds=offset)
        duplicate = any(
            v.effective_from == at and v.canceled_at is None
            for v in self.uow.work.fees.rows
            if v.scope == "NASDAQ"
        )
        try:
            result = asyncio.run(
                self.service.create(
                    "NASDAQ",
                    Decimal(2),
                    Decimal(60),
                    at,
                    "test",
                    expected,
                    self.actor,
                    "123456",
                    META,
                )
            )
        except AppError as exc:
            assert not correct or duplicate
            assert exc.code == ErrorCode.FEE_VERSION_CONFLICT
        else:
            assert correct and not duplicate
            self.latest += 1
            self.audit_count += 1
            self.created.append(result["id"])

    @rule(index=st.integers(0, 100))
    def cancel(self, index):
        if not self.created:
            return
        ident = self.created[index % len(self.created)]
        value = next(v for v in self.uow.work.fees.rows if v.id == ident)
        allowed = fees.can_cancel(value, self.clock.now())
        try:
            asyncio.run(self.service.cancel("NASDAQ", ident, "cancel", self.actor, "123456", META))
        except AppError as exc:
            assert not allowed
            assert exc.code == ErrorCode.FEE_VERSION_NOT_CANCELABLE
        else:
            assert allowed
            self.audit_count += 1

    @rule(seconds=st.integers(1, 300))
    def tick(self, seconds):
        self.clock.advance(seconds)

    @invariant()
    def consistency(self):
        rows = self.uow.work.fees.rows
        assert len(self.uow.work.audit.rows) == self.audit_count
        assert {v.version_no for v in rows if v.scope == "NASDAQ"} == set(range(1, self.latest + 1))
        assert fees.resolve_terms(rows, "NASDAQ", self.clock.now()) is not None


# Feature: admin-mod-07, Property 3: Secuencias de operaciones sobre la matriz
TestFeeSequences = FeeMachine.TestCase
TestFeeSequences.settings = settings(max_examples=100, stateful_step_count=20)


class HaltMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.uow, self.clock, self.actor, step = setup()
        self.service = HaltService(self.uow, Markets(), step, self.clock)
        self.count = 0

    @rule(scope=st.sampled_from(["global", "NASDAQ"]), duration=st.integers(1, 1000))
    def activate(self, scope, duration):
        start, end = self.clock.now(), self.clock.now() + timedelta(seconds=duration)
        conflict = any(
            h.scope == scope
            and h.released_at is None
            and halts.overlaps(start, end, h.starts_at, h.ends_at)
            for h in self.uow.work.halts.rows
        )
        try:
            asyncio.run(
                self.service.activate(scope, "incident", None, end, self.actor, "123456", META)
            )
        except AppError as exc:
            assert conflict and exc.code == ErrorCode.TRADING_HALT_OVERLAP
        else:
            assert not conflict
            self.count += 1

    @rule(index=st.integers(0, 100))
    def release(self, index):
        values = self.uow.work.halts.rows
        if not values:
            return
        value = values[index % len(values)]
        allowed = halts.effective_status(value, self.clock.now()) in {"active", "scheduled"}
        try:
            asyncio.run(self.service.release(value.id, "resolved", self.actor, "123456", META))
        except AppError as exc:
            assert not allowed and exc.code == ErrorCode.TRADING_HALT_NOT_RELEASABLE
        else:
            assert allowed
            self.count += 1

    @rule(seconds=st.integers(1, 2000))
    def tick(self, seconds):
        self.clock.advance(seconds)

    @invariant()
    def consistency(self):
        values = [h for h in self.uow.work.halts.rows if h.released_at is None]
        for i, a in enumerate(values):
            for b in values[i + 1 :]:
                assert a.scope != b.scope or not halts.overlaps(
                    a.starts_at, a.ends_at, b.starts_at, b.ends_at
                )
        assert len(self.uow.work.audit.rows) == self.count


# Feature: admin-mod-07, Property 7: Secuencias de activación y liberación de interruptores
TestHaltSequences = HaltMachine.TestCase
TestHaltSequences.settings = settings(max_examples=100, stateful_step_count=20)


class RestrictionMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.uow, self.clock, self.actor, step = setup()
        self.service = RestrictionService(self.uow, Users(), step, self.clock)
        self.users, self.count = [uuid4(), uuid4(), self.actor], 0

    @rule(index=st.integers(0, 2))
    def restrict(self, index):
        user = self.users[index]
        active = any(
            r.user_id == user and r.lifted_at is None for r in self.uow.work.restrictions.rows
        )
        try:
            asyncio.run(
                self.service.restrict(user, "review", "evidence", [], self.actor, "123456", META)
            )
        except AppError as exc:
            assert user == self.actor or active
            assert exc.code == (
                ErrorCode.VALIDATION_ERROR
                if user == self.actor
                else ErrorCode.RESTRICTION_ALREADY_ACTIVE
            )
        else:
            assert user != self.actor and not active
            self.count += 1

    @rule(index=st.integers(0, 50))
    def lift(self, index):
        rows = self.uow.work.restrictions.rows
        if not rows:
            return
        row = rows[index % len(rows)]
        try:
            asyncio.run(
                self.service.lift(
                    row.id, "review complete", "evidence", [], self.actor, "123456", META
                )
            )
        except AppError as exc:
            assert row.lifted_at and exc.code == ErrorCode.RESTRICTION_NOT_ACTIVE
        else:
            assert row.lifted_at is None
            self.count += 1

    @invariant()
    def consistency(self):
        active = [r.user_id for r in self.uow.work.restrictions.rows if r.lifted_at is None]
        assert len(active) == len(set(active))
        assert len(self.uow.work.audit.rows) == self.count
        for user in self.users:
            restriction = next(
                (
                    r
                    for r in self.uow.work.restrictions.rows
                    if r.user_id == user and r.lifted_at is None
                ),
                None,
            )
            assert halts.gate([], restriction, "NASDAQ", self.clock.now()).allowed == (
                user not in active
            )


# Feature: admin-mod-07, Property 13: Restricciones de cuenta únicas
TestRestrictionSequences = RestrictionMachine.TestCase
TestRestrictionSequences.settings = settings(max_examples=100, stateful_step_count=20)


class DispatchMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.uow, self.clock, self.actor, _ = setup()
        self.ident = uuid4()
        self.uow.work.dispatches.sources[self.ident] = {
            "target_id": "NASDAQ",
            "payload": {},
            "id": self.ident,
        }
        self.orders, self.notifier = self.Orders(), self.Notifier()
        self.service = ScheduleChangeDispatcher(self.uow, self.orders, self.notifier, self.clock)

    class Orders:
        fail, calls, applied = False, 0, False

        async def apply(self, source, now):
            self.calls += 1
            if self.fail:
                raise AppError(503, ErrorCode.DATABASE_UNAVAILABLE, "Unavailable")
            self.applied = True
            return 3

    class Notifier:
        def __init__(self):
            self.sent = []
            self.users = [uuid4(), uuid4()]

        async def recipients(self):
            return self.users

        async def notify(self, user, payload):
            self.sent.append((user, payload["change_id"]))

    @rule(fail=st.booleans())
    def dispatch(self, fail):
        self.orders.fail = fail
        before = self.orders.calls
        marker = self.ident in self.uow.work.dispatches.rows
        try:
            asyncio.run(self.service.dispatch(self.ident))
        except AppError:
            assert fail and not marker
        if marker:
            assert self.orders.calls == before

    @invariant()
    def consistency(self):
        assert len(self.notifier.sent) == len(set(self.notifier.sent))
        assert len(self.uow.work.dispatches.rows) <= 1
        if self.uow.work.dispatches.rows:
            assert self.orders.applied


# Feature: admin-mod-07, Property 12: Despacho idempotente de cambios de horario
TestDispatchSequences = DispatchMachine.TestCase
TestDispatchSequences.settings = settings(max_examples=100, stateful_step_count=15)


# Feature: admin-mod-07, Property 10: Atomicidad entre la operación y su Audit_Entry
@settings(max_examples=100)
@given(st.sampled_from(["create_fee", "cancel_fee", "activate", "release", "restrict", "lift"]))
def test_atomic_audit_rollback(operation):
    async def run():
        uow, clock, actor, step = setup()
        fee = FeeService(uow, Markets(), step, clock)
        halt = HaltService(uow, Markets(), step, clock)
        restriction = RestrictionService(uow, Users(), step, clock)
        user = uuid4()
        if operation == "cancel_fee":
            item = await fee.create(
                "NASDAQ",
                Decimal(2),
                Decimal(60),
                clock.now() + timedelta(days=1),
                "test",
                0,
                actor,
                "123456",
                META,
            )
        elif operation == "release":
            item = await halt.activate("global", "test", None, None, actor, "123456", META)
        elif operation == "lift":
            item = await restriction.restrict(user, "test", "", [], actor, "123456", META)
        before = (
            list(uow.work.fees.rows),
            list(uow.work.halts.rows),
            list(uow.work.restrictions.rows),
            list(uow.work.audit.rows),
        )
        uow.work.audit.fail = True
        with pytest.raises(AppError) as caught:
            if operation == "create_fee":
                await fee.create(
                    "NASDAQ", Decimal(2), Decimal(60), None, "test", 0, actor, "123456", META
                )
            elif operation == "cancel_fee":
                await fee.cancel("NASDAQ", item["id"], "test", actor, "123456", META)
            elif operation == "activate":
                await halt.activate("global", "test", None, None, actor, "123456", META)
            elif operation == "release":
                await halt.release(item["id"], "test", actor, "123456", META)
            elif operation == "restrict":
                await restriction.restrict(user, "test", "", [], actor, "123456", META)
            else:
                await restriction.lift(item["id"], "test", "", [], actor, "123456", META)
        assert caught.value.code == ErrorCode.DATABASE_UNAVAILABLE
        assert before == (
            uow.work.fees.rows,
            uow.work.halts.rows,
            uow.work.restrictions.rows,
            uow.work.audit.rows,
        )

    asyncio.run(run())
