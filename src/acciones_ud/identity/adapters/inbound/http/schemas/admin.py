from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, StrictBool, field_validator, model_validator

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
