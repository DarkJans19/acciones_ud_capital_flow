from uuid import UUID, uuid4

from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.identity.adapters.outbound.persistence.tables import (
    notification_preferences,
    role_assignments,
    users,
)
from acciones_ud.identity.domain.preferences import default_preferences
from acciones_ud.shared.domain.errors import AppError, ErrorCode


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def insert(self, user: dict[str, object], role: str | None) -> UUID:
        user_id = uuid4()
        try:
            await self.session.execute(insert(users).values(id=user_id, **user))
            if role:
                await self.session.execute(
                    insert(role_assignments).values(
                        id=uuid4(),
                        user_id=user_id,
                        role_code=role,
                        valid_from=user["terms_accepted_at"],
                    )
                )
            await self.session.execute(
                insert(notification_preferences),
                [{"user_id": user_id, **p} for p in default_preferences()],
            )
        except IntegrityError as exc:
            # Match the specific constraint rather than translating every integrity error as email.
            if "uq_users_email_normalized" in str(exc.orig):
                raise AppError(
                    409, ErrorCode.EMAIL_ALREADY_REGISTERED, "Email already registered."
                ) from None
            raise
        return user_id
