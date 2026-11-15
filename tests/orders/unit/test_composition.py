import asyncio
from uuid import uuid4

from acciones_ud.main import create_app
from acciones_ud.orders import composition
from tests.orders.fakes import BrokerLinks


async def test_registration_is_lazy_and_broker_port_can_be_installed_later(api_settings) -> None:
    app = create_app(api_settings)
    assert app.state.wallet_funding_port is not None
    assert app.state.order_schedule_change_port is not None
    user, broker = uuid4(), uuid4()
    assert await app.state.order_context.brokers.reviewing_broker(user) is None
    app.state.order_broker_link = BrokerLinks({user: broker})
    assert await app.state.order_context.brokers.reviewing_broker(user) == broker
    await composition.startup(app)
    assert not app.state.order_jobs
    await composition.shutdown(app)


async def test_enabled_jobs_use_configured_intervals_and_stop(api_settings) -> None:
    app = create_app(
        api_settings.model_copy(
            update={
                "orders_jobs_enabled": "true",
                "order_reconcile_interval_seconds": "17",
                "order_scheduler_interval_seconds": "31",
            }
        )
    )

    class WaitingWork:
        def __init__(self):
            self.entered = asyncio.Event()

        async def run_once(self):
            self.entered.set()
            await asyncio.Event().wait()

    app.state.order_reconciler, app.state.order_scheduler = WaitingWork(), WaitingWork()
    await composition.startup(app)
    await asyncio.wait_for(
        asyncio.gather(
            app.state.order_reconciler.entered.wait(), app.state.order_scheduler.entered.wait()
        ),
        1,
    )
    assert [job.interval for job in app.state.order_jobs] == [17, 31]
    tasks = [job.task for job in app.state.order_jobs]
    await composition.shutdown(app)
    assert all(task.done() for task in tasks)
