from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)

from acciones_ud.identity.domain.directory import DirectoryQuery
from acciones_ud.identity.domain.models import AssignmentStatus
from acciones_ud.identity.domain.rbac import validate_validity


class AssignmentIn(BaseModel):
    valid_from: AwareDatetime
    valid_to: AwareDatetime | None = None

    @field_validator("valid_from", "valid_to", mode="before")
    @classmethod
    def timestamp_with_offset(cls, value: object) -> object:
        if value is not None and not isinstance(value, (str, datetime)):
            raise ValueError("Timestamp with timezone offset required")
        return value

    @model_validator(mode="after")
    def valid_period(self) -> "AssignmentIn":
        validate_validity(self.valid_from, self.valid_to)
        return self


class CreateAssignmentIn(AssignmentIn):
    role: str


class PremiumIn(BaseModel):
    is_premium: StrictBool


class PermissionIn(BaseModel):
    permission_code: str


class RoleAssignmentOut(BaseModel):
    id: UUID
    role: str
    valid_from: datetime
    valid_to: datetime | None
    effective: bool
    status: AssignmentStatus
    cancelled_at: datetime | None = None
    cancelled_by: UUID | None = None


class BrokerActivationOut(BaseModel):
    user_id: UUID
    account_status: Literal["active"]
    role_assignment: RoleAssignmentOut
    investor_assignment: RoleAssignmentOut


class PremiumOut(BaseModel):
    user_id: UUID
    is_premium: bool


class RoleOut(BaseModel):
    role: str
    permissions: list[str]


class PermissionOut(BaseModel):
    code: str
    description: str


KycStatus = Literal[
    "INACTIVE",
    "ONBOARDING",
    "SUBMITTED",
    "SUBMISSION_FAILED",
    "ACTION_REQUIRED",
    "ACCOUNT_UPDATED",
    "APPROVAL_PENDING",
    "APPROVED",
    "REJECTED",
    "ACTIVE",
    "ACCOUNT_CLOSED",
]


class UserDirectoryQueryIn(BaseModel):
    account_status: Literal["active", "pending_broker_activation"] | None = None
    role: Literal["investor", "broker", "administrator"] | None = None
    q: str | None = None
    # A plain bool would also accept 1, 0, yes, no, on and off (20.9).
    broker_requested: Literal["true", "false"] | None = None
    kyc_status: KycStatus | None = None
    kyc_link_state: Literal["none", "unlinked", "linked"] | None = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @field_validator("q")
    @classmethod
    def trimmed_q(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not 1 <= len(trimmed) <= 100:
            raise ValueError("q must have 1 to 100 characters after trimming")
        return trimmed

    def to_domain(self) -> DirectoryQuery:
        return DirectoryQuery(
            account_status=self.account_status,
            role=self.role,
            q=self.q,
            broker_requested=(
                None if self.broker_requested is None else self.broker_requested == "true"
            ),
            kyc_status=self.kyc_status,
            kyc_link_state=self.kyc_link_state,
            limit=self.limit,
            offset=self.offset,
        )


class UserDirectoryEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    email: str
    first_names: str
    last_names: str
    phone: str | None
    country: str | None
    account_status: str
    is_premium: bool
    roles: list[str]
    broker_requested: bool
    registered_at: datetime
    kyc_link_state: Literal["none", "unlinked", "linked"]
    kyc_alpaca_account_id: str | None
    kyc_status: str | None
    kyc_status_updated_at: datetime | None
    kyc_status_checked_at: datetime | None
    kyc_reserved_at: datetime | None
    kyc_created_at: datetime | None


class UserDirectoryPageOut(BaseModel):
    items: list[UserDirectoryEntryOut]
    total: int
    limit: int
    offset: int
