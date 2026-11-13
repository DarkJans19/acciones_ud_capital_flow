from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class UserMeOut(BaseModel):
    user_id: UUID
    first_names: str
    last_names: str
    email: str
    phone: str
    country: str
    account_status: str
    registered_at: datetime
    contracted_plan: None = None
    is_premium: bool
    broker_requested: bool
    associated_broker: None = None
    roles: list[str]
    kyc_status: str | None
    kyc_status_unavailable: bool
    interests: list[str]
    investor_level: str | None
    mfa_enrolled: bool
