from uuid import UUID

from acciones_ud.identity.domain.audit import AuditAction, build_entry
from acciones_ud.identity.domain.ports import PasswordHasher, UnitOfWorkFactory
from acciones_ud.identity.domain.registration import build_new_user
from acciones_ud.shared.domain.clock import Clock


class RegistrationService:
    def __init__(self, uow: UnitOfWorkFactory, hasher: PasswordHasher, clock: Clock) -> None:
        self.uow = uow
        self.hasher = hasher
        self.clock = clock

    async def register(
        self,
        kind: str,
        payload: dict[str, object],
        actor_id: UUID | None = None,
    ) -> dict[str, object]:
        user, role = build_new_user(kind, payload)
        user["password_hash"] = self.hasher.hash(str(payload["password"]))
        user["terms_accepted_at"] = self.clock.now()
        async with self.uow() as work:
            user_id = await work.users.insert(user, role)
            if kind == "administrator" and actor_id is not None:
                await work.audit.append(
                    build_entry(
                        AuditAction.ADMINISTRATOR_CREATED,
                        actor_id,
                        "user",
                        str(user_id),
                        {},
                        self.clock.now(),
                    )
                )
        return {"user_id": user_id, "account_status": user["account_status"]}

    async def register_investor(self, payload: dict[str, object]) -> dict[str, object]:
        return await self.register("investor", payload)

    async def register_broker(self, payload: dict[str, object]) -> dict[str, object]:
        return await self.register("broker", payload)

    async def create_administrator(
        self, payload: dict[str, object], actor_id: UUID | None = None
    ) -> dict[str, object]:
        return await self.register("administrator", payload, actor_id)
