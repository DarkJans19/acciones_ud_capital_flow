"""Audit log read endpoint and guards (25.7-25.11, 25.13)."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from acciones_ud.config.settings import Settings
from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.application.audit_log import AuditLogService
from acciones_ud.identity.domain.audit import (
    AuditAction,
    AuditEntry,
    AuditPage,
    AuditQuery,
    build_entry,
    select,
)
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.main import create_app

NOW = datetime(2026, 1, 1, tzinfo=UTC)
ADMIN = uuid4()
TARGET = uuid4()


class FakeAuditRepository:
    def __init__(self, entries: list[AuditEntry]) -> None:
        self.entries = entries

    async def search(self, query: AuditQuery) -> AuditPage:
        return select(self.entries, query)

    @asynccontextmanager
    async def work(self) -> AsyncIterator[object]:
        repo = self

        class Work:
            audit = repo

        yield Work()


def entries() -> list[AuditEntry]:
    return [
        build_entry(
            AuditAction.PREMIUM_CHANGED,
            ADMIN,
            "user",
            str(TARGET),
            {"is_premium": True},
            NOW,
        ),
        build_entry(
            AuditAction.ROLE_PERMISSION_ADDED,
            ADMIN,
            "role",
            "broker",
            {"permission_code": "admin:users"},
            NOW - timedelta(minutes=5),
        ),
    ]


def make_client(
    settings: Settings,
    *,
    permissions: frozenset[str] = frozenset({"admin:rbac"}),
    authenticated: bool = True,
) -> TestClient:
    app = create_app(settings)
    app.state.audit_log_service = AuditLogService(FakeAuditRepository(entries()).work)
    if authenticated:
        current = CurrentUser(
            ADMIN,
            uuid4(),
            "admin@example.com",
            "active",
            False,
            frozenset({"administrator"}),
            permissions,
        )
        app.dependency_overrides[get_current_user] = lambda: current
    return TestClient(app)


def test_listing_returns_page_and_filters(api_settings: Settings) -> None:
    client = make_client(api_settings)

    body = client.get("/api/v1/admin/audit-log", params={"limit": 1}).json()
    assert body["total"] == 2 and len(body["items"]) == 1
    assert body["items"][0]["action"] == "premium_changed"
    assert body["items"][0]["occurred_at"]

    filtered = client.get(
        "/api/v1/admin/audit-log", params={"action": "role_permission_added"}
    ).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["target_type"] == "role"


def test_listing_requires_authentication(api_settings: Settings) -> None:
    client = make_client(api_settings, authenticated=False)

    assert client.get("/api/v1/admin/audit-log").status_code == 401


def test_listing_requires_admin_rbac(api_settings: Settings) -> None:
    client = make_client(api_settings, permissions=frozenset({"admin:users"}))

    response = client.get("/api/v1/admin/audit-log")

    assert response.status_code == 403 and response.json()["code"] == "FORBIDDEN"


@pytest.mark.parametrize(
    "params",
    [
        {"action": "deleted"},
        {"target_type": "banana"},
        {"target_id": ""},
        {"target_id": "x" * 101},
        {"actor_user_id": "nope"},
        {"limit": 0},
        {"offset": -1},
    ],
)
def test_invalid_parameters_are_rejected(
    api_settings: Settings, params: dict[str, object]
) -> None:
    client = make_client(api_settings)

    assert client.get("/api/v1/admin/audit-log", params=params).status_code == 422


def test_invalid_parameters_are_named_together(api_settings: Settings) -> None:
    client = make_client(api_settings)

    response = client.get(
        "/api/v1/admin/audit-log", params={"action": "deleted", "limit": 0}
    )

    assert response.status_code == 422
    fields = {error["field"] for error in response.json()["details"]["errors"]}
    assert {"query.action", "query.limit"} <= fields


def test_no_writable_audit_path_is_exposed(api_settings: Settings) -> None:
    document = make_client(api_settings).get("/openapi.json").json()

    for path, methods in document["paths"].items():
        if "audit-log" in path:
            assert set(methods) == {"get"}


def test_service_returns_page_over_entries() -> None:
    repo = FakeAuditRepository(entries())
    page = asyncio.run(AuditLogService(repo.work).list(AuditQuery(limit=10)))

    assert page.total == 2 and [entry.action for entry in page.items] == [
        AuditAction.PREMIUM_CHANGED,
        AuditAction.ROLE_PERMISSION_ADDED,
    ]
