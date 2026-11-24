from dataclasses import asdict, replace
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from acciones_ud.admin.application.step_up import StepUp
from acciones_ud.admin.domain import audit, fees
from acciones_ud.admin.domain.errors import conflict, invalid, not_found
from acciones_ud.admin.domain.model import FeeVersion, Raw
from acciones_ud.admin.domain.pagination import paginate
from acciones_ud.admin.domain.ports import AdminWorkFactory, MarketCatalogPort
from acciones_ud.shared.domain.audit_entry import RequestMeta
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import ErrorCode


def fee_out(version: FeeVersion, versions: list[FeeVersion], now: datetime) -> Raw:
    return {
        **asdict(version),
        "scope": version.scope,
        "broker_share_pct": version.terms.broker_share_pct,
        "status": fees.version_status(version, versions, now),
    }


class FeeService:
    def __init__(
        self, uow: AdminWorkFactory, markets: MarketCatalogPort, step_up: StepUp, clock: Clock
    ) -> None:
        self.uow, self.markets, self.step_up, self.clock = uow, markets, step_up, clock

    async def check_scope(self, scope: str) -> None:
        if scope != "default" and scope not in {m["code"] for m in await self.markets.markets()}:
            raise not_found("fee_scope")

    async def create(
        self,
        scope: str,
        rate: Decimal,
        share: Decimal,
        effective_from: datetime | None,
        reason: str,
        expected: int,
        actor: UUID,
        code: str | None,
        meta: RequestMeta,
    ) -> Raw:
        now = self.clock.now()
        await self.step_up.verify(actor, code)
        await self.check_scope(scope)
        fees.validate_new_version(rate, share, effective_from or now, now)
        if not 1 <= len(reason.strip()) <= 500:
            raise invalid("reason")
        async with self.uow() as work:
            await work.fees.lock_scope(scope)
            versions = await work.fees.all_versions()
            previous = max(
                (v for v in versions if v.scope == scope), key=lambda v: v.version_no, default=None
            )
            latest = previous.version_no if previous else 0
            if expected != latest or any(
                v.scope == scope
                and v.canceled_at is None
                and v.effective_from == (effective_from or now)
                for v in versions
            ):
                raise conflict(ErrorCode.FEE_VERSION_CONFLICT, latest_version=latest)
            version = FeeVersion(
                uuid4(),
                None if scope == "default" else scope,
                latest + 1,
                rate,
                share,
                effective_from or now,
                reason,
                actor,
                now,
            )
            await work.fees.insert(version)
            await work.audit.append(
                audit.build(
                    "fee_version_created",
                    actor,
                    "fee_version",
                    str(version.id),
                    {
                        "scope": scope,
                        "version_no": version.version_no,
                        "before": asdict(previous) if previous else None,
                        "after": asdict(version),
                    },
                    now,
                    meta,
                )
            )
        return fee_out(version, [*versions, version], now)

    async def cancel(
        self, scope: str, ident: UUID, reason: str, actor: UUID, code: str | None, meta: RequestMeta
    ) -> Raw:
        await self.step_up.verify(actor, code)
        now = self.clock.now()
        async with self.uow() as work:
            value = await work.fees.get_for_update(ident)
            if value is None or value.scope != scope:
                raise not_found("fee_version")
            versions = await work.fees.all_versions()
            if not fees.can_cancel(value, now):
                raise conflict(
                    ErrorCode.FEE_VERSION_NOT_CANCELABLE,
                    status=fees.version_status(value, versions, now),
                )
            if not await work.fees.cancel(ident, now, actor, reason):
                raise conflict(ErrorCode.FEE_VERSION_NOT_CANCELABLE, status="canceled")
            updated = replace(value, canceled_at=now, canceled_by=actor, cancel_reason=reason)
            await work.audit.append(
                audit.build(
                    "fee_version_canceled",
                    actor,
                    "fee_version",
                    str(ident),
                    {
                        "scope": scope,
                        "version_no": value.version_no,
                        "reason": reason,
                        "before": asdict(value),
                        "after": asdict(updated),
                    },
                    now,
                    meta,
                )
            )
        return fee_out(updated, versions, now)

    async def matrix(self) -> Raw:
        markets = await self.markets.markets()
        async with self.uow() as work:
            versions = await work.fees.all_versions()
        now = self.clock.now()
        rows = fees.matrix(versions, [m["code"] for m in markets], now)
        for row in rows:
            current = next(v for v in versions if v.id == row["terms"].fee_version_id)
            row["current"] = fee_out(current, versions, now)
            row["scheduled"] = [fee_out(v, versions, now) for v in row["scheduled"]]
        return {"items": rows}

    async def history(self, scope: str, cursor: str | None, size: int) -> Raw:
        await self.check_scope(scope)
        async with self.uow() as work:
            versions = await work.fees.all_versions()
        page = paginate(
            [v for v in versions if v.scope == scope],
            lambda v: (f"{v.version_no:020d}", str(v.id)),
            cursor,
            size,
        )
        return {
            "items": [fee_out(v, versions, self.clock.now()) for v in page.items],
            "next_cursor": page.next_cursor,
        }
