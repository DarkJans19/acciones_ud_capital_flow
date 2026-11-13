"""KYC refresh job and cache at the use-case level (Requirements 6 and 23)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from acciones_ud.config.settings import Settings
from acciones_ud.identity.adapters.inbound.jobs.kyc_refresh_job import KycRefreshJob
from acciones_ud.identity.adapters.outbound.alpaca.fake_accounts import FakeAlpacaAccounts
from acciones_ud.identity.application.account_info import AccountInfoService
from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.identity.domain.kyc import AlpacaAccount
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.main import create_app
from acciones_ud.shared.domain.alpaca_errors import AlpacaRateLimited, AlpacaUnavailable
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from tests.support.clock import FakeClock

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FakeKycStore:
    def __init__(self, account_ids: list[str] | None = None) -> None:
        self.account_ids = list(account_ids or [])
        self.writes: list[tuple[str, str]] = []
        self.reads = 0

    async def linked_account_ids(self) -> list[str]:
        self.reads += 1
        return list(self.account_ids)

    async def record_status_check(
        self, account: AlpacaAccount, retrieved_at: datetime
    ) -> None:
        self.writes.append((account.id, account.status))

    @asynccontextmanager
    async def work(self) -> AsyncIterator[object]:
        repo = self

        class Work:
            kyc = repo

        yield Work()


class AccountStore:
    def __init__(
        self, kyc: Record | None, failure: Exception | None = None, user_id: UUID | None = None
    ) -> None:
        self.user_id = user_id or uuid4()
        self.kyc = kyc
        self.failure = failure
        self.record: Record = {
            "id": self.user_id,
            "first_names": "Ana",
            "last_names": "Perez",
            "email": "ana@example.com",
            "phone": "+573001234567",
            "country": "CO",
            "account_status": "active",
            "is_premium": False,
            "broker_requested": False,
            "interests": [],
            "investor_level": None,
            "created_at": NOW,
            "totp_confirmed_at": None,
        }

    async def user(self, user_id: UUID, *, lock: bool = False) -> Record:
        return self.record

    @asynccontextmanager
    async def account_work(self) -> AsyncIterator[object]:
        if self.failure is not None:
            raise self.failure
        repo = self

        class Work:
            account = repo

        yield Work()

    async def get(self, user_id: UUID) -> Record | None:
        return self.kyc

    @asynccontextmanager
    async def kyc_work(self) -> AsyncIterator[object]:
        repo = self

        class Work:
            kyc = repo

        yield Work()

    async def record_status_check(
        self, account: AlpacaAccount, retrieved_at: datetime
    ) -> None:
        if self.kyc is None:
            return
        self.kyc["status"] = account.status
        self.kyc["status_updated_at"] = account.updated_at or retrieved_at
        self.kyc["status_checked_at"] = retrieved_at


def linked_row(checked_at: datetime | None = NOW) -> Record:
    return {
        "alpaca_account_id": "alpaca-account",
        "status": "SUBMITTED",
        "status_updated_at": NOW - timedelta(days=1),
        "status_checked_at": checked_at,
    }


def current_user(store: AccountStore) -> CurrentUser:
    return CurrentUser(
        store.user_id, uuid4(), "ana@example.com", "active", False, frozenset({"investor"})
    )


async def test_no_alpaca_call_without_a_linked_account() -> None:
    store = AccountStore(kyc=None)
    accounts = FakeAlpacaAccounts([])
    service = AccountInfoService(store.account_work, store.kyc_work, accounts, clock=FakeClock(NOW))

    result = await service.me(current_user(store))

    assert result["kyc_status"] is None and result["kyc_status_unavailable"] is False
    assert accounts.calls == []


async def test_fresh_check_is_served_from_the_cache() -> None:
    store = AccountStore(kyc=linked_row(checked_at=NOW))
    accounts = FakeAlpacaAccounts([AlpacaAccount("alpaca-account", "ACTIVE")])
    service = AccountInfoService(store.account_work, store.kyc_work, accounts, clock=FakeClock(NOW))

    result = await service.me(current_user(store))

    assert result["kyc_status"] == "SUBMITTED"
    assert accounts.calls == []


async def test_stale_check_is_refreshed_and_stored() -> None:
    store = AccountStore(kyc=linked_row(checked_at=NOW - timedelta(seconds=61)))
    live = AlpacaAccount("alpaca-account", "ACTIVE", NOW)
    accounts = FakeAlpacaAccounts([live])
    service = AccountInfoService(
        store.account_work, store.kyc_work, accounts, cache_ttl_seconds=60, clock=FakeClock(NOW)
    )

    result = await service.me(current_user(store))

    assert result["kyc_status"] == "ACTIVE"
    assert store.kyc is not None and store.kyc["status"] == "ACTIVE"
    assert store.kyc["status_checked_at"] == NOW


async def test_store_failure_still_returns_the_retrieved_status(caplog) -> None:
    store = AccountStore(kyc=linked_row(checked_at=None))
    accounts = FakeAlpacaAccounts([AlpacaAccount("alpaca-account", "ACTIVE", NOW)])
    service = AccountInfoService(store.account_work, store.kyc_work, accounts, clock=FakeClock(NOW))

    async def failing_record(account: AlpacaAccount, retrieved_at: datetime) -> None:
        raise AppError(
            503, ErrorCode.DATABASE_UNAVAILABLE, "Database operation could not complete."
        )

    store.record_status_check = failing_record  # type: ignore[method-assign]

    result = await service.me(current_user(store))

    assert result["kyc_status"] == "ACTIVE"
    assert result["kyc_status_unavailable"] is False
    assert "Database operation could not complete." not in caplog.text


async def test_database_failure_before_the_alpaca_call_is_503() -> None:
    store = AccountStore(
        kyc=linked_row(checked_at=None),
        failure=AppError(
            503, ErrorCode.DATABASE_UNAVAILABLE, "Database operation could not complete."
        ),
    )
    accounts = FakeAlpacaAccounts([AlpacaAccount("alpaca-account", "ACTIVE")])
    service = AccountInfoService(store.account_work, store.kyc_work, accounts, clock=FakeClock(NOW))

    try:
        await service.me(current_user(store))
    except AppError as exc:
        assert exc.status == 503
    else:
        raise AssertionError("expected AppError")
    assert accounts.calls == []


async def test_alpaca_failure_marks_the_status_unavailable() -> None:
    store = AccountStore(kyc=linked_row(checked_at=None))
    accounts = FakeAlpacaAccounts([AlpacaUnavailable()])
    service = AccountInfoService(store.account_work, store.kyc_work, accounts, clock=FakeClock(NOW))

    result = await service.me(current_user(store))

    assert result["kyc_status"] is None
    assert result["kyc_status_unavailable"] is True


async def test_cycle_stores_each_account_and_429_ends_it() -> None:
    accounts = FakeAlpacaAccounts(
        [
            AlpacaAccount("first", "ACTIVE"),
            AlpacaRateLimited(),
            AlpacaAccount("third", "ACTIVE"),
        ]
    )
    store = FakeKycStore(["first", "third"])
    job = KycRefreshJob(accounts, store.work, FakeClock(NOW), 900)

    await job.run_cycle()

    assert store.writes == [("first", "ACTIVE")]
    assert len(accounts.calls) == 2


async def test_cycle_skips_a_failing_account_and_continues() -> None:
    accounts = FakeAlpacaAccounts([AlpacaUnavailable(), AlpacaAccount("third", "ACTIVE")])
    store = FakeKycStore(["first", "third"])
    job = KycRefreshJob(accounts, store.work, FakeClock(NOW), 900)

    await job.run_cycle()

    assert store.writes == [("third", "ACTIVE")]


async def test_cycle_stores_nothing_once_stopping() -> None:
    accounts = FakeAlpacaAccounts([AlpacaAccount("first", "ACTIVE")])
    store = FakeKycStore(["first"])
    job = KycRefreshJob(accounts, store.work, FakeClock(NOW), 900)
    job._stopping.set()

    await job.run_cycle()

    assert store.writes == []
    assert accounts.calls == []


async def test_first_cycle_waits_one_interval_and_cycles_do_not_overlap() -> None:
    events: list[str] = []
    waits: list[float] = []

    class RecordingStore(FakeKycStore):
        async def linked_account_ids(self) -> list[str]:
            events.append("cycle")
            return []

    async def fake_wait(seconds: float) -> bool:
        waits.append(seconds)
        events.append("wait")
        return len(waits) >= 2

    job = KycRefreshJob(
        FakeAlpacaAccounts([]),
        RecordingStore().work,
        FakeClock(NOW),
        900,
        wait=fake_wait,
    )

    await job.run()

    # wait(interval) -> cycle -> wait(interval): the first cycle is one interval
    # after start and the next one starts after the previous cycle ended (23.2, 23.14).
    assert waits == [900, 900]
    assert events == ["wait", "cycle", "wait"]


def test_disabled_flag_starts_no_job(api_settings: Settings) -> None:
    app = create_app(api_settings)

    with TestClient(app):
        assert getattr(app.state, "kyc_refresh_job", None) is None


def test_enabled_flag_starts_and_stops_the_job(api_settings: Settings) -> None:
    settings = api_settings.model_copy(update={"kyc_status_refresh_enabled": "true"})
    app = create_app(settings)

    with TestClient(app):
        job = app.state.kyc_refresh_job
        assert isinstance(job, KycRefreshJob)

    assert job._task is None
