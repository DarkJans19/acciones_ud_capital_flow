from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
import pytest
from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.identity.adapters.outbound.alpaca.accounts_client import AlpacaAccountsClient
from acciones_ud.identity.adapters.outbound.alpaca.fake_accounts import FakeAlpacaAccounts
from acciones_ud.identity.application.account import AccountService
from acciones_ud.identity.application.account_info import AccountInfoService
from acciones_ud.identity.application.kyc import KycService
from acciones_ud.identity.domain.account_ports import AccountWork
from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.identity.domain.interests import normalize_interests
from acciones_ud.identity.domain.kyc import AlpacaAccount, can_trade, financial_range
from acciones_ud.identity.domain.kyc_ports import KycWork
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.identity.domain.preferences import default_preferences, merge, validate_patch
from acciones_ud.identity.domain.redaction import last4, redact
from acciones_ud.identity.domain.settings import validate_settings
from acciones_ud.shared.domain.alpaca_errors import (
    AlpacaAuthError,
    AlpacaRateLimited,
    AlpacaUnavailable,
    AlpacaValidationError,
)
from acciones_ud.shared.domain.errors import AppError
from tests.support.clock import FakeClock


class AccountFake:
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
            "broker_requested": False,
            "telegram_chat_id": None,
            "interests": [],
            "investor_level": None,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "totp_confirmed_at": None,
            "password_hash": "DO-NOT-LEAK",
            "totp_secret_enc": "PRIVATE",
        }
        self.prefs = default_preferences()
        self.saved: dict[str, Record] = {}
        self.writes = 0

    async def user(self, user_id: UUID, *, lock: bool = False) -> Record:
        assert user_id == self.user_id
        return self.record

    async def preferences(self, user_id: UUID) -> list[dict[str, object]]:
        return deepcopy(self.prefs)

    async def save_preferences(self, user_id: UUID, values: list[dict[str, object]]) -> None:
        self.prefs = merge(self.prefs, values)
        self.writes += 1

    async def settings(self, user_id: UUID, kind: str) -> Record | None:
        return self.saved.get(kind)

    async def save_settings(self, user_id: UUID, kind: str, values: Record) -> None:
        self.saved[kind] = values
        self.writes += 1

    async def update_user(self, user_id: UUID, values: Record) -> None:
        self.record.update(values)
        self.writes += 1

    async def known_interests(self) -> list[str]:
        return ["NYSE", "NASDAQ", "Technology"]

    @asynccontextmanager
    async def work(self) -> AsyncIterator[AccountWork]:
        repository = self

        class Work:
            account = repository

        snapshot = deepcopy(self.__dict__)
        try:
            yield Work()
        except BaseException:
            self.__dict__.update(snapshot)
            raise


class KycFake:
    def __init__(self, row: Record | None = None) -> None:
        self.row = row
        self.writes = 0

    async def get(self, user_id: UUID) -> Record | None:
        return self.row

    async def record_status_check(self, account: AlpacaAccount, retrieved_at: datetime) -> None:
        assert self.row
        checked = self.row.get("status_checked_at")
        if checked is not None and checked > retrieved_at:
            return
        if self.row["status"] != account.status:
            self.row["status"] = account.status
            self.row["status_updated_at"] = account.updated_at or retrieved_at
        self.row["status_checked_at"] = retrieved_at
        self.writes += 1

    async def linked_account_ids(self) -> list[str]:
        if self.row and self.row.get("alpaca_account_id"):
            return [self.row["alpaca_account_id"]]
        return []

    @asynccontextmanager
    async def work(self) -> AsyncIterator[KycWork]:
        repo = self

        class Work:
            kyc = repo

        yield Work()


async def test_account_defaults_and_atomic_rejection() -> None:
    repo = AccountFake()
    service = AccountService(repo.work)
    assert (await service.settings(repo.user_id, "portfolio"))["view_type"] == "table"
    assert (await service.settings(repo.user_id, "orders"))["daily_order_limit"] == 50
    assert repo.writes == 0
    before = deepcopy(repo.prefs)
    with pytest.raises(AppError):
        await service.preferences(
            repo.user_id,
            [
                {"event_type": "market_open", "channel": "email", "enabled": True},
                {"event_type": "market_open", "channel": "telegram", "enabled": True},
            ],
        )
    assert repo.prefs == before and repo.writes == 0
    await service.telegram(repo.user_id, "123456")
    result = await service.preferences(
        repo.user_id, [{"event_type": "market_open", "channel": "telegram", "enabled": True}]
    )
    assert len(result["preferences"]) == 28
    assert (await service.interests(repo.user_id, ["nyse", "NYSE", "technology"], "beginner")) == {
        "interests": ["NYSE", "Technology"],
        "level": "beginner",
    }
    snapshot = deepcopy(repo.record)
    with pytest.raises(AppError):
        await service.interests(repo.user_id, ["UNKNOWN"], "experienced")
    assert repo.record == snapshot


# Feature: identity-market-backend, Property 10: Notification preference merge round trip
@given(
    st.lists(
        st.tuples(st.integers(0, 6), st.integers(1, 3), st.booleans()), unique_by=lambda x: x[:2]
    )
)
def test_preference_merge(pairs: list[tuple[int, int, bool]]) -> None:
    stored = default_preferences()
    events = list(dict.fromkeys(str(p["event_type"]) for p in stored))
    channels = ["in_app", "email", "sms", "telegram"]
    patch = [{"event_type": events[e], "channel": channels[c], "enabled": v} for e, c, v in pairs]
    result = merge(stored, patch)
    assert len(result) == 28
    reference = {(p["event_type"], p["channel"]): p["enabled"] for p in stored + patch}
    assert {(p["event_type"], p["channel"]): p["enabled"] for p in result} == reference


