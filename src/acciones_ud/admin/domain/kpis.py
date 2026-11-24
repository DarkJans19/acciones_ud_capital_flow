from collections import Counter, defaultdict
from decimal import Decimal, localcontext

from acciones_ud.admin.domain.commissions import money, terms_from
from acciones_ud.admin.domain.model import LedgerExecution, Raw
from acciones_ud.shared.domain.trading import CommissionTerms

KPI_DEFINITIONS_VERSION = "kpi-v1"


def _metric(name: str, value: object, unit: str, **extra: object) -> Raw:
    return {"value": value, "unit": unit, "definition": f"kpi-v1.{name}", **extra}


def _rounded_groups(groups: dict[str, Decimal], total: Decimal) -> dict[str, Decimal]:
    values = {key: money(value) for key, value in groups.items()}
    difference = total - sum(values.values(), Decimal(0))
    if difference:
        # Largest fractional remainder; deterministic penny allocation, never changes total.
        candidates = sorted(
            groups, key=lambda k: (groups[k] - values[k], k), reverse=difference > 0
        )
        step = Decimal("0.01") if difference > 0 else Decimal("-0.01")
        for index in range(int(abs(difference) * 100)):
            values[candidates[index % len(candidates)]] += step
    return values


def compute(inputs: Raw, executions: list[LedgerExecution]) -> Raw:
    levels: Counter[str] = Counter()
    interests: Counter[str] = Counter()
    investor_levels: Counter[str] = Counter()
    linked: Counter[str] = Counter()
    for row in inputs["registrations"]:
        levels[row["investor_level"] or "unspecified"] += 1
        interests.update(set(row["interests"]))
    for row in inputs["investors"]:
        investor_levels[row["investor_level"] or "unspecified"] += 1
        linked["with_broker" if row["with_broker"] else "without_broker"] += 1
    by_market: dict[str, Decimal] = defaultdict(Decimal)
    by_side: dict[str, Decimal] = defaultdict(Decimal)
    commissions: dict[str, Decimal] = defaultdict(Decimal)
    counts_market: Counter[str] = Counter()
    counts_side: Counter[str] = Counter()
    unknown = 0
    with localcontext() as ctx:
        ctx.prec = 60
        for e in executions:
            amount = e.qty * e.price
            by_market[e.exchange] += amount
            by_side[e.side] += amount
            counts_market[e.exchange] += 1
            counts_side[e.side] += 1
            terms = terms_from(e.commission_rate_pct, e.platform_share_pct, e.fee_version_id)
            if terms:
                commissions[e.exchange] += compute_commission(e, terms)
            else:
                unknown += 1
        volume = money(sum(by_market.values(), Decimal(0)))
        commission = sum(commissions.values(), Decimal(0))
        revenue = sum(
            (p["amount"] for p in inputs["payments"] if p["currency"].upper() == "USD"), Decimal(0)
        )
    return {
        "registered_users": _metric("registered_users", inputs["registered_users"], "users"),
        "new_registrations": _metric(
            "new_registrations",
            sum(levels.values()),
            "users",
            by_level=dict(levels),
            by_interest=dict(interests),
        ),
        "active_users": _metric("active_users", inputs["active_users"], "users"),
        "traded_volume_usd": _metric(
            "traded_volume_usd",
            volume,
            "USD",
            by_market=_rounded_groups(by_market, volume),
            by_side=_rounded_groups(by_side, volume),
        ),
        "executions_count": _metric(
            "executions_count",
            len(executions),
            "executions",
            by_market=dict(counts_market),
            by_side=dict(counts_side),
        ),
        "platform_commissions_usd": _metric(
            "platform_commissions_usd",
            commission,
            "USD",
            by_market=dict(commissions),
            historical_terms_unknown_count=unknown,
            complete=unknown == 0,
        ),
        "active_subscriptions": _metric(
            "active_subscriptions", inputs["active_subscriptions"], "subscriptions"
        ),
        "revenue_by_source": _metric(
            "revenue_by_source",
            commission + revenue,
            "USD",
            commissions=commission,
            subscriptions=revenue,
            excluded_non_usd_payments=sum(
                p["currency"].upper() != "USD" for p in inputs["payments"]
            ),
            complete=unknown == 0,
        ),
        "users_by_type": _metric(
            "users_by_type",
            sum(investor_levels.values()),
            "users",
            by_level=dict(investor_levels),
            by_broker=dict(linked),
        ),
    }


# Keep the indicator compute function separate from the commission calculator.


def compute_commission(e: LedgerExecution, terms: CommissionTerms) -> Decimal:
    from acciones_ud.admin.domain.commissions import compute as commission

    return commission(
        terms, e.side, e.qty, e.price, e.signed_by_broker_id is not None
    ).platform_share
