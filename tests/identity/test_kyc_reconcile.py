"""KYC reconciliation use case and endpoint guards (Requirement 24)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from acciones_ud.config.settings import Settings
from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.adapters.outbound.alpaca.fake_accounts import FakeAlpacaAccounts
from acciones_ud.identity.application.kyc_reconcile import KycReconcileService
from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.identity.domain.kyc import AlpacaAccount, AlpacaAccountSummary
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.main import create_app
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from tests.support.clock import FakeClock

NOW = datetime(2026, 1, 1, tzinfo=UTC)
ADMIN = uuid4()


class FakeAuditLog:
    def __init__(self) -> None:
        self.entries: list[object] = []

    async def append(self, entry: object) -> None:
        self.entries.append(entry)


class FakeReconcileStore:
    def __init__(
        self,
        row: Record | None = None,
        *,
        email: str | None = "ana@example.com",
        other: Record | None = None,
    ) -> None:
        self.row = row
        self.email = email
        self.other = other
        self.links = 0
        self.audit = FakeAuditLog()

    async def user_email(self, user_id: UUID) -> str:
        if self.email is None:
            raise AppError(404, ErrorCode.NOT_FOUND, "User not found.", {"resource": "user"})
        return self.email

    async def get(self, user_id: UUID) -> Record | None:
        return self.row

    async def get_by_alpaca_id(self, account_id: str) -> Record | None:
        if self.row is not None and self.row.get("alpaca_account_id") == account_id:
            return self.row
        if self.other is not None and self.other.get("alpaca_account_id") == account_id:
            return self.other
        return None

    async def link_new(
        self, user_id: UUID, account_id: str, status: str, retrieved_at: datetime
    ) -> bool:
        if self.row is not None:
            return False
        self.row = {
            "user_id": user_id,
            "alpaca_account_id": account_id,
            "status": status,
            "status_updated_at": retrieved_at,
            "status_checked_at": retrieved_at,
            "reserved_at": retrieved_at,
            "tax_id_last4": None,
        }
        self.links += 1
        return True

    async def link_reserved(
        self,
        user_id: UUID,
        account_id: str,
        status: str,
        retrieved_at: datetime,
        observed_reserved_at: datetime,
    ) -> bool:
        if (
            self.row is None
            or self.row.get("alpaca_account_id") is not None
            or self.row.get("reserved_at") != observed_reserved_at
        ):
            return False
        self.row.update(alpaca_account_id=account_id, status=status)
        self.links += 1
        return True

    @asynccontextmanager
    async def work(self) -> AsyncIterator[object]:
        repo = self

        class Work:
            kyc = repo
            audit = repo.audit

        yield Work()


def service(
    store: FakeReconcileStore, accounts: FakeAlpacaAccounts
) -> KycReconcileService:
    return KycReconcileService(store.work, accounts, FakeClock(NOW))


def linked_row(account_id: UUID) -> Record:
    return {
        "user_id": uuid4(),
        "alpaca_account_id": str(account_id),
        "status": "ACTIVE",
        "reserved_at": NOW - timedelta(days=1),
    }


async def test_explicit_account_id_links_a_user_without_a_kyc_row() -> None:
    account_id = uuid4()
    store = FakeReconcileStore(None)
    accounts = FakeAlpacaAccounts([AlpacaAccount(str(account_id), "SUBMITTED", NOW)])
    target = uuid4()

    result = await service(store, accounts).reconcile(ADMIN, target, account_id)

    assert result["alpaca_account_id"] == str(account_id)
    assert result["status"] == "SUBMITTED" and result["outcome"] == "linked"
    assert store.links == 1 and accounts.calls == [("get", str(account_id))]


async def test_link_reserved_requires_the_observed_reservation() -> None:
    account_id = uuid4()
    row: Record = {
        "user_id": uuid4(),
        "alpaca_account_id": None,
        "status": None,
        "reserved_at": NOW - timedelta(seconds=500),
    }
    store = FakeReconcileStore(row)
    accounts = FakeAlpacaAccounts([AlpacaAccount(str(account_id), "SUBMITTED")])

    result = await service(store, accounts).reconcile(ADMIN, uuid4(), account_id)

    assert result["outcome"] == "linked"
    assert row["alpaca_account_id"] == str(account_id)


async def test_already_linked_does_not_call_alpaca() -> None:
    account_id = uuid4()
    store = FakeReconcileStore(linked_row(account_id))
    accounts = FakeAlpacaAccounts([])

    result = await service(store, accounts).reconcile(ADMIN, uuid4(), None)

    assert result["outcome"] == "already_linked"
    assert result["alpaca_account_id"] == str(account_id)
    assert accounts.calls == []


async def test_a_different_account_id_is_a_conflict() -> None:
    store = FakeReconcileStore(linked_row(uuid4()))
    accounts = FakeAlpacaAccounts([])

    with pytest.raises(AppError) as caught:
        await service(store, accounts).reconcile(ADMIN, uuid4(), uuid4())

    assert caught.value.code is ErrorCode.KYC_ACCOUNT_EXISTS
    assert accounts.calls == []


async def test_account_already_used_by_another_user_is_a_conflict() -> None:
    account_id = uuid4()
    store = FakeReconcileStore(
        None, other={"user_id": uuid4(), "alpaca_account_id": str(account_id)}
    )
    accounts = FakeAlpacaAccounts([AlpacaAccount(str(account_id), "SUBMITTED")])

    with pytest.raises(AppError) as caught:
        await service(store, accounts).reconcile(ADMIN, uuid4(), account_id)

    assert caught.value.code is ErrorCode.ALPACA_ACCOUNT_IN_USE
    assert store.links == 0


async def test_fresh_reservation_blocks_reconciliation() -> None:
    row: Record = {
        "user_id": uuid4(),
        "alpaca_account_id": None,
        "status": None,
        "reserved_at": NOW - timedelta(seconds=30),
    }
    accounts = FakeAlpacaAccounts([])

    with pytest.raises(AppError) as caught:
        await service(FakeReconcileStore(row), accounts).reconcile(ADMIN, uuid4(), uuid4())

    assert caught.value.code is ErrorCode.KYC_SUBMISSION_IN_PROGRESS
    assert accounts.calls == []


async def test_email_search_links_the_single_matching_account() -> None:
    store = FakeReconcileStore(None)
    accounts = FakeAlpacaAccounts(
        [],
        list_outcomes=[
            [AlpacaAccountSummary("acc-1", "ACTIVE", None, "ana@example.com")]
        ],
    )

    result = await service(store, accounts).reconcile(ADMIN, uuid4(), None)

    assert result["alpaca_account_id"] == "acc-1" and result["outcome"] == "linked"
    assert accounts.calls == [("list", "ana@example.com")]


async def test_email_search_without_matches_is_404() -> None:
    store = FakeReconcileStore(None)
    accounts = FakeAlpacaAccounts([], list_outcomes=[[]])

    with pytest.raises(AppError) as caught:
        await service(store, accounts).reconcile(ADMIN, uuid4(), None)

    assert caught.value.code is ErrorCode.KYC_RECONCILE_NOT_FOUND


async def test_email_search_with_many_matches_is_ambiguous() -> None:
    store = FakeReconcileStore(None)
    accounts = FakeAlpacaAccounts(
        [],
        list_outcomes=[
            [
                AlpacaAccountSummary("acc-1", "ACTIVE", None, "ana@example.com"),
                AlpacaAccountSummary("acc-2", "ACTIVE", None, "ana@example.com"),
            ]
        ],
    )

    with pytest.raises(AppError) as caught:
        await service(store, accounts).reconcile(ADMIN, uuid4(), None)

    assert caught.value.code is ErrorCode.KYC_RECONCILE_AMBIGUOUS
    assert caught.value.details == {"count": 2}


def app_client(store: FakeReconcileStore, accounts: FakeAlpacaAccounts) -> TestClient:
    app = create_app(Settings(_env_file=None, app_env="test"))
    app.state.kyc_reconcile_service = service(store, accounts)
    current = CurrentUser(
        ADMIN,
        uuid4(),
        "admin@example.com",
        "active",
        False,
        frozenset({"administrator"}),
        frozenset({"admin:users"}),
    )
    app.dependency_overrides[get_current_user] = lambda: current
    return TestClient(app)


def test_endpoint_requires_authentication() -> None:
    client = TestClient(create_app(Settings(_env_file=None, app_env="test")))

    response = client.post(f"/api/v1/admin/kyc/{uuid4()}/reconcile")

    assert response.status_code == 401


def test_endpoint_requires_the_admin_permission(api_settings: Settings) -> None:
    app = create_app(api_settings)
    current = CurrentUser(
        ADMIN, uuid4(), "user@example.com", "active", False, frozenset({"investor"})
    )
    app.dependency_overrides[get_current_user] = lambda: current

    response = TestClient(app).post(f"/api/v1/admin/kyc/{uuid4()}/reconcile")

    assert response.status_code == 403 and response.json()["code"] == "FORBIDDEN"


def test_endpoint_rejects_unknown_user_and_malformed_uuids(api_settings: Settings) -> None:
    store = FakeReconcileStore(None, email=None)
    client = app_client(store, FakeAlpacaAccounts([]))

    unknown = client.post(f"/api/v1/admin/kyc/{uuid4()}/reconcile")
    assert unknown.status_code == 404 and unknown.json()["code"] == "NOT_FOUND"

    bad_user = client.post("/api/v1/admin/kyc/not-a-uuid/reconcile")
    assert bad_user.status_code == 422

    bad_body = client.post(
        f"/api/v1/admin/kyc/{uuid4()}/reconcile", json={"alpaca_account_id": "nope"}
    )
    assert bad_body.status_code == 422


def test_endpoint_accepts_an_absent_body(api_settings: Settings) -> None:
    store = FakeReconcileStore(None, email=None)
    client = app_client(store, FakeAlpacaAccounts([]))

    response = client.post(f"/api/v1/admin/kyc/{uuid4()}/reconcile")

    assert response.status_code == 404
    assert "tax_id" not in response.text
