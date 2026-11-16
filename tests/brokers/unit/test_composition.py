import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from acciones_ud.brokers import composition as brokers
from acciones_ud.main import create_app
from acciones_ud.orders import composition as orders
from acciones_ud.portfolio import composition as portfolio


async def test_same_membership_port_is_used_by_orders_and_portfolio_after_startup(
    api_settings, monkeypatch
):
    app = create_app(api_settings)
    adapter = app.state.order_broker_link
    assert adapter is app.state.portfolio_broker_clients
    monkeypatch.setattr(adapter, "is_linked", AsyncMock(return_value=True))
    investor, broker = uuid4(), uuid4()
    await orders.startup(app)
    await portfolio.startup(app)
    await brokers.startup(app)
    try:
        assert app.state.order_context.brokers.port is adapter
        assert app.state.portfolio_service.brokers.port is adapter
        assert await app.state.order_context.brokers.is_linked(broker, investor)
        assert await app.state.portfolio_service.brokers.is_linked(broker, investor)
        assert adapter.is_linked.await_count == 2
        assert app.state.brokers_expiry_job is None
    finally:
        await brokers.shutdown(app)
        await orders.shutdown(app)
        await portfolio.shutdown(app)


async def test_missing_orders_port_fails_startup_explicitly(api_settings):
    app = create_app(api_settings)
    del app.state.order_query_port
    with pytest.raises(RuntimeError, match="order_query_port"):
        await brokers.startup(app)


async def test_expiry_job_uses_configured_interval_and_stops(api_settings):
    app = create_app(
        api_settings.model_copy(
            update={
                "brokers_jobs_enabled": "true",
                "brokers_expiry_interval_seconds": "11",
            }
        )
    )
    entered = asyncio.Event()

    class Work:
        async def run_once(self):
            entered.set()
            await asyncio.Event().wait()

    app.state.brokers_expiry_service = Work()
    await brokers.startup(app)
    try:
        await asyncio.wait_for(entered.wait(), 1)
        assert app.state.brokers_expiry_job.interval == 11
        task = app.state.brokers_expiry_job.task
    finally:
        await brokers.shutdown(app)
    assert task.done()
