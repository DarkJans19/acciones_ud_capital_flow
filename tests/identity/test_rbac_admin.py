from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from acciones_ud.config.settings import Settings
from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.application.broker_activation import BrokerActivationService
from acciones_ud.identity.application.rbac_admin import RbacService
from acciones_ud.identity.domain.admin_ports import AdminWork
from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.main import create_app
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from tests.support.clock import FakeClock


class FakeAdminRepository:
    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.admin_id, self.broker_id = uuid4(), uuid4()
        self.people = {
            self.admin_id: {"account_status": "active", "is_premium": False},
            self.broker_id: {"account_status": "pending_broker_activation", "is_premium": False},
        }
        self.rows = [
            {
                "id": uuid4(),
                "user_id": self.admin_id,
                "role_code": "administrator",
                "valid_from": clock.now() - timedelta(days=1),
                "valid_to": None,
            }
        ]
        self.mapping = {
            "administrator": ["admin:users", "admin:rbac"],
            "investor": [],
            "broker": [],
        }

    async def user(self, user_id: UUID) -> Record:
        if user_id not in self.people:
            raise AppError(404, ErrorCode.NOT_FOUND, "User not found.", {"resource": "user"})
        return self.people[user_id]

    async def assignments(self, user_id: UUID | None = None) -> list[Record]:
        return [
            {**r, "account_status": self.people[r["user_id"]]["account_status"]}
            for r in self.rows
            if user_id is None or r["user_id"] == user_id
        ]

    async def roles(self) -> list[Record]:
        return [
            {"role": role, "permissions": permissions} for role, permissions in self.mapping.items()
        ]

    async def permissions(self) -> list[Record]:
        return [{"code": "account:manage", "description": "Account settings"}]

    async def lock_admin_guard(self) -> None:
        pass

    async def cancel_assignment(
        self, user_id: UUID, assignment_id: UUID, actor_id: UUID, now: datetime
    ) -> Record:
        row = next(r for r in self.rows if r["id"] == assignment_id and r["user_id"] == user_id)
        row.update(status="CANCELLED", cancelled_at=now, cancelled_by=actor_id)
        return row

    async def save_assignment(
        self,
        user_id: UUID,
        role: str,
        valid_from: datetime,
        valid_to: datetime | None,
        assignment_id: UUID | None,
    ) -> Record:
        row = next((r for r in self.rows if r["id"] == assignment_id), None)
        if row is None:
            row = {"id": uuid4(), "user_id": user_id}
            self.rows.append(row)
        row.update(role_code=role, valid_from=valid_from, valid_to=valid_to)
        return row

    async def change_permission(self, role: str, permission: str, remove: bool) -> Record:
        if remove:
            self.mapping[role].remove(permission)
        else:
            self.mapping[role].append(permission)
        return {"role": role, "permissions": self.mapping[role]}

    async def mark_broker_active(self, user_id: UUID, now: datetime) -> None:
        user = await self.user(user_id)
        if user["account_status"] != "pending_broker_activation":
            raise AppError(409, ErrorCode.BROKER_NOT_PENDING, "Broker is not pending activation.")
        user["account_status"] = "active"

    async def set_premium(self, user_id: UUID, value: bool) -> Record:
        (await self.user(user_id))["is_premium"] = value
        return {"user_id": user_id, "is_premium": value}

    @asynccontextmanager
    async def work(self) -> AsyncIterator[AdminWork]:
        repo = self

        class Work:
            admin = repo

        before = deepcopy(self.__dict__)
        try:
            yield Work()
        except BaseException:
            self.__dict__.update(before)
            raise


def test_admin_api_guards_activation_and_last_admin(api_settings: Settings) -> None:
    clock = FakeClock()
    repo = FakeAdminRepository(clock)
    app = create_app(api_settings)
    app.state.rbac_service = RbacService(repo.work, clock)
    app.state.broker_activation_service = BrokerActivationService(repo.work, clock)
    current = CurrentUser(
        repo.admin_id,
        uuid4(),
        "admin@example.com",
        "active",
        False,
        frozenset({"administrator"}),
        frozenset({"admin:users", "admin:rbac"}),
    )
    app.dependency_overrides[get_current_user] = lambda: current
    client = TestClient(app)
    activated = client.post(f"/api/v1/admin/users/{repo.broker_id}/broker-activation")
    body = activated.json()
    assert activated.status_code == 200 and body["role_assignment"]["effective"]
    assert body["role_assignment"]["role"] == "broker"
    assert body["investor_assignment"]["role"] == "investor"
    again = client.post(f"/api/v1/admin/users/{repo.broker_id}/broker-activation")
    assert again.status_code == 409 and again.json()["code"] == "BROKER_NOT_PENDING"
    assert len(repo.rows) == 3
    assignment_id = repo.rows[0]["id"]
    before = deepcopy(repo.rows)
    rejected = client.post(f"/api/v1/admin/users/{repo.admin_id}/roles/{assignment_id}/revoke")
    assert rejected.status_code == 409 and rejected.json()["code"] == "LAST_ADMINISTRATOR"
    assert repo.rows == before
    foreign = client.put(
        f"/api/v1/admin/users/{repo.broker_id}/roles/{assignment_id}",
        json={"valid_from": "2025-01-01T00:00:00Z", "valid_to": None},
    )
    assert foreign.status_code == 404 and repo.rows == before
    assert client.put(
        f"/api/v1/admin/users/{repo.broker_id}/premium", json={"is_premium": True}
    ).json()["is_premium"]
    assert client.get(f"/api/v1/admin/users/{uuid4()}/roles").status_code == 404


async def test_assignment_and_permission_changes() -> None:
    clock = FakeClock()
    repo = FakeAdminRepository(clock)
    service = RbacService(repo.work, clock)
    added = await service.save(repo.broker_id, "investor", clock.now(), None, None)
    assert not added["effective"]  # pending accounts stay without effective roles
    await BrokerActivationService(repo.work, clock).activate(repo.admin_id, repo.broker_id)
    listed = await service.assignments(repo.broker_id)
    assert {r["role"] for r in listed} >= {"broker", "investor"}
    assert all(r["effective"] for r in listed)
    result = await service.change_permission("broker", "account:manage", False)
    assert result["permissions"] == ["account:manage"]
    result = await service.change_permission("broker", "account:manage", True)
    assert result["permissions"] == []
    clock.advance(1)
    revoked = await service.save(repo.broker_id, None, None, None, added["id"], revoke=True)
    assert not revoked["effective"] and revoked["valid_to"] == clock.now()
