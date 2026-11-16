from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from acciones_ud.portfolio.adapters.outbound.identity.account_reader import AccountReader
from acciones_ud.portfolio.adapters.outbound.identity.view_settings_reader import ViewSettingsReader
from acciones_ud.portfolio.domain.model import ViewSettings


async def test_defaults_and_unlinked_account():
    service = SimpleNamespace(settings=AsyncMock(return_value={}))
    owner = uuid4()
    assert await ViewSettingsReader(service).get(owner) == ViewSettings()

    @asynccontextmanager
    async def work():
        yield SimpleNamespace(kyc=SimpleNamespace(get=AsyncMock(return_value=None)))

    assert await AccountReader(work).get(owner) is None
