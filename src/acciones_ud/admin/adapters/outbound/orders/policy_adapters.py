from datetime import datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa

from acciones_ud.admin.adapters.outbound.persistence import tables as t
from acciones_ud.admin.domain.fees import resolve_terms
from acciones_ud.admin.domain.halts import gate
from acciones_ud.admin.domain.model import AccountRestriction, FeeVersion, TradingHalt
from acciones_ud.admin.domain.ports import MarketCatalogPort
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from acciones_ud.shared.domain.trading import CommissionTerms, GateDecision


class CommissionTermsAdapter:
    async def terms(self, exchange: str, at: datetime) -> CommissionTerms:
        from acciones_ud.shared.infrastructure.db import unit_of_work

        async with unit_of_work() as session:
            result = await session.execute(
                sa.select(t.fees).where(
                    sa.or_(t.fees.c.market_code == exchange, t.fees.c.market_code.is_(None)),
                    t.fees.c.effective_from <= at,
                    t.fees.c.canceled_at.is_(None),
                )
            )
            return resolve_terms([FeeVersion(**r) for r in result.mappings()], exchange, at)


class TradingGateAdapter:
    async def check(self, user_id: UUID, exchange: str, at: datetime) -> GateDecision:
        from acciones_ud.shared.infrastructure.db import unit_of_work

        async with unit_of_work() as session:
            rows = await session.execute(
                sa.select(t.halts).where(
                    sa.or_(t.halts.c.market_code == exchange, t.halts.c.market_code.is_(None)),
                    t.halts.c.starts_at <= at,
                    t.halts.c.released_at.is_(None),
                    sa.or_(t.halts.c.ends_at.is_(None), t.halts.c.ends_at > at),
                )
            )
            halts = [TradingHalt(**r) for r in rows.mappings()]
            row = (
                (
                    await session.execute(
                        sa.select(t.restrictions).where(
                            t.restrictions.c.user_id == user_id,
                            t.restrictions.c.lifted_at.is_(None),
                        )
                    )
                )
                .mappings()
                .first()
            )
            restriction = AccountRestriction(**row) if row else None
            return gate(halts, restriction, exchange, at)


class ProposalTermsAdapter:
    def __init__(self, markets: MarketCatalogPort, terms: CommissionTermsAdapter) -> None:
        self.markets, self.terms = markets, terms

    async def rate_pct(self, symbol: str, at: datetime) -> Decimal:
        exchange = await self.markets.exchange_of(symbol)
        if exchange is None:
            raise AppError(404, ErrorCode.SYMBOL_NOT_FOUND, "Unknown symbol.")
        return (await self.terms.terms(exchange, at)).commission_rate_pct
