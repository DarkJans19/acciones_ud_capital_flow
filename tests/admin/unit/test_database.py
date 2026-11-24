from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError

from acciones_ud.admin.adapters.outbound.orders.policy_adapters import (
    CommissionTermsAdapter,
    TradingGateAdapter,
)
from acciones_ud.admin.adapters.outbound.persistence.audit_trail_reader import AuditTrailReader
from acciones_ud.admin.adapters.outbound.persistence.repositories import (
    AuditWriter,
    FeeRepository,
    HaltRepository,
    ReportRepository,
    RestrictionRepository,
)
from acciones_ud.admin.domain import fees, reports
from acciones_ud.admin.domain.audit import build
from acciones_ud.admin.domain.model import (
    AccountRestriction,
    ComplianceReport,
    FeeVersion,
    TradingHalt,
)
from acciones_ud.orders.adapters.outbound.persistence.unit_of_work import build_work
from acciones_ud.orders.domain.model import Execution, OrderEvent
from acciones_ud.shared.domain.audit_entry import RequestMeta
from tests.brokers.unit.test_repository_db import parties
from tests.orders.support import make_order

pytestmark = pytest.mark.db


async def seed_evidence(session):
    owner, other = await parties(session)
    now = datetime.now(UTC)
    order = make_order(
        owner,
        created_at=now,
        updated_at=now,
        fee_version_id=fees.SEED_ID,
        commission_rate_pct=Decimal(2),
        platform_share_pct=Decimal(60),
    )
    work = build_work(session)
    await work.orders.insert(order)
    event = OrderEvent(
        uuid4(),
        order.id,
        None,
        "PENDING",
        "created",
        "investor",
        owner,
        now,
        {"totp_code": "secret", "safe": "visible"},
    )
    await work.events.insert(event)
    await work.executions.insert(
        Execution(str(uuid4()), order.id, Decimal(1), Decimal(10), now, now)
    )
    await session.execute(
        sa.text("""INSERT INTO auth_events(user_id,kind,result,occurred_at,ip_address)
        VALUES (:user,'mfa_verify','success',:now,'127.0.0.1')"""),
        {"user": owner, "now": now},
    )
    await session.execute(
        sa.text("""INSERT INTO broker_events
        (id,entity_type,entity_id,to_status,actor_type,actor_id,at,details)
        VALUES (:id,'link',:entity,'requested','investor',:user,:now,'{}')"""),
        {"id": uuid4(), "entity": uuid4(), "user": owner, "now": now},
    )
    await AuditWriter(session).append(
        build(
            "account_restricted",
            owner,
            "user",
            str(other),
            {
                "restriction_id": uuid4(),
                "restriction_type": "trading",
                "reason": "review",
                "evidence": {"text": "case", "refs": []},
            },
            now,
            RequestMeta("127.0.0.1", "request"),
        )
    )
    content = {"test": "content"}
    await ReportRepository(session).insert(
        ComplianceReport(
            uuid4(),
            owner,
            date.today(),
            date.today(),
            "atypical-v2",
            content,
            reports.digest(content),
            owner,
            now,
        )
    )
    return owner, other, order


async def rejected(session, statement, params=None):
    with pytest.raises(SQLAlchemyError):
        async with session.begin_nested():
            await session.execute(sa.text(statement), params or {})


async def test_all_immutable_sources_reject_update_delete_truncate(db_session):
    await seed_evidence(db_session)
    for table, column in (
        ("admin_audit_log", "target_id"),
        ("order_events", "cause"),
        ("order_executions", "price"),
        ("auth_events", "result"),
        ("broker_events", "to_status"),
        ("admin_compliance_reports", "rules_version"),
    ):
        await rejected(db_session, f"UPDATE {table} SET {column}={column}")
        await rejected(db_session, f"DELETE FROM {table}")
        await rejected(db_session, f"TRUNCATE {table} CASCADE")


