from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.json_schema import SkipJsonSchema

from acciones_ud.identity.domain.profile import normalize_profile_patch


class ProfilePatchIn(BaseModel):
    """Omission preserves data; explicit null and protected fields are rejected."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    first_names: str | SkipJsonSchema[None] = Field(
        default=None, description="Omit to preserve; explicit null is rejected."
    )
    last_names: str | SkipJsonSchema[None] = Field(
        default=None, description="Omit to preserve; explicit null is rejected."
    )
    phone: str | SkipJsonSchema[None] = Field(
        default=None, description="E.164. Omit to preserve; explicit null is rejected."
    )
    country: str | SkipJsonSchema[None] = Field(
        default=None, description="ISO alpha-2. Omit to preserve; explicit null is rejected."
    )

    @model_validator(mode="after")
    def validate_patch(self) -> "ProfilePatchIn":
        normalize_profile_patch(self.model_dump(exclude_unset=True))
        return self


class PersonalProfileOut(BaseModel):
    first_names: str
    last_names: str
    phone: str
    country: str


class AssociatedBrokerOut(BaseModel):
    id: UUID
    name: str
    firm_name: str
    since: datetime


class UserMeOut(BaseModel):
    user_id: UUID
    first_names: str
    last_names: str
    email: str
    phone: str
    country: str
    account_status: str
    registered_at: datetime
    contracted_plan: Literal["monthly", "annual"] | None = None
    is_premium: bool
    broker_requested: bool
    associated_broker: AssociatedBrokerOut | None = None
    roles: list[str]
    kyc_status: str | None
    kyc_status_unavailable: bool
    interests: list[str]
    investor_level: str | None
    mfa_enrolled: bool
