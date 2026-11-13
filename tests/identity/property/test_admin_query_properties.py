"""Property 43: admin listing parameters are validated together (20.11, 21.8, 25.10)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.config.settings import Settings
from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.application.audit_log import AuditLogService
from acciones_ud.identity.application.user_directory import UserDirectoryService
from acciones_ud.identity.domain.audit import AuditPage, AuditQuery
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.main import create_app
from tests.support.clock import FakeClock
from tests.support.identity_fakes import FakeDirectoryRepository, FakeDirectoryWorkFactory

NOW = datetime(2026, 1, 1, tzinfo=UTC)
ADMIN = uuid4()

DIRECTORY_INVALID = {
    "account_status": st.sampled_from(["deleted", "ACTIVE", ""]),
    "role": st.sampled_from(["auditor", "Investor", ""]),
    "q": st.sampled_from(["", "   ", "x" * 101]),
    "broker_requested": st.sampled_from(["yes", "1", ""]),
    "kyc_status": st.sampled_from(["submitted", "DONE", ""]),
    "kyc_link_state": st.sampled_from(["linked ", "LINKED", ""]),
    "limit": st.sampled_from([0, 101, "many"]),
    "offset": st.sampled_from([-1, "many"]),
}

AUDIT_INVALID = {
    "action": st.sampled_from(["deleted", "PREMIUM_CHANGED", ""]),
    "target_type": st.sampled_from(["banana", "User", ""]),
    "target_id": st.sampled_from(["", "x" * 101]),
    "actor_user_id": st.sampled_from(["nope", "123"]),
    "limit": st.sampled_from([0, 101, "many"]),
    "offset": st.sampled_from([-1, "many"]),
}


def invalid_pairs(
    strategies: dict[str, st.SearchStrategy[object]],
) -> st.SearchStrategy[list[tuple[str, object]]]:
    options = [st.tuples(st.just(key), value) for key, value in strategies.items()]
    return st.lists(
        st.one_of(*options), min_size=1, max_size=3, unique_by=lambda pair: pair[0]
    )


class EmptyAuditRepository:
    def __init__(self) -> None:
        self.queries: list[AuditQuery] = []

    async def search(self, query: AuditQuery) -> AuditPage:
        self.queries.append(query)
        return AuditPage(items=(), total=0)

    @asynccontextmanager
    async def work(self) -> AsyncIterator[object]:
        repo = self

        class Work:
            audit = repo

        yield Work()


def admin_client() -> TestClient:
    app = create_app(Settings(_env_file=None, app_env="test"))
    app.state.user_directory_service = UserDirectoryService(
        FakeDirectoryWorkFactory(FakeDirectoryRepository([])), FakeClock(NOW)
    )
    app.state.audit_log_service = AuditLogService(EmptyAuditRepository().work)
    current = CurrentUser(
        ADMIN,
        uuid4(),
        "admin@example.com",
        "active",
        False,
        frozenset({"administrator"}),
        frozenset({"admin:users", "admin:rbac"}),
    )
    app.dependency_overrides[get_current_user] = lambda: current
    return TestClient(app)


def assert_every_invalid_parameter_is_named(
    response: object, pairs: list[tuple[str, object]]
) -> None:
    assert response.status_code == 422  # type: ignore[attr-defined]
    fields = {
        error["field"] for error in response.json()["details"]["errors"]  # type: ignore[attr-defined]
    }
    assert {f"query.{key}" for key, _ in pairs} <= fields


# Feature: identity-market-backend, Property 43: Admin listing parameters are validated together
@given(pairs=invalid_pairs(DIRECTORY_INVALID))
def test_directory_invalid_parameters_are_named_together(
    pairs: list[tuple[str, object]],
) -> None:
    client = admin_client()

    response = client.get("/api/v1/admin/users", params=dict(pairs))

    assert_every_invalid_parameter_is_named(response, pairs)


# Feature: identity-market-backend, Property 43: Admin listing parameters are validated together
@given(pairs=invalid_pairs(AUDIT_INVALID))
def test_audit_invalid_parameters_are_named_together(
    pairs: list[tuple[str, object]],
) -> None:
    client = admin_client()

    response = client.get("/api/v1/admin/audit-log", params=dict(pairs))

    assert_every_invalid_parameter_is_named(response, pairs)
