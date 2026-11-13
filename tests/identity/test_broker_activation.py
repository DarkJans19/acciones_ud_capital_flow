"""Broker activation grants broker + investor and `broker_requested` is queryable.

Requirements 2.12-2.17 (D5), 22.5-22.7 (D6) and 22.2. In-memory fakes only.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from acciones_ud.config.settings import Settings
from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.application.account_info import AccountInfoService
from acciones_ud.identity.application.broker_activation import BrokerActivationService
from acciones_ud.identity.application.rbac_admin import RbacService
from acciones_ud.identity.domain.admin_ports import AdminWork
from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.main import create_app
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from tests.support.clock import FakeClock


class FakeAuditLog:
    def __init__(self) -> None:
        self.entries: list[object] = []

    async def append(self, entry: object) -> None:
        self.entries.append(entry)


class FakeActivationRepository:
    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.audit = FakeAuditLog()
        self.admin_id, self.broker_id, self.investor_id = uuid4(), uuid4(), uuid4()
        self.people: dict[UUID, Record] = {
            self.admin_id: {"account_status": "active", "broker_requested": False},
            self.broker_id: {
                "account_status": "pending_broker_activation",
                "broker_requested": True,
            },
            self.investor_id: {"account_status": "active", "broker_requested": True},
        }
        self.rows: list[Record] = []
        self.inserts = 0
        self.fail_on_insert: int | None = None

    async def user(self, user_id: UUID) -> Record:
        if user_id not in self.people:
            raise AppError(404, ErrorCode.NOT_FOUND, "User not found.", {"resource": "user"})
        return self.people[user_id]

    async def assignments(self, user_id: UUID | None = None) -> list[Record]:
        return [
            {**row, "account_status": self.people[row["user_id"]]["account_status"]}
            for row in self.rows
            if user_id is None or row["user_id"] == user_id
        ]

    async def lock_admin_guard(self) -> None:
        pass

    async def mark_broker_active(self, user_id: UUID, now: datetime) -> None:
        user = await self.user(user_id)
        if user["account_status"] != "pending_broker_activation":
            raise AppError(409, ErrorCode.BROKER_NOT_PENDING, "Broker is not pending activation.")
        user["account_status"] = "active"

    async def save_assignment(
        self,
        user_id: UUID,
        role: str,
        valid_from: datetime,
        valid_to: datetime | None,
        assignment_id: UUID | None,
    ) -> Record:
        self.inserts += 1
        if self.fail_on_insert == self.inserts:
            raise AppError(503, ErrorCode.DATABASE_UNAVAILABLE, "Database unavailable.")
        row = {
            "id": uuid4(),
            "user_id": user_id,
            "role_code": role,
            "valid_from": valid_from,
            "valid_to": valid_to,
        }
        self.rows.append(row)
        return row

    @asynccontextmanager
    async def work(self) -> AsyncIterator[AdminWork]:
        repo = self

        class Work:
            admin = repo
            audit = repo.audit

        before = (deepcopy(self.people), deepcopy(self.rows))
        try:
            yield Work()
        except BaseException:
            self.people, self.rows = before
            raise


def admin_client(
    app_settings: Settings, repo: FakeActivationRepository, roles: frozenset[str]
) -> TestClient:
    clock = repo.clock
    app = create_app(app_settings)
    app.state.rbac_service = RbacService(repo.work, clock)
    app.state.broker_activation_service = BrokerActivationService(repo.work, clock)
    current = CurrentUser(
        repo.admin_id,
        uuid4(),
        "admin@example.com",
        "active",
        False,
        roles,
        frozenset({"admin:users"}),
    )
    app.dependency_overrides[get_current_user] = lambda: current
    return TestClient(app)


def test_activation_creates_broker_and_investor_assignments(api_settings: Settings) -> None:
    repo = FakeActivationRepository(FakeClock())
    client = admin_client(api_settings, repo, frozenset({"administrator"}))

    response = client.post(f"/api/v1/admin/users/{repo.broker_id}/broker-activation")

    assert response.status_code == 200
    body = response.json()
    assert body["account_status"] == "active"
    assert body["role_assignment"]["role"] == "broker"
    assert body["investor_assignment"]["role"] == "investor"
    assert body["role_assignment"]["effective"] and body["investor_assignment"]["effective"]
    assert {row["role_code"] for row in repo.rows} == {"broker", "investor"}
    assert repo.people[repo.broker_id]["account_status"] == "active"

    again = client.post(f"/api/v1/admin/users/{repo.broker_id}/broker-activation")
    assert again.status_code == 409 and again.json()["code"] == "BROKER_NOT_PENDING"
    assert len(repo.rows) == 2


def test_active_investor_with_broker_flag_is_not_activatable(api_settings: Settings) -> None:
    repo = FakeActivationRepository(FakeClock())
    client = admin_client(api_settings, repo, frozenset({"administrator"}))

    response = client.post(f"/api/v1/admin/users/{repo.investor_id}/broker-activation")

    assert response.status_code == 409 and response.json()["code"] == "BROKER_NOT_PENDING"
    assert repo.investor_id in repo.people
    assert repo.people[repo.investor_id]["broker_requested"] is True
    assert repo.rows == []


def test_activation_of_unknown_user_is_404(api_settings: Settings) -> None:
    repo = FakeActivationRepository(FakeClock())
    client = admin_client(api_settings, repo, frozenset({"administrator"}))

    response = client.post(f"/api/v1/admin/users/{uuid4()}/broker-activation")

    assert response.status_code == 404 and response.json()["code"] == "NOT_FOUND"
    assert repo.rows == []


def test_failed_second_insert_rolls_back_the_status_change(api_settings: Settings) -> None:
    repo = FakeActivationRepository(FakeClock())
    repo.fail_on_insert = 2
    client = admin_client(api_settings, repo, frozenset({"administrator"}))

    response = client.post(f"/api/v1/admin/users/{repo.broker_id}/broker-activation")

    assert response.status_code == 503 and response.json()["code"] == "DATABASE_UNAVAILABLE"
    assert repo.people[repo.broker_id]["account_status"] == "pending_broker_activation"
    assert repo.rows == []


def test_requester_without_administrator_role_is_403(api_settings: Settings) -> None:
    repo = FakeActivationRepository(FakeClock())
    client = admin_client(api_settings, repo, frozenset({"investor"}))

    response = client.post(f"/api/v1/admin/users/{repo.broker_id}/broker-activation")

    assert response.status_code == 403 and response.json()["code"] == "FORBIDDEN"
    assert repo.people[repo.broker_id]["account_status"] == "pending_broker_activation"
    assert repo.rows == []


def test_role_assignment_keeps_the_broker_request_flag(api_settings: Settings) -> None:
    repo = FakeActivationRepository(FakeClock())
    clock = repo.clock
    service = RbacService(repo.work, clock)

    added = asyncio.run(
        service.save(repo.investor_id, "broker", clock.now(), None, None, actor_id=repo.admin_id)
    )

    assert added["role"] == "broker"
    assert repo.people[repo.investor_id]["account_status"] == "active"
    assert repo.people[repo.investor_id]["broker_requested"] is True


class _AccountFake:
    def __init__(self) -> None:
        self.user_id = uuid4()
        self.record: Record = {
            "id": self.user_id,
            "first_names": "Ana",
            "last_names": "Perez",
            "email": "ana@example.com",
            "phone": "+573001234567",
            "country": "CO",
            "account_status": "active",
            "is_premium": False,
            "broker_requested": True,
            "interests": [],
            "investor_level": None,
            "created_at": datetime(2026, 1, 1),
            "totp_confirmed_at": None,
        }

    async def user(self, user_id: UUID, *, lock: bool = False) -> Record:
        return self.record

    @asynccontextmanager
    async def work(self) -> AsyncIterator[object]:
        repo = self

        class Work:
            account = repo

        yield Work()


class _KycFake:
    def __init__(self) -> None:
        self.user_id = uuid4()

    async def get(self, user_id: UUID) -> None:
        return None

    @asynccontextmanager
    async def work(self) -> AsyncIterator[object]:
        repo = self

        class Work:
            kyc = repo

        yield Work()


class _NoAlpaca:
    async def get_account(self, account_id: str, timeout: float = 10) -> object:
        raise AssertionError("Alpaca must not be called without a linked account")


async def test_account_information_returns_the_broker_request_flag() -> None:
    accounts = _AccountFake()
    service = AccountInfoService(accounts.work, _KycFake().work, _NoAlpaca())
    current = CurrentUser(
        accounts.user_id, uuid4(), "ana@example.com", "active", False, frozenset({"investor"})
    )

    result = await service.me(current)

    assert result["broker_requested"] is True
