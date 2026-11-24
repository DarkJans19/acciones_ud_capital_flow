from dataclasses import asdict, replace
from uuid import UUID, uuid4

from acciones_ud.admin.application.step_up import StepUp
from acciones_ud.admin.domain import audit
from acciones_ud.admin.domain.errors import conflict, invalid, not_found
from acciones_ud.admin.domain.model import AccountRestriction, Raw
from acciones_ud.admin.domain.pagination import paginate
from acciones_ud.admin.domain.ports import AdminWorkFactory, UserReaderPort
from acciones_ud.shared.domain.audit_entry import RequestMeta
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import ErrorCode


def validate_evidence(text: str, refs: list[Raw]) -> None:
    if len(text) > 2000 or len(refs) > 20:
        raise invalid("evidence")
    for ref in refs:
        if (
            set(ref) != {"source", "id"}
            or ref["source"] not in {"admin", "orders", "brokers", "auth", "execution"}
            or not isinstance(ref["id"], str)
            or not 1 <= len(ref["id"]) <= 256
        ):
            raise invalid("evidence_refs")


def restriction_out(value: AccountRestriction) -> Raw:
    return {**asdict(value), "status": "lifted" if value.lifted_at else "active"}


class RestrictionService:
    def __init__(
        self, uow: AdminWorkFactory, users: UserReaderPort, step_up: StepUp, clock: Clock
    ) -> None:
        self.uow, self.users, self.step_up, self.clock = uow, users, step_up, clock

    async def restrict(
        self,
        user: UUID,
        reason: str,
        text: str,
        refs: list[Raw],
        actor: UUID,
        code: str | None,
        meta: RequestMeta,
    ) -> Raw:
        await self.step_up.verify(actor, code)
        if user == actor:
            raise invalid("user_id", "self_restriction")
        validate_evidence(text, refs)
        if await self.users.summary(user, self.clock.now()) is None:
            raise not_found("user")
        now = self.clock.now()
        async with self.uow() as work:
            await work.restrictions.lock_user(user)
            active = next((r for r in await work.restrictions.all(user) if not r.lifted_at), None)
            if active:
                raise conflict(ErrorCode.RESTRICTION_ALREADY_ACTIVE, restriction_id=str(active.id))
            value = AccountRestriction(uuid4(), user, "trading", reason, text, refs, actor, now)
            await work.restrictions.insert(value)
            await work.audit.append(
                audit.build(
                    "account_restricted",
                    actor,
                    "user",
                    str(user),
                    {
                        "restriction_id": value.id,
                        "restriction_type": "trading",
                        "reason": reason,
                        "evidence": {"text": text, "refs": refs},
                    },
                    now,
                    meta,
                )
            )
        return restriction_out(value)

    async def lift(
        self,
        ident: UUID,
        reason: str,
        text: str,
        refs: list[Raw],
        actor: UUID,
        code: str | None,
        meta: RequestMeta,
    ) -> Raw:
        await self.step_up.verify(actor, code)
        validate_evidence(text, refs)
        now = self.clock.now()
        async with self.uow() as work:
            value = await work.restrictions.get_for_update(ident)
            if value is None:
                raise not_found("account_restriction")
            if value.lifted_at:
                raise conflict(ErrorCode.RESTRICTION_NOT_ACTIVE)
            updated = replace(
                value,
                lifted_at=now,
                lifted_by=actor,
                lift_reason=reason,
                lift_evidence_text=text,
                lift_evidence_refs=refs,
            )
            if not await work.restrictions.lift(updated):
                raise conflict(ErrorCode.RESTRICTION_NOT_ACTIVE)
            await work.audit.append(
                audit.build(
                    "account_rehabilitated",
                    actor,
                    "user",
                    str(value.user_id),
                    {
                        "restriction_id": ident,
                        "restriction_type": "trading",
                        "reason": reason,
                        "evidence": {"text": text, "refs": refs},
                    },
                    now,
                    meta,
                )
            )
        return restriction_out(updated)

    async def page(
        self, user: UUID | None, status: str | None, cursor: str | None, size: int
    ) -> Raw:
        if status and status not in {"active", "lifted"}:
            raise invalid("status")
        async with self.uow() as work:
            rows = [
                r
                for r in await work.restrictions.all(user)
                if status is None or ("lifted" if r.lifted_at else "active") == status
            ]
        page = paginate(rows, lambda r: (r.restricted_at.isoformat(), str(r.id)), cursor, size)
        return {"items": [restriction_out(r) for r in page.items], "next_cursor": page.next_cursor}
