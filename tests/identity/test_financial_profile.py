from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from acciones_ud.identity.adapters.inbound.http.schemas.kyc import KycSubmissionIn
from acciones_ud.identity.adapters.outbound.alpaca.kyc_mapping import financial_fields
from acciones_ud.identity.domain.financial_profile import (
    FinancialProfile,
    FinancialRange,
)
from acciones_ud.identity.domain.financial_profile import (
    FinancialRangeCode as Code,
)
from acciones_ud.shared.domain.errors import AppError


def kyc_payload() -> dict:
    return {
        "identity": {
            "given_name": "Identity",
            "family_name": "Test",
            "date_of_birth": "1990-01-01",
            "tax_id": "123-45-6789",
            "tax_id_type": "USA_SSN",
            "country_of_citizenship": "USA",
            "country_of_tax_residence": "USA",
            "funding_source": ["savings"],
            "annual_income_range": "RANGE_3",
            "liquid_net_worth_range": "RANGE_2",
            "total_net_worth_range": "RANGE_4",
        },
        "contact": {
            "email_address": "identity@example.com",
            "phone_number": "+15555550100",
            "street_address": ["123 Test Street"],
            "city": "New York",
            "state": "NY",
            "postal_code": "10001",
            "country": "USA",
        },
        "employment_status": "student",
        "disclosures": {
            "is_control_person": False,
            "is_affiliated_exchange_or_finra": False,
            "is_politically_exposed": False,
            "immediate_family_exposed": False,
        },
        "agreements": {
            "customer_agreement": True,
            "account_agreement": True,
            "margin_agreement": True,
        },
    }


@pytest.mark.parametrize(
    "code,low,high",
    [
        (Code.RANGE_1, "0.00", "24999.99"),
        (Code.RANGE_2, "25000.00", "49999.99"),
        (Code.RANGE_3, "50000.00", "99999.99"),
        (Code.RANGE_4, "100000.00", "249999.99"),
        (Code.RANGE_5, "250000.00", "499999.99"),
        (Code.RANGE_6, "500000.00", "999999.99"),
    ],
)
def test_every_range_and_all_six_alpaca_fields(code: Code, low: str, high: str) -> None:
    selected = FinancialRange(code)
    assert selected.limits == (Decimal(low), Decimal(high))
    mapped = financial_fields(FinancialProfile(selected, selected, selected))
    assert len(mapped) == 6
    for prefix in ("annual_income", "liquid_net_worth", "total_net_worth"):
        assert mapped[prefix + "_min"] == low
        assert mapped[prefix + "_max"] == high
    assert all(isinstance(v, str) for v in mapped.values())


@pytest.mark.parametrize(
    "low,high",
    [
        (Decimal("0"), Decimal("0")),
        (Decimal("1000000.01"), Decimal("999999999999999999999999999.99")),
        (Decimal("0.001"), Decimal("0.002")),
    ],
)
def test_custom_preserves_precision_and_has_no_catalog_ceiling(low: Decimal, high: Decimal) -> None:
    selected = FinancialRange(Code.CUSTOM, low, high)
    mapped = financial_fields(FinancialProfile(selected, selected, selected))
    assert Decimal(mapped["annual_income_min"]) == low
    assert Decimal(mapped["annual_income_max"]) == high
    assert "E" not in mapped["annual_income_max"]


@pytest.mark.parametrize(
    "low,high",
    [
        (None, None),
        (Decimal("0"), None),
        (None, Decimal("1")),
        (Decimal("-0.01"), Decimal("1")),
        (Decimal("2"), Decimal("1")),
        (Decimal("NaN"), Decimal("1")),
        (Decimal("0"), Decimal("Infinity")),
        (True, Decimal("1")),
        (0.0, Decimal("1")),
    ],
)
def test_invalid_custom(low: object, high: object) -> None:
    with pytest.raises(AppError):
        FinancialRange(Code.CUSTOM, low, high)


def test_preset_cannot_be_overridden_and_financial_consistency() -> None:
    with pytest.raises(AppError):
        FinancialRange(Code.RANGE_1, Decimal("0"), Decimal("1"))
    for low, high in (("20", "30"), ("0", "50")):
        with pytest.raises(AppError):
            FinancialProfile(
                FinancialRange(Code.RANGE_6),
                FinancialRange(Code.CUSTOM, Decimal(low), Decimal(high)),
                FinancialRange(Code.CUSTOM, Decimal("10"), Decimal("40")),
            )


@given(
    st.decimals(min_value=0, max_value=10**20, places=2, allow_nan=False, allow_infinity=False),
    st.decimals(min_value=0, max_value=10**20, places=2, allow_nan=False, allow_infinity=False),
)
def test_custom_round_trip(first: Decimal, second: Decimal) -> None:
    low, high = sorted([first, second])
    selected = FinancialRange(Code.CUSTOM, low, high)
    mapped = financial_fields(FinancialProfile(selected, selected, selected))
    assert Decimal(mapped["total_net_worth_min"]) == low
    assert Decimal(mapped["total_net_worth_max"]) == high


def test_http_schema_uses_product_codes_and_validates_custom() -> None:
    body = kyc_payload()
    KycSubmissionIn.model_validate(body)
    body["identity"]["annual_income_range"] = "CUSTOM"
    with pytest.raises(AppError):
        KycSubmissionIn.model_validate(body)
    body["identity"].update(
        annual_income_custom_min="1000000.00", annual_income_custom_max="2000000.00"
    )
    assert KycSubmissionIn.model_validate(
        body
    ).identity.financial_profile().annual_income.limits == (
        Decimal("1000000.00"),
        Decimal("2000000.00"),
    )
    body["identity"]["annual_income_range"] = "50000-100000"
    with pytest.raises(ValidationError):
        KycSubmissionIn.model_validate(body)
