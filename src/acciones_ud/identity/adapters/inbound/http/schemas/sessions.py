from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RefreshOut(BaseModel):
    access_expires_at: datetime
    refresh_expires_at: datetime


class SessionOut(BaseModel):
    session_id: UUID
    user_agent: str
    ip_address: str
    created_at: datetime
    last_used_at: datetime
    current: bool


class RevokedCountOut(BaseModel):
    revoked_count: int
