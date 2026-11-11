from uuid import UUID

from acciones_ud.identity.domain.account_ports import AccountWorkFactory
from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.identity.domain.interests import normalize_interests
from acciones_ud.identity.domain.preferences import merge, validate_patch
from acciones_ud.identity.domain.settings import (
    ORDER_DEFAULTS,
    PORTFOLIO_DEFAULTS,
    validate_settings,
)


class AccountService:
    def __init__(self, uow: AccountWorkFactory) -> None:
        self.uow = uow

    async def preferences(
        self, user_id: UUID, patch: list[dict[str, object]] | None = None
    ) -> Record:
        async with self.uow() as work:
            repo = work.account
            user = await repo.user(user_id, lock=patch is not None)
            stored = await repo.preferences(user_id)
            if patch is not None:
                validate_patch(patch, bool(user["phone"]), bool(user["telegram_chat_id"]))
                await repo.save_preferences(user_id, patch)
                stored = merge(stored, patch)
            return {"preferences": stored}

    async def settings(self, user_id: UUID, kind: str, values: Record | None = None) -> Record:
        if values is not None:
            validate_settings(kind, values)
        async with self.uow() as work:
            if values is not None:
                await work.account.save_settings(user_id, kind, values)
                return values
            stored = await work.account.settings(user_id, kind)
            return (
                stored
                if stored is not None
                else dict(PORTFOLIO_DEFAULTS if kind == "portfolio" else ORDER_DEFAULTS)
            )

    async def telegram(self, user_id: UUID, chat_id: str | None) -> Record:
        async with self.uow() as work:
            await work.account.user(user_id, lock=True)
            await work.account.update_user(user_id, {"telegram_chat_id": chat_id})
        return {"chat_id": chat_id}

    async def interests(self, user_id: UUID, values: list[str], level: str) -> Record:
        if level not in {"beginner", "experienced"}:
            from acciones_ud.shared.domain.errors import AppError, ErrorCode

            raise AppError(422, ErrorCode.VALIDATION_ERROR, "Invalid field: level")
        async with self.uow() as work:
            normalized = normalize_interests(values, await work.account.known_interests())
            await work.account.update_user(
                user_id, {"interests": normalized, "investor_level": level}
            )
        return {"interests": normalized, "level": level}
