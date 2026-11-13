import os
from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
from asgi_lifespan import LifespanManager
from cryptography.fernet import Fernet
from hypothesis import settings as hypothesis_settings

from acciones_ud.config.settings import Settings, get_settings
from acciones_ud.main import create_app

hypothesis_settings.register_profile("project", max_examples=100, deadline=None)
hypothesis_settings.load_profile("project")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if not os.environ.get("TEST_DATABASE_URL"):
        for item in items:
            if "db" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="TEST_DATABASE_URL unset: DB not verified"))


@pytest.fixture
def api_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        database_url="postgresql+asyncpg://test:test@localhost/test",
        migration_database_url="postgresql+asyncpg://test:test@localhost/test",
        alpaca_broker_api_key="test-key",
        alpaca_broker_api_secret="test-secret",
        alpaca_broker_base_url="https://broker-api.sandbox.alpaca.markets",
        alpaca_data_base_url="https://data.sandbox.alpaca.markets",
        alpaca_stream_base_url="wss://stream.data.sandbox.alpaca.markets",
        alpaca_data_feed="iex",
        jwt_secret="x" * 32,
        access_token_ttl_seconds="900",
        refresh_token_ttl_seconds="604800",
        cors_allowed_origins="https://frontend.test",
        totp_encryption_key=Fernet.generate_key().decode(),
        alert_engine_enabled="false",
        price_streaming_enabled="false",
    )


@pytest.fixture
async def api_client(api_settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(api_settings)
    async with (
        LifespanManager(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://api.test"
        ) as client,
    ):
        yield client


@pytest.fixture(scope="session")
def migrated_database() -> Iterator[str]:
    """Destructive operations exclusively against an explicitly supplied test URL."""
    from alembic import command
    from alembic.config import Config
    from argon2 import PasswordHasher

    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL unset: DB not verified")
    names = {
        "DATABASE_URL": url,
        "MIGRATION_DATABASE_URL": url,
        "APP_ENV": "test",
        "INITIAL_ADMIN_EMAIL": "admin@example.com",
        "INITIAL_ADMIN_PASSWORD_HASH": PasswordHasher().hash("TestPassword123"),
        "INITIAL_ADMIN_FIRST_NAMES": "Test",
        "INITIAL_ADMIN_LAST_NAMES": "Administrator",
        "INITIAL_ADMIN_PHONE": "+573001234567",
        "INITIAL_ADMIN_COUNTRY": "CO",
    }
    previous = {name: os.environ.get(name) for name in names}
    os.environ.update(names)
    get_settings.cache_clear()
    config = Config("alembic.ini")
    try:
        # Repeatable runs: a previous failed run may have left a partial schema.
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        yield url
    finally:
        try:
            command.downgrade(config, "base")
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
            get_settings.cache_clear()


@pytest.fixture
async def db_session(migrated_database: str) -> AsyncIterator[object]:
    from sqlalchemy.ext.asyncio import AsyncSession

    from acciones_ud.shared.infrastructure.db import build_engine

    engine = build_engine(migrated_database)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            async with AsyncSession(bind=connection, join_transaction_mode="create_savepoint") as s:
                yield s
            await transaction.rollback()
    finally:
        await engine.dispose()
