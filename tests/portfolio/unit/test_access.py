from uuid import uuid4

import pytest

from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.portfolio.domain.access import resolve
from acciones_ud.shared.domain.errors import AppError


def test_active_roles_only():
    for required in ("investor", "broker"):
        user = CurrentUser(uuid4(), uuid4(), "user@test.co", "active", False, frozenset({required}))
        resolve(user, required)
        with pytest.raises(AppError) as caught:
            resolve(user, "broker" if required == "investor" else "investor")
        assert caught.value.status == 403