# Feature: identity-market-backend, Property 11: Rejected preference patches change nothing
@given(st.sampled_from(["in_app", "telegram", "sms"]), st.booleans())
def test_invalid_prefs(channel: str, enabled: bool) -> None:
    patch = [{"event_type": "market_open", "channel": channel, "enabled": enabled}]
    before = deepcopy(patch)
    if (channel == "in_app" and not enabled) or (channel != "in_app" and enabled):
        with pytest.raises(AppError):
            validate_patch(patch, False, False)
    else:
        validate_patch(patch, False, False)
    assert patch == before


# Feature: identity-market-backend, Property 12: Settings validators accept exactly their domains
@given(st.integers(-1000, 2000), st.booleans())
def test_order_limits(limit: int, flag: bool) -> None:
    values = {
        "default_order_type": "market",
        "daily_order_limit": limit,
        "high_order_threshold_usd": Decimal("10.00"),
        "extra_confirmation": flag,
    }
    if 1 <= limit <= 1000:
        validate_settings("orders", values)
    else:
        with pytest.raises(AppError):
            validate_settings("orders", values)


# Feature: identity-market-backend, Property 13: Tax identifier never leaks
@given(st.from_regex(r"[0-9]{9}", fullmatch=True), st.text())
def test_tax_redaction(tax: str, prefix: str) -> None:
    assert tax not in redact(prefix + tax + " 123456789 ", tax)
    assert len(redact(prefix + tax, tax)) <= 500
    assert last4(tax) == tax[-4:]


# Feature: identity-market-backend, Property 14: can_trade follows the Alpaca status
@given(st.one_of(st.none(), st.text(), st.just("ACTIVE")))
def test_can_trade(status: str | None) -> None:
    assert can_trade(status) == (status == "ACTIVE")


# Feature: identity-market-backend, Property 15: Interest normalization
@given(
    st.lists(st.sampled_from(["NYSE", "nyse", "Technology", "technology"]), min_size=1, max_size=20)
)
def test_interests(values: list[str]) -> None:
    normalized = normalize_interests(values, ["NYSE", "Technology"])
    assert normalized == list(
        dict.fromkeys("NYSE" if v.lower() == "nyse" else "Technology" for v in values)
    )


async def test_status_fallback_and_read_only_me() -> None:
    clock = FakeClock()
    row = {
        "alpaca_account_id": "account-id",
        "status": "SUBMITTED",
        "status_updated_at": clock.now(),
    }
    repo = KycFake(row)
    accounts = FakeAlpacaAccounts(
        [AlpacaUnavailable(), AlpacaAccount("account-id", "ACTIVE", clock.now())]
    )
    service = KycService(repo.work, accounts, clock)
    stale = await service.status(uuid4())
    assert stale["stale"] and not stale["can_trade"] and repo.writes == 0
    live = await service.status(uuid4())
    assert not live["stale"] and live["can_trade"] and repo.writes == 1
    user_repo = AccountFake()
    info = AccountInfoService(user_repo.work, repo.work, FakeAlpacaAccounts([]), clock=clock)
    current = CurrentUser(
        user_repo.user_id, uuid4(), "ana@example.com", "pending_broker_activation", False
    )
    result = await info.me(current)
    # The stored status check is fresh, so /users/me serves the cache (23.4).
    assert result["kyc_status"] == "ACTIVE" and not result["kyc_status_unavailable"]
    assert result["broker_requested"] is False
    assert "DO-NOT-LEAK" not in str(result) and "PRIVATE" not in str(result)
    assert user_repo.writes == 0 and repo.writes == 1
    empty = KycFake()
    fake = FakeAlpacaAccounts([])
    assert not (await KycService(empty.work, fake, clock).status(uuid4()))["has_account"]
    assert fake.calls == []


@pytest.mark.parametrize(
    "status,error", [(429, AlpacaRateLimited), (500, AlpacaUnavailable), (401, AlpacaAuthError)]
)
async def test_broker_errors_and_basic_auth(status: int, error: type[Exception]) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.url.path == "/v1/accounts/account-id"
        assert request.headers["authorization"].startswith("Basic ")
        return httpx.Response(status, json={"message": "sensitive response"})

    async with httpx.AsyncClient(
        base_url="https://broker-api.sandbox.alpaca.markets",
        auth=httpx.BasicAuth("key", "secret"),
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(error):
            await AlpacaAccountsClient(client).get_account("account-id")
    assert len(calls) == 1


async def test_broker_creation_redacts_validation_and_rejects_bad_response() -> None:
    async with httpx.AsyncClient(
        base_url="https://sandbox.test",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                422, json={"message": "Invalid tax 123-45-6789 and 123456789"}
            )
        ),
    ) as client:
        with pytest.raises(AlpacaValidationError) as caught:
            await AlpacaAccountsClient(client).create_account(
                {"identity": {"tax_id": "123-45-6789"}}
            )
        assert "123-45-6789" not in str(caught.value) and "123456789" not in str(caught.value)
    async with httpx.AsyncClient(
        base_url="https://sandbox.test",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"id": "account-id", "secret": "not-an-account"}
            )
        ),
    ) as client:
        with pytest.raises(AlpacaUnavailable):
            await AlpacaAccountsClient(client).get_account("account-id")


def test_financial_ranges_require_approval() -> None:
    with pytest.raises(AppError):
        financial_range("invented-range", {})
    assert financial_range("approved", {"approved": (Decimal("1"), Decimal("2"))}) == ("1", "2")