async def test_conditional_guards_and_unique_restriction(db_session):
    actor, user = await parties(db_session)
    now = datetime.now(UTC)
    fee_repo, halt_repo, restriction_repo = (
        FeeRepository(db_session),
        HaltRepository(db_session),
        RestrictionRepository(db_session),
    )
    version = FeeVersion(
        uuid4(),
        "NASDAQ",
        1,
        Decimal("1.75"),
        Decimal(60),
        now + timedelta(days=1),
        "test",
        actor,
        now,
    )
    await fee_repo.insert(version)
    assert version in await fee_repo.all_versions()
    await rejected(
        db_session,
        "UPDATE admin_fee_versions SET commission_rate_pct=3 WHERE id=:id",
        {"id": version.id},
    )
    assert await fee_repo.cancel(version.id, now, actor, "cancel")
    assert not await fee_repo.cancel(version.id, now, actor, "cancel")
    await rejected(
        db_session,
        "UPDATE admin_fee_versions SET canceled_at=now() WHERE id=:id",
        {"id": version.id},
    )
    await rejected(
        db_session,
        "UPDATE admin_fee_versions SET canceled_at=now(),canceled_by=:actor,"
        "cancel_reason='invalid' WHERE id=:id",
        {"id": fees.SEED_ID, "actor": actor},
    )
    halt = TradingHalt(uuid4(), None, "test", now, None, actor, now)
    await halt_repo.insert(halt)
    assert await halt_repo.release(halt.id, now, actor, "release")
    assert not await halt_repo.release(halt.id, now, actor, "release")
    await rejected(
        db_session, "UPDATE admin_trading_halts SET reason='rewrite' WHERE id=:id", {"id": halt.id}
    )
    restriction = AccountRestriction(uuid4(), user, "trading", "test", "evidence", [], actor, now)
    await restriction_repo.insert(restriction)
    with pytest.raises(SQLAlchemyError):
        async with db_session.begin_nested():
            await restriction_repo.insert(replace(restriction, id=uuid4()))
    lifted = replace(
        restriction,
        lifted_at=now,
        lifted_by=actor,
        lift_reason="review complete",
        lift_evidence_text="evidence",
        lift_evidence_refs=[],
    )
    assert await restriction_repo.lift(lifted)
    assert not await restriction_repo.lift(lifted)
    await rejected(
        db_session,
        "UPDATE admin_account_restrictions SET lift_reason='rewrite' WHERE id=:id",
        {"id": restriction.id},
    )
    for table in ("admin_fee_versions", "admin_trading_halts", "admin_account_restrictions"):
        await rejected(db_session, f"DELETE FROM {table}")
        await rejected(db_session, f"TRUNCATE {table} CASCADE")


async def test_order_terms_cannot_be_rewritten_and_historical_orders_stay_unknown(db_session):
    owner, _, order = await seed_evidence(db_session)
    work = build_work(db_session)
    assert await work.orders.get(id=order.id) == order
    await rejected(
        db_session, "UPDATE orders SET commission_rate_pct=3 WHERE id=:id", {"id": order.id}
    )
    old = replace(make_order(owner), created_at=order.created_at, updated_at=order.updated_at)
    await work.orders.insert(old)
    await rejected(
        db_session,
        "UPDATE orders SET fee_version_id=:fee,commission_rate_pct=2,"
        "platform_share_pct=60 WHERE id=:id",
        {"id": old.id, "fee": fees.SEED_ID},
    )
    stored = await work.orders.get(id=old.id)
    assert stored.fee_version_id is None and stored.commission_rate_pct is None


