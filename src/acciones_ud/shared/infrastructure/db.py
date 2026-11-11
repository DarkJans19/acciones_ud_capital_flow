from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from acciones_ud.config.settings import get_settings


def require_database_url() -> str:
    database_url = get_settings().database_url
    if database_url is None:
        raise RuntimeError("DATABASE_URL debe configurarse con la conexión de Supabase")
    return database_url


engine = create_async_engine(require_database_url(), pool_pre_ping=True)
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
