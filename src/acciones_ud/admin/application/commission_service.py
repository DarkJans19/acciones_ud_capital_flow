from dataclasses import asdict
from decimal import Decimal
from uuid import UUID

from acciones_ud.admin.domain.commissions import compute, terms_from
from acciones_ud.admin.domain.errors import invalid
from acciones_ud.admin.domain.fees import resolve_terms
from acciones_ud.admin.domain.model import LedgerExecution, Raw
from acciones_ud.admin.domain.pagination import paginate
from acciones_ud.admin.domain.periods import Period
from acciones_ud.admin.domain.ports import (
    AdminWorkFactory,
    BrokerLinkPort,
    MarketCatalogPort,
    PlatformLedgerPort,
    UserReaderPort,
)
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import AppError, ErrorCode


def execution_out(e: LedgerExecution) -> Raw:
    terms = terms_from(e.commission_rate_pct, e.platform_share_pct, e.fee_version_id)
    result = asdict(e)
    result["gross_amount"] = e.qty * e.price
    result["commission_status"] = "official" if terms else "historical_terms_unknown"
    result.update(
        {
            "commission": None,
            "platform_share": None,
            "broker_share": None,
            "total": None,
            "net": None,
        }
    )
    if terms:
        result.update(
            asdict(compute(terms, e.side, e.qty, e.price, e.signed_by_broker_id is not None))
        )
    return result


class CommissionQuoteService:
    def __init__(self, uow: AdminWorkFactory, markets: MarketCatalogPort, clock: Clock) -> None:
        self.uow, self.markets, self.clock = uow, markets, clock

    async def quote(
        self, symbol: str, side: str, qty: Decimal, price: Decimal, with_broker: bool
    ) -> Raw:
        market = await self.markets.exchange_of(symbol.strip().upper())
        if market is None:
            raise AppError(404, ErrorCode.SYMBOL_NOT_FOUND, "Unknown symbol.")
        now = self.clock.now()
        async with self.uow() as work:
            terms = resolve_terms(await work.fees.all_versions(), market, now)
        return {
            **asdict(compute(terms, side, qty, price, with_broker)),
            **asdict(terms),
            "symbol": symbol.strip().upper(),
            "market": market,
            "binding": False,
            "quoted_at": now,
        }


class CommissionQueryService:
    def __init__(
        self, ledger: PlatformLedgerPort, links: BrokerLinkPort, users: UserReaderPort
    ) -> None:
        self.ledger, self.links, self.users = ledger, links, users

    async def query(
        self,
        period: Period,
        cursor: str | None,
        size: int,
        *,
        investor: UUID | None = None,
        broker: UUID | None = None,
        market: str | None = None,
        symbol: str | None = None,
        broker_view: bool = False,
    ) -> Raw:
        if not 1 <= size <= 100:
            raise invalid("page_size")
        linked: set[UUID] | None = None
        if broker_view:
            assert broker is not None
            linked = set(await self.links.linked_investors(broker))
            if investor is not None and investor not in linked:
                raise AppError(404, ErrorCode.CLIENT_NOT_FOUND, "Client not found.")
        start, end = period.bounds()
        values = [
            e
            async for e in self.ledger.iterate(
                start,
                end,
                {
                    "user_id": investor,
                    "broker_id": broker,
                    "market": market,
                    "symbol": symbol.strip().upper() if symbol else None,
                    "investor_ids": tuple(linked) if linked is not None else None,
                },
            )
            if (investor is None or e.user_id == investor)
            and (broker is None or e.signed_by_broker_id == broker)
            and (market is None or e.exchange == market)
            and (symbol is None or e.symbol == symbol.strip().upper())
            and (linked is None or e.user_id in linked)
        ]
        page = paginate(values, lambda e: (e.executed_at.isoformat(), e.execution_id), cursor, size)
        items = [execution_out(e) for e in page.items]
        names = await self.users.display_names([e.user_id for e in page.items])
        for item in items:
            item["investor_name"] = names.get(item["user_id"], "")
        totals: Raw = {
            "gross_amount": Decimal(0),
            "commission": Decimal(0),
            "platform_share": Decimal(0),
            "broker_share": Decimal(0),
            "historical_terms_unknown_count": 0,
        }
        by_market: Raw = {}
        by_broker: Raw = {}
        for e in values:
            row = execution_out(e)
            totals["gross_amount"] += row["gross_amount"]
            if row["commission"] is None:
                totals["historical_terms_unknown_count"] += 1
                continue
            for key in ("commission", "platform_share", "broker_share"):
                totals[key] += row[key]
            for groups, key in (
                (by_market, e.exchange),
                (by_broker, str(e.signed_by_broker_id) if e.signed_by_broker_id else "unassigned"),
            ):
                group = groups.setdefault(
                    key, {k: Decimal(0) for k in ("commission", "platform_share", "broker_share")}
                )
                for name in group:
                    group[name] += row[name]
        totals["complete"] = totals["historical_terms_unknown_count"] == 0
        return {
            "items": items,
            "next_cursor": page.next_cursor,
            "totals": totals,
            "by_market": by_market,
            "by_broker": by_broker,
        }
