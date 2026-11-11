import json
from collections import deque
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker

from acciones_ud.config.settings import Settings
from acciones_ud.identity.adapters.outbound.persistence import tables as t
from acciones_ud.main import create_app


@pytest.fixture
async def postgres_app(
    migrated_database: str, api_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[object]:
    from acciones_ud.shared.infrastructure import db

    engine = db.build_engine(migrated_database)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db, "session_factory", factory)
    app = create_app(api_settings)
    app.state.sql_factory = factory
    app.state.test_tag = "identity-" + uuid4().hex
    app.state.provider_calls = []
    app.state.provider_documents = []
    app.state.provider_outcomes = deque()
    app.state.test_symbols = []

    def provider(request: httpx.Request) -> httpx.Response:
        app.state.provider_calls.append((request.method, request.url.path))
        if request.method == "POST":
            app.state.provider_documents.append(json.loads(request.content))
        if app.state.provider_outcomes:
            outcome = app.state.provider_outcomes.popleft()
            if isinstance(outcome, Exception):
                raise outcome
            return httpx.Response(outcome[0], json=outcome[1])
        return httpx.Response(
            200,
            json={
                "id": str(uuid4()) if request.method == "POST" else request.url.path.split("/")[-1],
                "status": "SUBMITTED" if request.method == "POST" else "ACTIVE",
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )

    async with httpx.AsyncClient(
        base_url="https://broker-api.sandbox.alpaca.markets",
        auth=httpx.BasicAuth("fake", "fake"),
        transport=httpx.MockTransport(provider),
    ) as broker:
        app.state.alpaca_broker = broker
        try:
            yield app
        finally:
            # Delete only the UUID-tagged identities created by this fixture's tests.
            async with factory() as session, session.begin():
                ids = sa.select(t.users.c.id).where(
                    t.users.c.email_normalized.like(app.state.test_tag + "%@example.com")
                )
                for table in (t.auth_events, t.mfa_challenges, t.role_assignments):
                    await session.execute(table.delete().where(table.c.user_id.in_(ids)))
                await session.execute(t.users.delete().where(t.users.c.id.in_(ids)))
                for symbol in app.state.test_symbols:
                    await session.execute(
                        sa.text("DELETE FROM instruments WHERE symbol=:symbol"), {"symbol": symbol}
                    )
            await engine.dispose()
