from dataclasses import fields
from decimal import Decimal
from uuid import UUID, uuid4

from acciones_ud.portfolio.application.report_builder import (
    ReportAmounts,
    ReportBuilder,
    amount_document,
)
from acciones_ud.portfolio.domain import model as m
from acciones_ud.portfolio.domain import rounding
from acciones_ud.portfolio.domain.decimal_math import add
from acciones_ud.portfolio.domain.errors import NotFoundError
from acciones_ud.portfolio.domain.pagination import decode, validate_size
from acciones_ud.portfolio.domain.period import parse
from acciones_ud.portfolio.domain.ports import BrokerClientPort, ReportWorkFactory
from acciones_ud.shared.domain.clock import Clock


class ReportService:
    def __init__(
        self,
        builder: ReportBuilder,
        uow: ReportWorkFactory,
        brokers: BrokerClientPort,
        clock: Clock,
    ) -> None:
        self.builder, self.uow, self.brokers, self.clock = builder, uow, brokers, clock

    async def create_on_demand(self, user_id: UUID, period: m.Period) -> m.Report:
        built = await self.builder.build(user_id, parse(period.from_, period.to))
        report = m.Report(
            uuid4(),
            user_id,
            "investor",
            "on_demand",
            period,
            built.positions_as_of,
            {**built.content, "report_type": "on_demand"},
            self.clock.now(),
        )
        async with self.uow() as work:
            await work.reports.add(report)
        return report

    async def create_broker(self, broker_id: UUID, period: m.Period) -> m.Report:
        parse(period.from_, period.to)
        clients = []
        amounts: list[ReportAmounts] = []
        attributed = Decimal(0)
        for investor in sorted(set(await self.brokers.linked_investors(broker_id))):
            built = await self.builder.build(investor, period)
            commission = add(
                *(
                    self.builder.commissions.commission(e).amount
                    for e in built.executions
                    if e.signed_by_broker_id == broker_id
                )
            )
            attributed = add(attributed, commission)
            clients.append(
                {
                    "investor_id": str(investor),
                    **built.content,
                    "commissions_attributed": str(rounding.money(commission)),
                }
            )
            amounts.append(built.amounts)
        total = ReportAmounts(
            **{
                field.name: add(*(getattr(a, field.name) for a in amounts))
                for field in fields(ReportAmounts)
            }
        )
        now = self.clock.now()
        report = m.Report(
            uuid4(),
            broker_id,
            "broker",
            "broker",
            period,
            now,
            {
                "report_type": "broker",
                "currency": "USD",
                "clients": clients,
                "totals": {
                    **amount_document(total),
                    "commissions_attributed": str(rounding.money(attributed)),
                    "client_count": len(clients),
                },
            },
            now,
        )
        async with self.uow() as work:
            await work.reports.add(report)
        return report

    async def list(
        self,
        owner_id: UUID,
        type: m.ReportType | None = None,
        cursor: str | None = None,
        size: int = 50,
        require_linked: bool = True,
    ) -> m.Page[m.Report]:
        validate_size(size)
        if cursor:
            decode(cursor)
        if require_linked:
            await self.builder.portfolio.linked(owner_id)
        async with self.uow() as work:
            return await work.reports.list_page(owner_id, type, cursor, size)

    async def get(self, owner_id: UUID, report_id: UUID, require_linked: bool = True) -> m.Report:
        async with self.uow() as work:
            report = await work.reports.get(owner_id, report_id)
        if report is None:
            raise NotFoundError()
        if require_linked:
            await self.builder.portfolio.linked(owner_id)
        return report

    async def get_client_report(
        self, broker_id: UUID, investor_id: UUID, report_id: UUID
    ) -> m.Report:
        if not await self.brokers.is_linked(broker_id, investor_id):
            raise NotFoundError()
        return await self.get(investor_id, report_id, require_linked=False)

    async def create_scheduled(
        self, user_id: UUID, type: m.ReportType, period: m.Period
    ) -> m.Report | None:
        async with self.uow() as work:
            existing = await work.reports.scheduled(user_id, type, period)
        if existing:
            return existing
        built = await self.builder.build(user_id, period)
        if type == "daily_summary" and not built.executions and not built.content["positions"]:
            return None
        report = m.Report(
            uuid4(),
            user_id,
            "investor",
            type,
            period,
            built.positions_as_of,
            {**built.content, "report_type": type},
            self.clock.now(),
        )
        async with self.uow() as work:
            if await work.reports.add(report):
                return report
            return await work.reports.scheduled(user_id, type, period)
