import json
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from uuid import UUID, uuid4

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.admin.domain import atypical, audit, commissions, fees, halts, kpis, reports
from acciones_ud.admin.domain.model import FeeVersion, LedgerExecution, TradingHalt
from acciones_ud.admin.domain.pagination import decode, paginate
from acciones_ud.admin.domain.periods import Period
from acciones_ud.shared.domain.audit_entry import RequestMeta
from acciones_ud.shared.domain.errors import AppError
from acciones_ud.shared.domain.trading import CommissionTerms

NOW = datetime(2026, 11, 20, tzinfo=UTC)
ACTOR = UUID(int=10)


def version(n, offset, market=None, rate=Decimal("2")):
    return FeeVersion(
        UUID(int=n),
        market,
        n,
        rate,
        Decimal("60"),
        NOW + timedelta(seconds=offset),
        "reason",
        ACTOR,
        NOW - timedelta(days=365),
    )


def execution(n, amount, offset=0, user=ACTOR):
    return LedgerExecution(
        str(n),
        UUID(int=n + 100),
        user,
        "AAPL",
        "NASDAQ",
        "buy",
        Decimal(1),
        Decimal(amount),
        NOW + timedelta(seconds=offset),
        None,
        fees.SEED_ID,
        Decimal("2"),
        Decimal("60"),
    )


# Feature: admin-mod-07, Property 1: Resolución total y no retroactiva de Commission_Terms
@settings(max_examples=100)
@given(st.lists(st.integers(-1000, 1000), unique=True), st.integers(-1000, 1000), st.booleans())
def test_fee_resolution(offsets, instant, market_specific):
    seed = version(1, -2000)
    scope = "NASDAQ" if market_specific else None
    versions = [seed, *[version(n + 2, offset, scope) for n, offset in enumerate(offsets)]]
    at = NOW + timedelta(seconds=instant)
    matching = [v for v in versions if v.scope == "NASDAQ" and v.effective_from <= at]
    fallback = [v for v in versions if v.scope == "default" and v.effective_from <= at]
    expected = max(matching or fallback, key=lambda v: v.effective_from)
    assert fees.resolve_terms(reversed(versions), "NASDAQ", at) == expected.terms
    assert (
        fees.resolve_terms([*versions, version(99999, 2001, "NASDAQ")], "NASDAQ", at)
        == expected.terms
    )


# Feature: admin-mod-07, Property 2: Validación de una Fee_Version nueva
@settings(max_examples=100)
@given(
    st.integers(-1000, 110000), st.integers(-100, 10100), st.integers(-10, 10), st.integers(0, 6)
)
def test_fee_validation(rate_int, share_int, seconds, scale):
    rate = Decimal(rate_int).scaleb(-scale)
    share = Decimal(share_int).scaleb(-2)
    valid = 0 <= rate <= 10 and 0 <= share <= 100 and scale <= 4 and seconds >= 0
    try:
        fees.validate_new_version(rate, share, NOW + timedelta(seconds=seconds), NOW)
    except AppError:
        assert not valid
    else:
        assert valid


def fraction_cents(value):
    value *= 100
    lower = value.numerator // value.denominator
    remainder = value - lower
    return (
        Decimal(
            lower + (remainder > Fraction(1, 2) or (remainder == Fraction(1, 2) and lower % 2 == 1))
        )
        / 100
    )


# Feature: admin-mod-07, Property 4: Cálculo y reparto de la comisión
@settings(max_examples=100)
@given(
    st.integers(1, 10**9),
    st.integers(1, 10**9),
    st.integers(0, 100000),
    st.integers(0, 10000),
    st.booleans(),
    st.sampled_from(["buy", "sell"]),
)
def test_commission_fraction_reference(qty, price, rate, share, signed, side):
    terms = CommissionTerms(fees.SEED_ID, Decimal(rate) / 10000, Decimal(share) / 100)
    result = commissions.compute(terms, side, Decimal(qty) / 1000, Decimal(price) / 10000, signed)
    gross = Fraction(qty, 1000) * Fraction(price, 10000)
    expected = fraction_cents(gross * Fraction(rate, 10**6))
    platform = fraction_cents(Fraction(expected) * Fraction(share, 10000)) if signed else expected
    assert result.commission == expected
    assert result.platform_share == platform
    assert result.platform_share + result.broker_share == expected
    assert 0 <= result.broker_share <= expected
    assert (result.total if side == "buy" else result.net) == fraction_cents(
        gross + Fraction(expected) * (1 if side == "buy" else -1)
    )


