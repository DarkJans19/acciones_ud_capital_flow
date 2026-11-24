from acciones_ud.admin.application.halt_service import halt_out
from acciones_ud.admin.domain.errors import not_found
from acciones_ud.admin.domain.fees import resolve_terms
from acciones_ud.admin.domain.model import Raw
from acciones_ud.admin.domain.ports import AdminWorkFactory, MarketCatalogPort
from acciones_ud.shared.domain.clock import Clock


class MarketAdminView:
    def __init__(self, uow: AdminWorkFactory, markets: MarketCatalogPort, clock: Clock) -> None:
        self.uow, self.markets, self.clock = uow, markets, clock

    async def list(self, code: str | None = None) -> list[Raw]:
        markets = await self.markets.markets()
        if code is not None:
            markets = [m for m in markets if m["code"] == code]
            if not markets:
                raise not_found("market")
        now = self.clock.now()
        async with self.uow() as work:
            versions = await work.fees.all_versions()
            halts = await work.halts.all()
        for market in markets:
            terms = resolve_terms(versions, market["code"], now)
            market["commission_terms"] = terms
            market["fee_origin"] = (
                "market"
                if any(
                    v.id == terms.fee_version_id and v.market_code == market["code"]
                    for v in versions
                )
                else "default"
            )
            market["trading_halts"] = [
                out
                for h in halts
                if h.scope in {"global", market["code"]}
                and (out := halt_out(h, now))["status"] in {"active", "scheduled"}
            ]
        return markets
