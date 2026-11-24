from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import asdict
from datetime import time
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Request

from acciones_ud.admin import composition as admin
from acciones_ud.admin.adapters.outbound.portfolio.official_commission import OfficialCommission
from acciones_ud.main import create_app
from acciones_ud.market_data.composition import schedule_admin_service
from acciones_ud.market_data.domain.entities import Market
from acciones_ud.market_data.domain.schedule_audit import AuditActor
from acciones_ud.portfolio.adapters.outbound.commissions.reference_commission import (
    ReferenceCommission,
)
from acciones_ud.portfolio.composition import InstalledCommission
from acciones_ud.portfolio.domain.model import ExecutionRecord
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from acciones_ud.shared.domain.trading import CommissionTerms, GateDecision
from tests.admin.fakes import Audit, setup
from tests.admin.property.test_rules import execution
from tests.support.market_fakes import MemoryMarkets


async def test_five_adapters_are_installed_and_resolved_after_startup(api_settings):
    app = create_app(api_settings)
    for name in (
        "order_commission_terms",
        "order_trading_gate",
        "portfolio_commission_port",
        "brokers_commission_terms",
        "market_schedule_change_listener",
    ):
        assert getattr(app.state, name) is not None
    assert isinstance(app.state.portfolio_commission_port, OfficialCommission)
    await admin.startup(app)

    class Terms:
        async def terms(self, exchange, at):
            return CommissionTerms(None, Decimal(7), Decimal(60))

    class Gate:
        async def check(self, user, exchange, at):
            return GateDecision(False, "TRADING_HALTED")

    class ProposalTerms:
        async def rate_pct(self, symbol, at):
            return Decimal(7)

    app.state.order_commission_terms = Terms()
    app.state.order_trading_gate = Gate()
    app.state.brokers_commission_terms = ProposalTerms()
    now = app.state.order_context.clock.now()
    assert (
        await app.state.order_context.commission_terms.terms("NASDAQ", now)
    ).commission_rate_pct == 7
    assert not (await app.state.order_context.trading_gate.check(uuid4(), "NASDAQ", now)).allowed
    assert await app.state.brokers_context.commission_terms.rate_pct("AAPL", now) == 7
    record = ExecutionRecord(**asdict(execution(1, Decimal(10))))
    wrapped = InstalledCommission(app, ReferenceCommission())
    assert wrapped.commission(record).source == "official"
    del app.state.portfolio_commission_port
    assert wrapped.commission(record).source == "reference"
    request = Request({"type": "http", "app": app})
    service = schedule_admin_service(request, AuditActor(uuid4()))
    assert service.listener is app.state.market_schedule_change_listener
    await admin.shutdown(app)


async def test_schedule_audit_is_atomic_and_listener_runs_after_commit():
    from acciones_ud.market_data.application.schedule_admin import ScheduleAdminService

    _, clock, actor, _ = setup()
    market = MemoryMarkets([Market("NASDAQ", "Nasdaq")])
    audit = Audit()
    committed, notifications = [], []

    @asynccontextmanager
    async def uow():
        before = deepcopy(market.__dict__)
        try:
            yield SimpleNamespace(markets=market, schedule_audit=audit)
        except BaseException:
            market.__dict__ = before
            raise
        else:
            committed.append(True)

    class Listener:
        def changed(self, entry_id):
            assert committed
            notifications.append(entry_id)

    service = ScheduleAdminService(uow, AuditActor(actor), Listener(), clock)
    await service.set_default("NASDAQ", time(9, 30), time(16))
    assert audit.rows[0].id == notifications[0]
    assert audit.rows[0].payload["before"]["default_open_time"] is None
    assert audit.rows[0].payload["after"]["default_open_time"] == time(9, 30)
    audit.fail = True
    with pytest.raises(AppError) as caught:
        await service.set_default("NASDAQ", time(10), time(15))
    assert caught.value.code == ErrorCode.DATABASE_UNAVAILABLE
    assert market.items["NASDAQ"].default_open_time == time(9, 30)
    assert len(notifications) == 1


def test_domain_and_application_import_without_framework_or_database():
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import importlib
import pathlib
import sys
base = pathlib.Path('src/acciones_ud/admin')
for layer in ('domain','application'):
    for path in (base / layer).glob('*.py'):
        importlib.import_module('acciones_ud.admin.' + layer + '.' + path.stem)
assert 'fastapi' not in sys.modules
assert 'sqlalchemy' not in sys.modules
assert 'pydantic' not in sys.modules
""",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