# Feature: admin-mod-07, Property 5: Reproducibilidad de la comisión de una Execution
@settings(max_examples=100)
@given(st.lists(st.integers(1, 1000000), min_size=1, max_size=25), st.integers(0, 100000))
def test_commission_reproducibility(amounts, changed_rate):
    from acciones_ud.admin.adapters.outbound.portfolio.official_commission import OfficialCommission
    from acciones_ud.admin.application.commission_service import execution_out
    from acciones_ud.portfolio.domain.model import ExecutionRecord

    # Multiple partial executions of the same order retain the same accepted terms.
    executions = [
        replace(execution(i, Decimal(a) / 100), order_id=UUID(int=100))
        for i, a in enumerate(amounts)
    ]
    official = OfficialCommission(Decimal(changed_rate) / 1000000)
    total = Decimal(0)
    for e in executions:
        record = ExecutionRecord(**asdict(e))
        result = execution_out(e)
        assert official.commission(record).amount == result["commission"]
        assert official.commission(record).source == "official"
        total += result["platform_share"]
    inputs = dict(
        registered_users=0,
        active_users=0,
        registrations=[],
        investors=[],
        payments=[],
        active_subscriptions=0,
    )
    assert kpis.compute(inputs, executions)["platform_commissions_usd"]["value"] == total
    old = replace(
        executions[0], fee_version_id=None, commission_rate_pct=None, platform_share_pct=None
    )
    assert execution_out(old)["commission"] is None
    assert official.commission(ExecutionRecord(**asdict(old))).source == "reference"


# Feature: admin-mod-07, Property 6: Estados, solapamientos y prioridad de Trading_Halt
@settings(max_examples=100)
@given(st.integers(-100, 100), st.integers(1, 100), st.integers(-100, 200), st.booleans())
def test_halt_intervals(start, duration, instant, released):
    a = NOW + timedelta(seconds=start)
    b = a + timedelta(seconds=duration)
    at = NOW + timedelta(seconds=instant)
    value = TradingHalt(
        uuid4(),
        None,
        "reason",
        a,
        b,
        ACTOR,
        NOW,
        NOW if released else None,
        ACTOR if released else None,
        "release" if released else None,
    )
    expected = (
        "released"
        if released and at >= NOW
        else "scheduled"
        if at < a
        else "expired"
        if at >= b
        else "active"
    )
    assert halts.effective_status(value, at) == expected
    assert not halts.overlaps(a, b, b, b + timedelta(seconds=1))
    decision = halts.gate([value], None, "NASDAQ", at)
    assert decision.allowed == (expected != "active")
    if not decision.allowed:
        assert decision.details["scope"] == "global"


# Feature: admin-mod-07, Property 9: Lista blanca y ausencia de secretos en Audit_Entries
@settings(max_examples=100)
@given(st.sampled_from(list(audit.SENSITIVE_KEYS)), st.integers(0, 5), st.booleans())
def test_audit_whitelist(secret, depth, upper):
    key = secret.upper() if upper else secret
    value = {key: "private", "allowed": 123}
    for _ in range(depth):
        value = {"nested": [value]}
    cleaned = audit.sanitize(value)
    assert "private" not in json.dumps(cleaned)
    assert "123" in json.dumps(cleaned)
    for action, keys in audit.PAYLOAD_KEYS.items():
        valid = {k: None for k in keys}
        audit.build(action, ACTOR, "user", str(ACTOR), valid, NOW, RequestMeta())
        with pytest.raises(ValueError):
            audit.build(
                action, ACTOR, "user", str(ACTOR), {**valid, "extra": "x"}, NOW, RequestMeta()
            )


# Feature: admin-mod-07, Property 11: Selección y paginación del rastro de auditoría
@settings(max_examples=100)
@given(
    st.lists(
        st.tuples(st.integers(0, 1000), st.sampled_from(["admin", "orders", "brokers", "auth"])),
        max_size=80,
    ),
    st.integers(1, 100),
)
def test_audit_pagination(rows, size):
    values = [
        {
            "occurred_at": (NOW + timedelta(seconds=t)).isoformat(),
            "source": source,
            "event_id": str(i),
        }
        for i, (t, source) in enumerate(rows)
    ]

    def key(r):
        return (r["occurred_at"], r["source"], r["event_id"])

    # Empty pages still validate the exact three-part cursor format in the SQL reader.
    cursor, selected = None, []
    while True:
        page = paginate(values, key, cursor, size)
        selected.extend(page.items)
        cursor = page.next_cursor
        if cursor is None:
            break
        assert len(decode(cursor, 3)) == 3
    assert selected == sorted(values, key=key, reverse=True)


