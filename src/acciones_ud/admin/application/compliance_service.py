from collections import Counter
from dataclasses import asdict
from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from acciones_ud.admin.application.commission_service import execution_out
from acciones_ud.admin.domain import atypical, audit, reports
from acciones_ud.admin.domain.atypical import AtypicalConfig
from acciones_ud.admin.domain.commissions import money
from acciones_ud.admin.domain.errors import invalid, not_found
from acciones_ud.admin.domain.model import ComplianceReport, Raw
from acciones_ud.admin.domain.pagination import paginate
from acciones_ud.admin.domain.periods import Period
from acciones_ud.admin.domain.ports import (
    AdminWorkFactory,
    AuditTrailReader,
    PlatformLedgerPort,
    UserReaderPort,
)
from acciones_ud.shared.domain.audit_entry import RequestMeta
from acciones_ud.shared.domain.clock import Clock


class ComplianceService:
    def __init__(
        self,
        uow: AdminWorkFactory,
        ledger: PlatformLedgerPort,
        trail: AuditTrailReader,
        users: UserReaderPort,
        clock: Clock,
        config: AtypicalConfig,
    ) -> None:
        self.uow, self.ledger, self.trail = uow, ledger, trail
        self.users, self.clock, self.config = users, clock, config

    async def flags(self, period: Period) -> list[Raw]:
        start, end = period.bounds()
        executions = [
            e
            async for e in self.ledger.iterate(start - timedelta(days=self.config.window_days), end)
        ]
        lookback = max(
            self.config.frequency_seconds,
            self.config.cancellation_seconds,
            self.config.rejection_seconds,
        )
        behavior = await self.trail.behavior(start - timedelta(seconds=lookback), end)
        flags = [
            *atypical.flag(executions, self.config),
            *atypical.behavior_flags(behavior, self.config),
        ]
        return [asdict(f) for f in flags if start <= f.at < end]

    async def atypical(
        self,
        period: Period,
        user: UUID | None,
        min_amount: Decimal | None,
        cursor: str | None,
        size: int,
    ) -> Raw:
        if min_amount is not None and (not min_amount.is_finite() or min_amount < 0):
            raise invalid("min_amount")
        values = [
            f
            for f in await self.flags(period)
            if (user is None or f["user_id"] == user)
            and (min_amount is None or f["observed"].get("gross_amount", Decimal(0)) >= min_amount)
        ]
        page = paginate(
            values,
            lambda f: (f["at"].isoformat(), f["event_id"] + ":" + ",".join(f["reasons"])),
            cursor,
            size,
        )
        return {
            "items": page.items,
            "next_cursor": page.next_cursor,
            "rules_version": atypical.RULES_VERSION,
            "configuration": asdict(self.config),
        }

    async def generate_report(
        self, user: UUID, period: Period, actor: UUID, meta: RequestMeta
    ) -> Raw:
        now = self.clock.now()
        summary = await self.users.summary(user, now)
        if summary is None:
            raise not_found("user")
        start, end = period.bounds()
        executions = [e async for e in self.ledger.iterate(start, end)]
        own = [e for e in executions if e.user_id == user]
        activity = await self.trail.counts(user, start, end)
        flags = [f for f in await self.flags(period) if f["user_id"] == user]
        counts = Counter(e.user_id for e in executions)
        population = len(counts)
        volume = sum((e.qty * e.price for e in executions), Decimal(0))
        own_volume = sum((e.qty * e.price for e in own), Decimal(0))
        average_count = Decimal(len(executions)) / population if population else Decimal(0)
        average_volume = volume / population if population else Decimal(0)
        rows = [execution_out(e) for e in own]
        async with self.uow() as work:
            restrictions = [
                asdict(r)
                for r in await work.restrictions.all(user)
                if r.restricted_at < end and (r.lifted_at is None or r.lifted_at >= start)
            ]
        content: Raw = {
            "user": summary,
            "period": {"from": period.from_, "to": period.to},
            "activity": activity,
            "executions_count": len(own),
            "volume_usd": money(own_volume),
            "commission_usd": sum(
                (r["commission"] for r in rows if r["commission"] is not None), Decimal(0)
            ),
            "historical_terms_unknown_count": sum(r["commission"] is None for r in rows),
            "average": {"execution_count": average_count, "volume_usd": average_volume},
            "ratios": {
                "execution_count": money(Decimal(len(own)) / average_count)
                if average_count
                else None,
                "volume": money(own_volume / average_volume) if average_volume else None,
            },
            "atypical_operations": flags,
            "restrictions": restrictions,
            "rules_version": atypical.RULES_VERSION,
            "configuration": asdict(self.config),
        }
        canonical = reports.canonical_value(audit.sanitize(content))
        report = ComplianceReport(
            uuid4(),
            user,
            period.from_,
            period.to,
            atypical.RULES_VERSION,
            canonical,
            reports.digest(canonical),
            actor,
            now,
        )
        async with self.uow() as work:
            await work.reports.insert(report)
            await work.audit.append(
                audit.build(
                    "compliance_report_generated",
                    actor,
                    "user",
                    str(user),
                    {
                        "report_id": report.id,
                        "period_from": period.from_,
                        "period_to": period.to,
                        "rules_version": report.rules_version,
                        "content_sha256": report.content_sha256,
                    },
                    now,
                    meta,
                )
            )
        return asdict(report)

    async def get_report(self, ident: UUID) -> Raw:
        async with self.uow() as work:
            report = await work.reports.get(ident)
        if report is None:
            raise not_found("compliance_report")
        return asdict(report)

    async def reports_for_user(self, user: UUID, cursor: str | None, size: int) -> Raw:
        if await self.users.summary(user, self.clock.now()) is None:
            raise not_found("user")
        async with self.uow() as work:
            values = await work.reports.for_user(user)
        page = paginate(values, lambda r: (r.generated_at.isoformat(), str(r.id)), cursor, size)
        return {"items": [asdict(r) for r in page.items], "next_cursor": page.next_cursor}
