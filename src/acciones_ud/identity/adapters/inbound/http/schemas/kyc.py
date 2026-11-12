from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

import pycountry
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from acciones_ud.identity.domain.financial_profile import (
    FinancialProfile,
    FinancialRange,
    FinancialRangeCode,
)
from acciones_ud.identity.domain.kyc_submission import AccountOpeningRequest
from acciones_ud.identity.domain.validation import valid_email, valid_phone


class KycModel(BaseModel):
    model_config = ConfigDict(extra="ignore", hide_input_in_errors=True)


class KycIdentityIn(KycModel):
    given_name: str = Field(min_length=1, max_length=100)
    family_name: str = Field(min_length=1, max_length=100)
    date_of_birth: date
    tax_id: str = Field(min_length=4, max_length=100, repr=False)
    tax_id_type: str = Field(min_length=1, max_length=50)
    country_of_citizenship: str
    country_of_tax_residence: str
    funding_source: list[
        Literal[
            "employment_income",
            "investments",
            "inheritance",
            "business_income",
            "savings",
            "family",
        ]
    ] = Field(min_length=1)
    annual_income_range: FinancialRangeCode
    liquid_net_worth_range: FinancialRangeCode
    total_net_worth_range: FinancialRangeCode
    annual_income_custom_min: Decimal | None = None
    annual_income_custom_max: Decimal | None = None
    liquid_net_worth_custom_min: Decimal | None = None
    liquid_net_worth_custom_max: Decimal | None = None
    total_net_worth_custom_min: Decimal | None = None
    total_net_worth_custom_max: Decimal | None = None

    @field_validator("given_name", "family_name", mode="before")
    @classmethod
    def trim(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("country_of_citizenship", "country_of_tax_residence")
    @classmethod
    def country(cls, value: str) -> str:
        value = value.upper()
        if len(value) != 3 or pycountry.countries.get(alpha_3=value) is None:
            raise ValueError("ISO alpha-3 country required")
        return value

    def financial_profile(self) -> FinancialProfile:
        return FinancialProfile(
            FinancialRange(
                self.annual_income_range,
                self.annual_income_custom_min,
                self.annual_income_custom_max,
            ),
            FinancialRange(
                self.liquid_net_worth_range,
                self.liquid_net_worth_custom_min,
                self.liquid_net_worth_custom_max,
            ),
            FinancialRange(
                self.total_net_worth_range,
                self.total_net_worth_custom_min,
                self.total_net_worth_custom_max,
            ),
        )

    @model_validator(mode="after")
    def validate_profile(self) -> "KycIdentityIn":
        self.financial_profile()
        return self


class KycContactIn(KycModel):
    email_address: str
    phone_number: str
    street_address: list[str] = Field(min_length=1, max_length=3)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    postal_code: str = Field(min_length=1, max_length=20)
    country: str

    @field_validator("email_address")
    @classmethod
    def email(cls, value: str) -> str:
        if not valid_email(value):
            raise ValueError("Invalid email_address")
        return value.strip()

    @field_validator("phone_number")
    @classmethod
    def phone(cls, value: str) -> str:
        if not valid_phone(value):
            raise ValueError("Invalid phone_number")
        return value

    @field_validator("country")
    @classmethod
    def country_code(cls, value: str) -> str:
        return KycIdentityIn.country(value)

    @field_validator("street_address")
    @classmethod
    def address(cls, values: list[str]) -> list[str]:
        if any(not v.strip() or len(v) > 200 for v in values):
            raise ValueError("Invalid street_address")
        return values


class DisclosuresIn(KycModel):
    is_control_person: StrictBool
    is_affiliated_exchange_or_finra: StrictBool
    is_politically_exposed: StrictBool
    immediate_family_exposed: StrictBool


class AgreementsIn(KycModel):
    customer_agreement: StrictBool
    account_agreement: StrictBool
    margin_agreement: StrictBool

    @field_validator("customer_agreement")
    @classmethod
    def accepted(cls, value: bool) -> bool:
        if not value:
            raise ValueError("customer_agreement must be accepted")
        return value


class KycSubmissionIn(KycModel):
    identity: KycIdentityIn = Field(repr=False)
    contact: KycContactIn = Field(repr=False)
    employment_status: Literal["employed", "unemployed", "retired", "student"]
    disclosures: DisclosuresIn
    agreements: AgreementsIn

    def to_request(self, now: datetime, ip: str) -> AccountOpeningRequest:
        identity = self.identity.model_dump(
            exclude={
                name for name in KycIdentityIn.model_fields if "range" in name or "custom" in name
            }
        )
        identity["date_of_birth"] = self.identity.date_of_birth.isoformat()
        return AccountOpeningRequest(
            identity,
            self.contact.model_dump(),
            self.identity.financial_profile(),
            self.employment_status,
            self.disclosures.model_dump(),
            self.agreements.model_dump(),
            now,
            ip,
        )


class KycAccountOut(KycModel):
    alpaca_account_id: str
    status: str


class KycStatusOut(KycModel):
    has_account: bool
    status: str | None
    status_updated_at: datetime | None
    can_trade: bool
    stale: bool


class KycReconcileIn(KycModel):
    alpaca_account_id: UUID | None = None


class KycReconcileOut(KycModel):
    user_id: UUID
    alpaca_account_id: str
    status: str | None
    outcome: Literal["linked", "already_linked"]
