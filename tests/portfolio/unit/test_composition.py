import asyncio
from decimal import Decimal
from uuid import uuid4

from acciones_ud.main import create_app
from acciones_ud.portfolio import composition
from acciones_ud.portfolio.application.position_port import PortfolioPositionPort
from acciones_ud.portfolio.domain.model import CommissionQuote
from tests.portfolio.fakes import Sources
from tests.portfolio.property.test_pnl import records


async def test_registration_injects_orders_and_late_extension_ports(api_settings):
    app = create_app(api_settings)
    assert isinstance(app.state.order_context.positions, PortfolioPositionPort)
    assert app.state.order_context.positions is app.state.order_position_port
    broker, investor = uuid4(), uuid4()
    clients = Sources()
    clients.links.add((broker, investor))
    app.state.portfolio_broker_clients = clients
    assert await app.state.portfolio_service.brokers.is_linked(broker, investor)

    class Official:
        def commission(self, execution):
            return CommissionQuote(Decimal("1.23"), "official")

    app.state.portfolio_commission_port = Official()
    assert (
        app.state.portfolio_service.commissions.commission(
            records([("buy", Decimal(1), Decimal(1))])[0]
        ).source
        == "official"
    )
    await composition.startup(app)
    assert app.state.portfolio_job is None
    await composition.shutdown(app)


async def test_scheduler_interval_and_cancellation(api_settings):
    app = create_app(
        api_settings.model_copy(
            update={"portfolio_jobs_enabled": "true", "portfolio_report_interval_seconds": "61"}
        )
    )
    entered = asyncio.Event()

    class Work:
        async def run_once(self):
            entered.set()
            await asyncio.Event().wait()

    app.state.portfolio_report_scheduler = Work()
    await composition.startup(app)
    await asyncio.wait_for(entered.wait(), 1)
    assert app.state.portfolio_job.interval == 61
    task = app.state.portfolio_job.task
    await composition.shutdown(app)
    assert task.done()
