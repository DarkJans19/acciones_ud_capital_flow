from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    ValidationInfo,
    field_validator,
    model_validator,
)

from acciones_ud.identity.domain import validation as rules

TrimmedName = Annotated[str, Field(min_length=1, max_length=100)]


class RegisterBaseIn(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=False, hide_input_in_errors=True)
    first_names: TrimmedName
    last_names: TrimmedName
    email: str
    phone: str
    country: str
    password: str = Field(repr=False)
    terms_accepted: StrictBool
    monthly_report: StrictBool
    interests: list[Annotated[str, Field(min_length=1, max_length=50)]] = Field(
        default_factory=list, max_length=20
    )
    investor_level: Literal["beginner", "experienced"] | None = None
    broker_requested: StrictBool = False
    premium_requested: StrictBool = False

    @field_validator("first_names", "last_names", mode="before")
    @classmethod
    def trim_names(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email", "phone", "country", "password")
    @classmethod
    def validate_field(cls, value: str, info: ValidationInfo) -> str:
        name = info.field_name or ""
        check = {
            "email": rules.valid_email,
            "phone": rules.valid_phone,
            "country": rules.valid_country,
            "password": rules.valid_password,
        }[name]
        if not check(value):
            raise ValueError(f"Invalid {name}")
        return value.upper() if name == "country" else value

    @field_validator("terms_accepted")
    @classmethod
    def terms_required(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Terms must be accepted")
        return value


class RegisterInvestorIn(RegisterBaseIn):
    pass


class RegisterBrokerIn(RegisterBaseIn):
    firm_name: str = Field(min_length=1, max_length=200)
    license_number: str = Field(min_length=1, max_length=50)

    @field_validator("firm_name", "license_number", mode="before")
    @classmethod
    def trim_broker_fields(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class RegistrationOut(BaseModel):
    user_id: UUID
    account_status: Literal["active", "pending_broker_activation"]


class LoginIn(BaseModel):
    email: str
    password: str = Field(repr=False, max_length=128)


class EnrollmentOut(BaseModel):
    secret: str
    otpauth_uri: str


class LoginOut(BaseModel):
    mfa_token: str
    mfa_expires_at: datetime
    totp_enrollment: EnrollmentOut | None


class MfaVerifyIn(BaseModel):
    mfa_token: str = Field(min_length=1, max_length=128, repr=False)
    code: str | None = Field(default=None, pattern=r"^[0-9]{6}$", repr=False)
    recovery_code: str | None = Field(default=None, pattern=r"^[A-Z0-9]{10}$", repr=False)

    @field_validator("recovery_code", mode="before")
    @classmethod
    def normalize_recovery(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def exactly_one(self) -> "MfaVerifyIn":
        if (self.code is None) == (self.recovery_code is None):
            from pydantic import ValidationError
            from pydantic_core import InitErrorDetails

            raise ValidationError.from_exception_data(
                "MfaVerifyIn",
                [
                    InitErrorDetails(
                        type="value_error",
                        loc=(field,),
                        input=None,
                        ctx={"error": ValueError("Supply exactly one MFA method")},
                    )
                    for field in ("code", "recovery_code")
                ],
            )
        return self


class AuthUserOut(BaseModel):
    user_id: UUID
    email: str
    account_status: str


class MfaVerifyOut(BaseModel):
    user: AuthUserOut
    recovery_codes: list[str] | None
    recovery_codes_remaining: int | None
