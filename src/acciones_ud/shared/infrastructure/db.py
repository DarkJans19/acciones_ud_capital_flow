from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as PoolTimeout
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from acciones_ud.config.settings import get_settings
from acciones_ud.shared.domain.errors import AppError, ErrorCode


def require_database_url() -> str:
    database_url = get_settings().database_url
    if database_url is None:
        raise RuntimeError("DATABASE_URL debe configurarse con la conexión de Supabase")
    return database_url


def build_engine(url: str) -> AsyncEngine:
    return create_async_engine(
        url,
        pool_pre_ping=True,
        pool_timeout=10,
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4().hex}__",
            "command_timeout": 10,
        },
        hide_parameters=True,
    )


engine = build_engine(require_database_url())
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


def database_error(exc: Exception) -> AppError:
    return AppError(503, ErrorCode.DATABASE_UNAVAILABLE, "Database operation could not complete.")


@asynccontextmanager
async def unit_of_work() -> AsyncIterator[AsyncSession]:
    try:
        async with session_factory() as session, session.begin():
            yield session
    except (SQLAlchemyError, OSError, TimeoutError) as exc:
        raise database_error(exc) from None


@asynccontextmanager
async def translate_database_errors() -> AsyncIterator[None]:
    try:
        yield
    except (DBAPIError, PoolTimeout, OSError, TimeoutError) as exc:
        raise database_error(exc) from None
