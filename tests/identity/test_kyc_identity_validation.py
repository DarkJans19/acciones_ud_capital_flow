from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.adapters.inbound.http.schemas.kyc import KycSubmissionIn
from acciones_ud.identity.adapters.outbound.alpaca.fake_accounts import FakeAlpacaAccounts
from acciones_ud.identity.application.kyc import KycService
from acciones_ud.identity.domain.kyc import AlpacaAccount
from acciones_ud.identity.domain.kyc_validation import validate_adult, validate_tax_id
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.main import create_app
from acciones_ud.shared.domain.errors import AppError
from tests.identity.test_financial_profile import kyc_payload
from tests.support.clock import FakeClock


class SubmissionFake:
    def __init__(self):
        self.reservations = 0
        self.last4 = None

    async def reserve(self, user_id, now):
        self.reservations += 1
        return True

    async def complete(self, user_id, now, account, last4):
        self.last4 = last4
        return True

    @asynccontextmanager
    async def work(self):
        yield type("Work", (), {"kyc": self})()


@pytest.mark.parametrize(
    "kind,value,country",
    [
        ("PASSPORT", "aB829461", "COL"),
        ("PASSPORT", "842617395", "COL"),
        ("PASSPORT", "A2", "COL"),  # No invented passport minimum of 4/6/9.
        ("PASSPORT", "AB.82-46+1", "COL"),  # Alpaca's common character rules.
        ("COL_NIT", "900123456-7", "COL"),
        ("COL_NIT", "900.123.456-7", "COL"),
        ("COL_NIT", "1098765432", "COL"),
        ("USA_SSN", "321-54-6789", "USA"),
        ("USA_ITIN", "912345678", "USA"),
        ("NATIONAL_ID", "ID849261", "COL"),
        ("PERMANENT_RESIDENT", "PR849261", "CAN"),
        ("DRIVER_LICENSE", "DL849261", "CAN"),
        ("OTHER_GOV_ID", "G849261", "CAN"),
    ],
)
def test_supported_documents_preserve_identifier(kind, value, country):
    validate_tax_id(value, kind, country)


@pytest.mark.parametrize(
    "kind,value,country",
    [
        ("PASSPORT", "", "COL"),
        ("PASSPORT", "   ", "COL"),
        ("PASSPORT", "ABCD", "COL"),
        ("PASSPORT", "A", "COL"),
        ("PASSPORT", " A829461 ", "COL"),
        ("PASSPORT", "Á829461", "COL"),
        ("PASSPORT", "A82/9461", "COL"),
        ("PASSPORT", "A" * 40 + "2", "COL"),
        ("PASSPORT", "11111111", "COL"),
        ("PASSPORT", "1234", "COL"),
        ("PASSPORT", "9876", "COL"),
        ("UNKNOWN", "842617395", "COL"),
        ("NOT_SPECIFIED", "842617395", "COL"),
        ("COL_NIT", "AB829461", "COL"),
        ("COL_NIT", "900123456-78", "COL"),
        ("COL_NIT", "90012.3456-7", "COL"),
        ("COL_NIT", "900123456-7", "USA"),
        ("USA_SSN", "321-54-6789", "COL"),
        ("USA_SSN", "AB829461", "USA"),
        ("USA_SSN", "32154678", "USA"),
        ("USA_SSN", "000-54-6789", "USA"),
        ("USA_SSN", "666-54-6789", "USA"),
        ("USA_SSN", "321-00-6789", "USA"),
        ("USA_SSN", "321-54-0000", "USA"),
        ("USA_SSN", "123-45-6789", "USA"),
        ("USA_ITIN", "987-65-4321", "USA"),
    ],
)
async def test_invalid_document_rejected_before_reservation_or_alpaca(kind, value, country):
    clock = FakeClock()
    request = KycSubmissionIn.model_validate(kyc_payload()).to_request(clock.now(), "127.0.0.1")
    # Bypass HTTP validation deliberately: the application must enforce the invariant too.
    request = replace(
        request,
        identity={
            **request.identity,
            "tax_id": value,
            "tax_id_type": kind,
            "country_of_tax_residence": country,
        },
    )
    repo, alpaca = SubmissionFake(), FakeAlpacaAccounts([])
    with pytest.raises(AppError) as caught:
        await KycService(repo.work, alpaca, clock).submit(uuid4(), request)
    assert caught.value.status == 422
    assert repo.reservations == 0 and alpaca.calls == []
    assert value not in str(caught.value.details) if value else True


@pytest.mark.parametrize(
    "today,birthday,allowed",
    [
        ("2026-11-24", "2008-11-24", True),
        ("2026-11-24", "2008-11-25", False),
        ("2026-11-24", "2009-01-01", False),
        ("2026-11-24", "1980-05-20", True),
        ("2026-11-24", "2026-11-25", False),
        ("2026-11-24", "2026-11-24", False),
        ("2026-02-28", "2008-02-29", False),
        ("2026-03-01", "2008-02-29", True),
        ("2024-02-29", "2004-02-29", True),
        ("2024-02-29", "2008-02-29", False),
        ("2026-02-28", "2008-02-28", True),
    ],
)
async def test_age_uses_completed_calendar_years(today, birthday, allowed):
    clock = FakeClock(datetime.combine(date.fromisoformat(today), datetime.min.time(), UTC))
    body = kyc_payload()
    body["identity"]["date_of_birth"] = birthday
    request = KycSubmissionIn.model_validate(body).to_request(clock.now(), "127.0.0.1")
    repo = SubmissionFake()
    alpaca = FakeAlpacaAccounts([AlpacaAccount("test-account", "SUBMITTED", clock.now())])
    if allowed:
        validate_adult(date.fromisoformat(birthday), clock.now().date())
        result = await KycService(repo.work, alpaca, clock).submit(uuid4(), request)
        assert result == {"alpaca_account_id": "test-account", "status": "SUBMITTED"}
        assert repo.reservations == 1 and alpaca.calls == [("create", None)]
        assert repo.last4 == "6789"
    else:
        with pytest.raises(AppError) as caught:
            await KycService(repo.work, alpaca, clock).submit(uuid4(), request)
        assert caught.value.status == 422
        assert repo.reservations == 0 and alpaca.calls == []


@pytest.mark.parametrize(
    "change",
    [
        {"tax_id_type": "UNKNOWN"},
        {"tax_id_type": "COL_NIT", "tax_id": "ABC829461", "country_of_tax_residence": "COL"},
        {"tax_id": ""},
        {"date_of_birth": "2008-02-30"},
        {"date_of_birth": "2008-11-25"},
    ],
)
def test_http_invalid_identity_never_calls_provider(api_settings, change):
    app = create_app(api_settings)
    repo, alpaca = SubmissionFake(), FakeAlpacaAccounts([])
    clock = FakeClock(datetime(2026, 11, 24, tzinfo=UTC))
    app.state.kyc_service = KycService(repo.work, alpaca, clock)
    current = CurrentUser(
        uuid4(),
        uuid4(),
        "ana@example.com",
        "active",
        False,
        frozenset({"investor"}),
        frozenset({"kyc:submit"}),
    )
    app.dependency_overrides[get_current_user] = lambda: current
    body = kyc_payload()
    body["identity"].update(change)
    response = TestClient(app).post("/api/v1/kyc/account", json=body)
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert repo.reservations == 0 and alpaca.calls == []
