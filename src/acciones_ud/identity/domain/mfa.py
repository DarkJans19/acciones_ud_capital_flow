from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class Challenge:
    id: UUID
    user_id: UUID
    expires_at: datetime
    failed_attempts: int = 0
    used_at: datetime | None = None
    invalidated_at: datetime | None = None

    def usable(self, now: datetime) -> bool:
        return (
            now < self.expires_at
            and self.failed_attempts < 5
            and self.used_at is None
            and self.invalidated_at is None
        )

    def fail(self, now: datetime) -> None:
        self.failed_attempts += 1
        if self.failed_attempts >= 5:
            self.invalidated_at = now

    def succeed(self, now: datetime) -> bool:
        if not self.usable(now):
            return False
        self.used_at = now
        return True
