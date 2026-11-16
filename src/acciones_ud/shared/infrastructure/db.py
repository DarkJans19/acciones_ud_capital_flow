import logging
import re
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
    # Never log str(exc), SQL, parameters or driver details: they can contain
    # credentials, personal data and request bodies. SQLSTATE is sufficient
    # to distinguish a deployment fault from a connectivity failure.
    raw_state = getattr(getattr(exc, "orig", None), "sqlstate", None)
    state = (
        raw_state
        if isinstance(raw_state, str) and re.fullmatch(r"[0-9A-Z]{5}", raw_state)
        else None
    )
    status, code, message = (
        503,
        ErrorCode.DATABASE_UNAVAILABLE,
        "Database operation could not complete.",
    )
    if state == "42501" or (state and state.startswith("28")):
        status, code, message = (
            500,
            ErrorCode.DATABASE_PERMISSION_ERROR,
            "Database access configuration requires attention.",
        )
    elif state and state.startswith("42"):
        status, code, message = (
            500,
            ErrorCode.DATABASE_SCHEMA_ERROR,
            "Database schema or query requires attention.",
        )
    elif state and state.startswith("23"):
        status, code, message = (
            409,
            ErrorCode.DATABASE_INTEGRITY_ERROR,
            "Operation conflicts with stored data constraints.",
        )
    elif state and state.startswith("22"):
        status, code, message = (
            500,
            ErrorCode.DATABASE_DATA_ERROR,
            "Database value could not be processed.",
        )
    logging.getLogger(__name__).error(
        "Database operation failed code=%s sqlstate=%s exception_type=%s",
        code,
        state or "unknown",
        type(exc).__name__,
    )
    return AppError(status, code, message)


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
