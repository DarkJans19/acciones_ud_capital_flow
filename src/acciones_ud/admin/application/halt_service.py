from dataclasses import asdict, replace
from datetime import datetime
from uuid import UUID, uuid4

from acciones_ud.admin.application.step_up import StepUp
from acciones_ud.admin.domain import audit, halts
from acciones_ud.admin.domain.errors import conflict, invalid, not_found
from acciones_ud.admin.domain.model import Raw, TradingHalt
from acciones_ud.admin.domain.pagination import paginate
from acciones_ud.admin.domain.ports import AdminWorkFactory, MarketCatalogPort
from acciones_ud.shared.domain.audit_entry import RequestMeta
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import ErrorCode


def halt_out(value: TradingHalt, at: datetime) -> Raw:
    return {**asdict(value), "scope": value.scope, "status": halts.effective_status(value, at)}


class HaltService:
    def __init__(
        self, uow: AdminWorkFactory, markets: MarketCatalogPort, step_up: StepUp, clock: Clock
    ) -> None:
        self.uow, self.markets, self.step_up, self.clock = uow, markets, step_up, clock

    async def activate(
        self,
        scope: str,
        reason: str,
        starts: datetime | None,
        ends: datetime | None,
        actor: UUID,
        code: str | None,
        meta: RequestMeta,
    ) -> Raw:
        now = self.clock.now()
        await self.step_up.verify(actor, code)
        if scope != "global" and scope not in {m["code"] for m in await self.markets.markets()}:
            raise not_found("market")
        start = starts or now
        if start.utcoffset() is None or start < now:
            raise invalid("starts_at", "retroactive")
        if ends is not None and (ends.utcoffset() is None or ends <= start):
            raise invalid("ends_at")
        async with self.uow() as work:
            await work.halts.lock_scope(scope)
            existing = next(
                (
                    h
                    for h in await work.halts.all()
                    if h.scope == scope
                    and h.released_at is None
                    and halts.overlaps(start, ends, h.starts_at, h.ends_at)
                ),
                None,
            )
            if existing:
                raise conflict(
                    ErrorCode.TRADING_HALT_OVERLAP,
                    halt_id=str(existing.id),
                    scope=scope,
                    ends_at=existing.ends_at.isoformat() if existing.ends_at else None,
                )
            value = TradingHalt(
                uuid4(), None if scope == "global" else scope, reason, start, ends, actor, now
            )
            await work.halts.insert(value)
            await work.audit.append(
                audit.build(
                    "trading_halt_activated",
                    actor,
                    "trading_halt",
                    str(value.id),
                    {"scope": scope, "starts_at": start, "ends_at": ends, "reason": reason},
                    now,
                    meta,
                )
            )
        return halt_out(value, now)

    async def release(
        self, ident: UUID, reason: str, actor: UUID, code: str | None, meta: RequestMeta
    ) -> Raw:
        await self.step_up.verify(actor, code)
        now = self.clock.now()
        async with self.uow() as work:
            value = await work.halts.get_for_update(ident)
            if value is None:
                raise not_found("trading_halt")
            status = halts.effective_status(value, now)
            if status not in {"active", "scheduled"}:
                raise conflict(ErrorCode.TRADING_HALT_NOT_RELEASABLE, status=status)
            if not await work.halts.release(ident, now, actor, reason):
                raise conflict(ErrorCode.TRADING_HALT_NOT_RELEASABLE, status="released")
            updated = replace(value, released_at=now, released_by=actor, release_reason=reason)
            await work.audit.append(
                audit.build(
                    "trading_halt_released",
                    actor,
                    "trading_halt",
                    str(ident),
                    {
                        "scope": value.scope,
                        "reason": reason,
                        "before": asdict(value),
                        "after": asdict(updated),
                    },
                    now,
                    meta,
                )
            )
        return halt_out(updated, now)

    async def page(
        self, scope: str | None, status: str | None, cursor: str | None, size: int
    ) -> Raw:
        if status and status not in {"active", "scheduled", "released", "expired"}:
            raise invalid("status")
        now = self.clock.now()
        async with self.uow() as work:
            rows = [
                h
                for h in await work.halts.all()
                if (scope is None or h.scope == scope)
                and (status is None or halts.effective_status(h, now) == status)
            ]
        page = paginate(rows, lambda h: (h.starts_at.isoformat(), str(h.id)), cursor, size)
        return {"items": [halt_out(h, now) for h in page.items], "next_cursor": page.next_cursor}

    async def active_public(self) -> list[Raw]:
        async with self.uow() as work:
            return [
                {"scope": h.scope, "starts_at": h.starts_at, "ends_at": h.ends_at}
                for h in await work.halts.all()
                if halts.effective_status(h, self.clock.now()) == "active"
            ]
