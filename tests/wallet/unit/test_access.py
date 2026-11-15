from uuid import uuid4

import pytest

from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.shared.domain.errors import AppError
from acciones_ud.wallet.adapters.inbound.http.deps import require_investor


@pytest.mark.parametrize(
    "roles,status,allowed",
    [
        (frozenset({"investor"}), "active", True),
        (frozenset({"broker"}), "active", False),
        (frozenset({"investor"}), "restricted", False),
    ],
)
async def test_investor_guard(roles: frozenset[str], status: str, allowed: bool) -> None:
    user = CurrentUser(uuid4(), uuid4(), "test@example.com", status, False, roles)
    if allowed:
        assert await require_investor(user) == user
    else:
        with pytest.raises(AppError) as caught:
            await require_investor(user)
        assert caught.value.status == 403
