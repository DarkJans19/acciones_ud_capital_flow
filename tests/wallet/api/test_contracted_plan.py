from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx

from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.application.account_info import AccountInfoService
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.main import create_app
from acciones_ud.wallet.adapters.outbound.identity.contracted_plan_reader import (
    ContractedPlanReader,
)
from acciones_ud.wallet.domain.model import Subscription
from tests.identity.test_account_kyc import AccountFake
from tests.wallet.fakes import MemoryFactory


async def test_users_me_contract_plan(api_settings) -> None:
    repository, uow = AccountFake(), MemoryFactory()

    @asynccontextmanager
    async def kyc():
        yield SimpleNamespace(kyc=SimpleNamespace(get=AsyncMock(return_value=None)))

    app = create_app(api_settings)
    app.state.account_info_service = AccountInfoService(
        repository.work, kyc, None, plans=ContractedPlanReader(uow)
    )
    user = CurrentUser(
        repository.user_id, uuid4(), "test@example.com", "active", False, frozenset({"investor"})
    )
    app.dependency_overrides[get_current_user] = lambda: user
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://test"
    ) as client:
        assert (await client.get("/api/v1/users/me")).json()["contracted_plan"] is None
        await uow.work.subscriptions.insert(
            Subscription(uuid4(), user.user_id, "annual", "active", "cs_plan")
        )
        response = await client.get("/api/v1/users/me")
        assert response.status_code == 200, response.text
        assert response.json()["contracted_plan"] == "annual"
    if app.state.wallet_stripe_http is not None:
        await app.state.wallet_stripe_http.aclose()