async def test_audit_view_filters_sanitization_custody_and_policy_adapters(db_session, monkeypatch):
    from acciones_ud.shared.infrastructure import db

    owner, other, order = await seed_evidence(db_session)

    @asynccontextmanager
    async def sessions():
        yield db_session

    monkeypatch.setattr(db, "unit_of_work", sessions)
    reader = AuditTrailReader()
    start, end = order.created_at - timedelta(days=1), order.created_at + timedelta(days=1)
    values, cursor = [], None
    while True:
        page = await reader.page(start, end, {"user_id": owner}, cursor, 1)
        values.extend(page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert {r["source"] for r in values} == {"admin", "orders", "auth", "brokers"}
    assert len(values) == len({(r["source"], r["event_id"]) for r in values})
    assert "totp_code" not in str(values) and "secret" not in str(values)
    affected = await reader.page(start, end, {"user_id": other}, None, 100)
    assert len(affected["items"]) == 1 and affected["items"][0]["source"] == "admin"
    custody = await reader.order_custody(order.id)
    from acciones_ud.admin.adapters.inbound.http.schemas import OrderCustodyOut
    from acciones_ud.admin.domain.reports import canonical_value

    OrderCustodyOut.model_validate(canonical_value(custody))
    assert custody["order"]["fee_version_id"] == fees.SEED_ID
    assert len(custody["executions"]) == 1
    assert custody["created_by"] == owner
    assert (await CommissionTermsAdapter().terms("UNKNOWN", order.created_at)) == fees.SEED_TERMS
    assert (await TradingGateAdapter().check(owner, "NASDAQ", order.created_at)).allowed


async def test_rbac_seed_is_least_privilege(db_session):
    pairs = (
        await db_session.execute(
            sa.text(
                "SELECT role_code,permission_code FROM role_permissions "
                "WHERE permission_code LIKE 'admin:%'"
            )
        )
    ).all()
    assert {p for role, p in pairs if role == "auditor"} == {"admin:audit", "admin:compliance:read"}
    assert {p for role, p in pairs if role == "analyst"} == {"admin:bi"}
    assert all(role in {"administrator", "auditor", "analyst"} for role, p in pairs)


async def test_platform_filtered_ledger_volume_and_kpi_sources(db_session, monkeypatch):
    from acciones_ud.admin.adapters.outbound.sources import KpiSource, MarketCatalog, UserReader
    from acciones_ud.admin.domain.periods import Period
    from acciones_ud.orders.adapters.outbound.persistence.execution_repository import (
        ExecutionRepository,
    )
    from acciones_ud.orders.application.execution_ledger import LedgerFilters
    from acciones_ud.shared.infrastructure import db

    owner, other, order = await seed_evidence(db_session)
    now = order.created_at
    repo = ExecutionRepository(db_session)
    start, end = now - timedelta(days=1), now + timedelta(days=1)
    rows, token = await repo.list_platform_page(
        start,
        end,
        None,
        1000,
        LedgerFilters(user_id=owner, market="NASDAQ", symbol="AAPL", investor_ids=(owner,)),
    )
    assert len(rows) == 1 and token is None
    assert rows[0].fee_version_id == fees.SEED_ID
    assert not (
        await repo.list_platform_page(start, end, None, 1000, LedgerFilters(investor_ids=(other,)))
    )[0]
    assert (await repo.volume(start, end))[0]["gross_amount"] == 10

    @asynccontextmanager
    async def sessions():
        yield db_session

    monkeypatch.setattr(db, "unit_of_work", sessions)
    inputs = await KpiSource().inputs(Period(now.date() - timedelta(days=1), now.date()), now)
    assert inputs["registered_users"] >= 2 and inputs["active_users"] == 1
    assert inputs["active_subscriptions"] == 0
    assert (await UserReader().summary(owner, now))["id"] == owner
    assert len(await MarketCatalog().markets()) == 7


def test_production_evidence_repositories_expose_no_mutators():
    from acciones_ud.brokers.adapters.outbound.persistence.event_repository import (
        BrokerEventRepository,
    )
    from acciones_ud.shared.infrastructure.evidence_repository import EvidenceRepository

    for repository in (EvidenceRepository, BrokerEventRepository, AuditWriter, ReportRepository):
        assert not hasattr(repository, "save")
        assert not hasattr(repository, "delete")


async def test_concurrent_fee_and_halt_requests_commit_once(migrated_database):
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from acciones_ud.admin.adapters.outbound.persistence.unit_of_work import (
        build_work as admin_work,
    )
    from acciones_ud.admin.application.fee_service import FeeService
    from acciones_ud.admin.application.halt_service import HaltService
    from acciones_ud.shared.domain.errors import AppError, ErrorCode
    from acciones_ud.shared.infrastructure.db import build_engine
    from tests.admin.fakes import Markets, setup

    engine = build_engine(migrated_database)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    _, clock, _, step = setup()
    clock.set(datetime.now(UTC))
    async with factory() as session:
        actor = await session.scalar(sa.text("SELECT id FROM users LIMIT 1"))
        latest = await session.scalar(
            sa.text(
                "SELECT COALESCE(max(version_no),0) FROM admin_fee_versions "
                "WHERE market_code='NYSE'"
            )
        )

    @asynccontextmanager
    async def uow():
        async with factory() as session, session.begin():
            yield admin_work(session)

    try:
        service = FeeService(uow, Markets(), step, clock)
        future = clock.now() + timedelta(days=1)
        results = await asyncio.gather(
            *[
                service.create(
                    "NYSE",
                    Decimal(2),
                    Decimal(60),
                    future,
                    "Concurrent test",
                    latest,
                    actor,
                    "123456",
                    RequestMeta(),
                )
                for _ in range(2)
            ],
            return_exceptions=True,
        )
        assert sum(isinstance(r, dict) for r in results) == 1
        assert [r.code for r in results if isinstance(r, AppError)] == [
            ErrorCode.FEE_VERSION_CONFLICT
        ]
        halts = HaltService(uow, Markets(), step, clock)
        results = await asyncio.gather(
            *[
                halts.activate(
                    "NYSE",
                    "Concurrent incident",
                    future,
                    future + timedelta(hours=1),
                    actor,
                    "123456",
                    RequestMeta(),
                )
                for _ in range(2)
            ],
            return_exceptions=True,
        )
        assert sum(isinstance(r, dict) for r in results) == 1
        assert [r.code for r in results if isinstance(r, AppError)] == [
            ErrorCode.TRADING_HALT_OVERLAP
        ]
        async with factory() as session:
            count = await session.scalar(
                sa.text(
                    "SELECT count(*) FROM admin_audit_log "
                    "WHERE action IN ('fee_version_created','trading_halt_activated')"
                )
            )
            assert count == 2
    finally:
        await engine.dispose()


async def test_schedule_change_audit_dispatch_and_history_on_postgres(db_session, monkeypatch):
    from datetime import time

    from fastapi import FastAPI

    from acciones_ud.admin.adapters.inbound.http.schemas import ScheduleChangeOut
    from acciones_ud.admin.adapters.outbound.persistence.unit_of_work import (
        admin_uow,
    )
    from acciones_ud.admin.adapters.outbound.schedule_adapters import OrderScheduleChanges
    from acciones_ud.admin.application.schedule_change_dispatcher import ScheduleChangeDispatcher
    from acciones_ud.admin.domain.periods import Period
    from acciones_ud.admin.domain.reports import canonical_value
    from acciones_ud.market_data.application.schedule_admin import ScheduleAdminService
    from acciones_ud.market_data.composition import market_uow
    from acciones_ud.market_data.domain.schedule_audit import AuditActor
    from acciones_ud.orders.application.schedule_change import ScheduleChangeService
    from acciones_ud.shared.infrastructure import db
    from tests.orders.support import make_context
    from tests.support.clock import FakeClock

    actor = await db_session.scalar(sa.text("SELECT id FROM users LIMIT 1"))
    now = datetime.now(UTC)
    clock = FakeClock(now)
    order = replace(make_order(actor), created_at=now, updated_at=now)
    await build_work(db_session).orders.insert(order)

    @asynccontextmanager
    async def sessions():
        async with db_session.begin_nested():
            yield db_session

    @asynccontextmanager
    async def orders_uow():
        async with sessions():
            yield build_work(db_session)

    monkeypatch.setattr(db, "unit_of_work", sessions)
    context, _ = make_context()
    app = FastAPI()
    app.state.order_schedule_change_port = ScheduleChangeService(replace(context, uow=orders_uow))

    class Listener:
        def __init__(self):
            self.ids = []

        def changed(self, ident):
            self.ids.append(ident)

    class Notifier:
        def __init__(self):
            self.sent = []

        async def recipients(self):
            return [actor]

        async def notify(self, user, payload):
            self.sent.append((user, payload))

    listener, notifier = Listener(), Notifier()
    service = ScheduleAdminService(
        market_uow, AuditActor(actor, RequestMeta("127.0.0.1", "request")), listener, clock
    )
    await service.set_default("NASDAQ", time(9, 30), time(16))
    assert len(listener.ids) == 1
    dispatcher = ScheduleChangeDispatcher(admin_uow, OrderScheduleChanges(app), notifier, clock)
    await dispatcher.dispatch(listener.ids[0])
    await dispatcher.dispatch(listener.ids[0])
    assert len(notifier.sent) == 1
    current = await build_work(db_session).orders.get(id=order.id)
    assert current.status == "IN_REVIEW"
    period = Period(now.date() - timedelta(days=1), now.date() + timedelta(days=1))
    history = await dispatcher.history("NASDAQ", period, None, 20)
    assert history["items"][0]["affected_orders"] == 1
    assert history["items"][0]["dispatch_status"] == "dispatched"
    ScheduleChangeOut.model_validate(canonical_value(history["items"][0]))
