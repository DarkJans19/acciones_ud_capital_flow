"""RF-04/05/41/42: authenticated HTTP flow with PostgreSQL and fake providers."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import httpx
import pytest
import sqlalchemy as sa

from acciones_ud.identity.adapters.outbound.persistence import tables as identity
from acciones_ud.market_data.adapters.outbound.alpaca.fake_data import FakeAlpacaData
from acciones_ud.market_data.domain.entities import Snapshot
from acciones_ud.orders.adapters.outbound.persistence import tables as orders
from acciones_ud.orders.adapters.outbound.persistence.unit_of_work import build_work
from acciones_ud.orders.domain.model import Execution, OrderStatus, Reservation
from acciones_ud.portfolio.adapters.outbound.persistence.tables import reports
from tests.identity.conftest import postgres_app as postgres_app
from tests.identity.test_financial_profile import kyc_payload
from tests.identity.test_postgres_api import client, register_and_login
from tests.orders.support import make_order

pytestmark = pytest.mark.db


async def test_authenticated_portfolio_reports_and_scheduler_on_postgres(postgres_app):
    app = postgres_app
    order_ids = []
    owner = None
    async with client(app) as investor, client(app) as other:
        enrolled = await register_and_login(investor, app.state.test_tag + "-portfolio@example.com")
        owner = UUID(enrolled["user"]["user_id"])
        await register_and_login(other, app.state.test_tag + "-other@example.com")
        missing = await investor.get("/api/v1/portfolio/positions")
        assert missing.status_code == 409 and missing.json()["code"] == "ACCOUNT_NOT_LINKED"
        assert app.state.provider_calls == []
        opened = await investor.post("/api/v1/kyc/account", json=kyc_payload())
        assert opened.status_code == 201, opened.text
        assert (await investor.get("/api/v1/kyc/status")).status_code == 200
        now = datetime.now(UTC)
        symbol = "P" + uuid4().hex[:8].upper()
        app.state.test_symbols.append(symbol)
        local_day = now.astimezone(ZoneInfo("America/New_York")).date()
        closed_day = local_day - timedelta(days=1)
        while closed_day.weekday() >= 5:
            closed_day -= timedelta(days=1)
        try:
            async with app.state.sql_factory() as session, session.begin():
                await session.execute(
                    sa.update(identity.users)
                    .where(identity.users.c.id == owner)
                    .values(monthly_report=True)
                )
                account = (
                    await session.execute(
                        sa.select(identity.kyc_accounts.c.alpaca_account_id).where(
                            identity.kyc_accounts.c.user_id == owner
                        )
                    )
                ).scalar_one()
                await session.execute(
                    sa.text(
                        "INSERT INTO instruments "
                        "(symbol,name,exchange,asset_class,status,sector,updated_at) "
                        "VALUES (:symbol,'Portfolio integration','NYSE','us_equity',"
                        "'active','Technology',now())"
                    ),
                    {"symbol": symbol},
                )
                work = build_work(session)
                for side, quantity, price, offset in [("buy", 10, 10, 3), ("sell", 5, 15, 2)]:
                    order = make_order(
                        owner,
                        symbol=symbol,
                        exchange="NYSE",
                        side=side,
                        qty=Decimal(quantity),
                        filled_qty=Decimal(quantity),
                        fully_filled=True,
                        status=OrderStatus.EXECUTING,
                    )
                    order_ids.append(order.id)
                    await work.orders.insert(order)
                    await work.executions.insert(
                        Execution(
                            str(uuid4()),
                            order.id,
                            Decimal(quantity),
                            Decimal(price),
                            now - timedelta(minutes=offset),
                            now,
                        )
                    )
                pending = make_order(
                    owner, symbol=symbol, exchange="NYSE", side="sell", qty=Decimal(2)
                )
                order_ids.append(pending.id)
                await work.orders.insert(pending)
                await work.reservations.insert(
                    Reservation(pending.id, owner, "shares", symbol, Decimal(2), "active", now)
                )
            market = FakeAlpacaData()
            market.snapshot_value = Snapshot(last_trade_price=Decimal(16), quote_updated_at=now)
            app.state.alpaca_data_port = market
            state = {"positions_status": 200, "positions_calls": 0}
            raw = dict(
                symbol=symbol,
                exchange="NYSE",
                qty="5",
                qty_available="4",
                avg_entry_price="10",
                current_price="15",
            )

            def provider(request):
                path = request.url.path
                if path.endswith("/positions") or "/positions/" in path:
                    state["positions_calls"] += 1
                    if state["positions_status"] != 200:
                        return httpx.Response(state["positions_status"])
                    return httpx.Response(200, json=[raw] if path.endswith("/positions") else raw)
                if path.endswith("/account"):
                    return httpx.Response(
                        200,
                        json=dict(
                            status="ACTIVE",
                            currency="USD",
                            cash="120",
                            cash_withdrawable="120",
                            buying_power="120",
                            equity="200",
                            portfolio_value="200",
                            long_market_value="80",
                        ),
                    )
                if path == "/v1/calendar":
                    return httpx.Response(
                        200,
                        json=[{"date": closed_day.isoformat(), "open": "09:30", "close": "16:00"}],
                    )
                raise AssertionError(f"Unexpected provider request: {request.method} {path}")

            async with httpx.AsyncClient(
                base_url="https://alpaca.test", transport=httpx.MockTransport(provider)
            ) as broker:
                app.state.alpaca_broker = broker
                response = await investor.get("/api/v1/portfolio/positions")
                assert response.status_code == 200, response.text
                position = response.json()["positions"][0]
                assert position["qty"] == "5.000000000"
                assert position["reserved_qty"] == "3.000000000"
                assert position["price_source"] == "market_data"
                assert position["market_value"] == "80.00"
                assert not position["reconciliation_mismatch"]
                assert await app.state.order_position_port.qty_available(
                    account, symbol
                ) == Decimal(4)
                preference = await investor.put(
                    "/api/v1/users/preferences/portfolio",
                    json={
                        "view_type": "cards",
                        "sort_by": "gain_loss",
                        "sort_direction": "desc",
                        "hide_threshold": "100.00",
                    },
                )
                assert preference.status_code == 200, preference.text
                hidden = (await investor.get("/api/v1/portfolio/positions")).json()
                assert hidden["positions"] == [] and hidden["totals"]["market_value"] == "80.00"
                start = (now - timedelta(minutes=3)).astimezone(ZoneInfo("America/New_York")).date()
                period = {"from": start.isoformat(), "to": local_day.isoformat()}
                history = await investor.get(
                    "/api/v1/portfolio/executions", params={**period, "page_size": 1}
                )
                assert history.status_code == 200, history.text
                first_page = history.json()
                assert first_page["items"][0]["side"] == "sell" and first_page["next_cursor"]
                second_page = (
                    await investor.get(
                        "/api/v1/portfolio/executions",
                        params={**period, "page_size": 1, "cursor": first_page["next_cursor"]},
                    )
                ).json()
                assert (
                    second_page["items"][0]["side"] == "buy" and second_page["next_cursor"] is None
                )
                stats = (await investor.get("/api/v1/portfolio/statistics", params=period)).json()
                assert stats["execution_count"] == 2 and stats["volume"] == "175.00"
                assert stats["by_sector"] == [
                    {"key": "Technology", "volume": "175.00", "percentage": "100.00"}
                ]
                risk = await investor.get("/api/v1/portfolio/risk-profile")
                assert risk.status_code == 200, risk.text
                assert not risk.json()["equity_unavailable"] and risk.json()["e"] == "40.00"
                created = await investor.post("/api/v1/portfolio/reports", json=period)
                assert created.status_code == 201, created.text
                report = created.json()
                assert report["content"]["realized_pnl"] == {"gross": "25.00", "net": "23.50"}
                assert report["content"]["unrealized_pnl"] == "30.00"
                assert report["content"]["commissions"] == "3.50"
                assert report["content"]["profitability"] == "55.00"
                assert len(report["content"]["positions"]) == 1
                path = "/api/v1/portfolio/reports/" + report["id"]
                assert (await investor.get(path)).json() == report
                assert (await other.get(path)).status_code == 404
                await app.state.portfolio_report_scheduler.run_cycle(now)
                async with app.state.sql_factory() as session:
                    saved = (
                        (
                            await session.execute(
                                sa.select(reports).where(reports.c.owner_id == owner)
                            )
                        )
                        .mappings()
                        .all()
                    )
                    notifications = (
                        (
                            await session.execute(
                                sa.text(
                                    "SELECT payload FROM notifications WHERE user_id = :owner "
                                    "AND event_type = 'daily_summary'"
                                ),
                                {"owner": owner},
                            )
                        )
                        .scalars()
                        .all()
                    )
                assert {r["type"] for r in saved} == {"on_demand", "daily_summary", "monthly"}
                assert all(r["notified_at"] is not None for r in saved if r["type"] != "on_demand")
                assert len(notifications) == 2
                calls = state["positions_calls"]
                await app.state.portfolio_report_scheduler.run_cycle(now)
                assert state["positions_calls"] == calls
                async with app.state.sql_factory() as session:
                    assert (
                        await session.execute(
                            sa.text(
                                "SELECT count(*) FROM notifications WHERE user_id = :owner "
                                "AND event_type = 'daily_summary'"
                            ),
                            {"owner": owner},
                        )
                    ).scalar_one() == 2
                page = (
                    await investor.get("/api/v1/portfolio/reports", params={"page_size": 1})
                ).json()
                next_page = (
                    await investor.get(
                        "/api/v1/portfolio/reports",
                        params={"page_size": 1, "cursor": page["next_cursor"]},
                    )
                ).json()
                assert page["items"][0]["id"] != next_page["items"][0]["id"]
                state["positions_status"] = 429
                failed = await investor.post("/api/v1/portfolio/reports", json=period)
                assert failed.status_code == 503 and failed.json()["code"] == "ALPACA_RATE_LIMITED"
                async with app.state.sql_factory() as session:
                    assert (
                        await session.execute(
                            sa.select(sa.func.count())
                            .select_from(reports)
                            .where(reports.c.owner_id == owner)
                        )
                    ).scalar_one() == 3
        finally:
            async with app.state.sql_factory() as session, session.begin():
                await session.execute(reports.delete().where(reports.c.owner_id == owner))
                # Owner-only cleanup of UUID-tagged test evidence in the disposable DB.
                for table in ("order_executions", "order_events"):
                    await session.execute(
                        sa.text(f"ALTER TABLE {table} DISABLE TRIGGER {table}_admin_immutable")
                    )
                for table in (orders.executions, orders.reservations, orders.events):
                    await session.execute(table.delete().where(table.c.order_id.in_(order_ids)))
                for table in ("order_executions", "order_events"):
                    await session.execute(
                        sa.text(f"ALTER TABLE {table} ENABLE TRIGGER {table}_admin_immutable")
                    )
                await session.execute(
                    orders.orders.delete().where(orders.orders.c.id.in_(order_ids))
                )
                await session.execute(
                    sa.text("DELETE FROM instrument_snapshots WHERE symbol = :symbol"),
                    {"symbol": symbol},
                )