# Feature: admin-mod-07, Property 14: Reglas deterministas de operaciones atípicas
@settings(max_examples=100)
@given(
    st.lists(
        st.tuples(st.integers(0, 3), st.integers(1, 50000), st.integers(0, 20000000)), max_size=60
    )
)
def test_atypical_reference(rows):
    cfg = atypical.AtypicalConfig()
    executions = [
        execution(i, amount, offset, UUID(int=user + 1))
        for i, (user, amount, offset) in enumerate(rows)
    ]
    flags = {f.event_id: f for f in atypical.flag(executions, cfg)}
    assert flags == {f.event_id: f for f in atypical.flag(list(reversed(executions)), cfg)}
    for e in executions:
        history = [
            other
            for other in executions
            if other.user_id == e.user_id
            and e.executed_at - timedelta(days=90) <= other.executed_at < e.executed_at
        ]
        mean = (
            sum((o.qty * o.price for o in history), Decimal(0)) / len(history) if history else None
        )
        reasons = []
        if e.qty * e.price >= cfg.absolute_usd:
            reasons.append("absolute_threshold")
        if len(history) >= cfg.min_history and e.qty * e.price > mean * cfg.multiplier:
            reasons.append("relative_to_history")
        assert (e.execution_id in flags) == bool(reasons)
        if reasons:
            assert flags[e.execution_id].reasons == tuple(reasons)
            assert flags[e.execution_id].observed["baseline_count"] == len(history)


# Feature: admin-mod-07, Property 15: Resumen canónico del Compliance_Report
@settings(max_examples=100)
@given(st.integers(-(10**15), 10**15), st.integers(0, 8), st.integers(-12, 12))
def test_digest_normalization(number, scale, offset):
    from datetime import timezone

    value = Decimal(number).scaleb(-scale)
    content = {"number": value, "at": NOW, "nested": {"id": ACTOR}}
    equivalent = {
        "nested": {"id": ACTOR},
        "at": NOW.astimezone(timezone(timedelta(hours=offset))),
        "number": value.quantize(Decimal(1).scaleb(-scale - 2)),
    }
    assert reports.digest(content) == reports.digest(equivalent)
    assert reports.digest(content) == reports.digest(json.loads(reports.canonical_json(content)))
    assert reports.digest(content) != reports.digest({**content, "number": value + 1})


# Feature: admin-mod-07, Property 16: Fórmulas y consistencia de los indicadores
@settings(max_examples=100)
@given(st.lists(st.integers(1, 10**8), max_size=60), st.integers(0, 20))
def test_kpi_reference(amounts, subscribers):
    rows = [
        replace(
            execution(i, Decimal(a) / 1000),
            exchange="NYSE" if i % 2 else "NASDAQ",
            side="buy" if i % 3 else "sell",
        )
        for i, a in enumerate(amounts)
    ]
    registrations = [
        {"investor_level": "beginner" if i % 2 else None, "interests": ["tech", "finance"]}
        for i in range(subscribers)
    ]
    investors = [
        {"investor_level": "experienced", "with_broker": bool(i % 2)} for i in range(subscribers)
    ]
    inputs = dict(
        registered_users=subscribers,
        active_users=subscribers // 2,
        active_subscriptions=subscribers,
        registrations=registrations,
        payments=[
            {"amount": Decimal(5), "currency": "USD"},
            {"amount": Decimal(1000), "currency": "COP"},
        ],
        investors=investors,
    )
    result = kpis.compute(inputs, rows)
    assert result["traded_volume_usd"]["value"] == commissions.money(
        sum((e.qty * e.price for e in rows), Decimal(0))
    )
    assert result["registered_users"]["value"] == subscribers
    assert result["new_registrations"]["value"] == subscribers
    assert result["users_by_type"]["value"] == subscribers
    assert result["active_subscriptions"]["value"] == subscribers
    assert result["revenue_by_source"]["subscriptions"] == Decimal(5)
    for name, dimensions in (
        ("traded_volume_usd", ("by_market", "by_side")),
        ("executions_count", ("by_market", "by_side")),
        ("platform_commissions_usd", ("by_market",)),
        ("new_registrations", ("by_level",)),
        ("users_by_type", ("by_level", "by_broker")),
    ):
        for dimension in dimensions:
            assert sum(result[name][dimension].values()) == result[name]["value"]


def test_known_commission_example_and_non_finite_values():
    result = commissions.compute(fees.SEED_TERMS, "buy", Decimal(10), Decimal("187.35"), True)
    assert (result.commission, result.platform_share, result.broker_share) == (
        Decimal("37.47"),
        Decimal("22.48"),
        Decimal("14.99"),
    )
    for rate in (Decimal("NaN"), Decimal("Infinity")):
        with pytest.raises(AppError):
            fees.validate_new_version(rate, Decimal(60), NOW, NOW)


def test_period_dst_and_invalid_cursor():
    period = Period(datetime(2026, 3, 8).date(), datetime(2026, 3, 8).date())
    start, end = period.bounds()
    assert (end - start).total_seconds() == 23 * 3600
    with pytest.raises(AppError):
        decode("malformed", 2)
    from acciones_ud.admin.domain.pagination import encode

    with pytest.raises(AppError):
        decode(encode(("not-a-timestamp", "id")), 2)
    for start, end in (
        (datetime(2026, 11, 20).date(), datetime(2026, 11, 19).date()),
        (datetime(2025, 1, 1).date(), datetime(2026, 1, 2).date()),
    ):
        with pytest.raises(AppError):
            Period(start, end)
