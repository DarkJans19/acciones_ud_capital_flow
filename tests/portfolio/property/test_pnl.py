from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from uuid import UUID

from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.portfolio.domain.model import ExecutionRecord
from acciones_ud.portfolio.domain.pnl import average_cost, replay

D = Decimal
amount = st.decimals(
    min_value="0.000000001", max_value="1000000000", places=9, allow_nan=False, allow_infinity=False
)
price = st.decimals(
    min_value="0.0001", max_value="1000000000", places=4, allow_nan=False, allow_infinity=False
)
trades = st.lists(
    st.tuples(st.sampled_from(["buy", "sell"]), amount, price), min_size=1, max_size=25
)


def records(rows):
    return [
        ExecutionRecord(
            str(i).zfill(3),
            UUID(int=1),
            UUID(int=2),
            "A",
            "NYSE",
            side,
            qty,
            p,
            datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=i),
        )
        for i, (side, qty, p) in enumerate(rows)
    ]


# Feature: portfolio-mod-05, Property 2: Pnl_Calculator contra el modelo de referencia
@settings(max_examples=100)
@given(trades)
def test_reference(rows):
    with localcontext() as ctx:
        ctx.prec = 200
        quantity = cost = gross = net = D(0)
        mismatch = False
        for side, q, p in rows:
            if side == "buy":
                cost += q * p
                quantity += q
            else:
                sold = min(q, quantity)
                with localcontext() as division:
                    division.prec = 40
                    removed = cost if sold == quantity else cost * sold / quantity
                result = sold * p - removed
                gross += result
                net += result - q * p * D("0.02") if sold else D(0)
                mismatch |= q > quantity
                quantity -= sold
                cost -= removed
        actual = replay(records(rows), lambda e: e.qty * e.price * D("0.02"))["A"]
        assert (
            actual.qty,
            actual.total_cost,
            actual.realized_gross,
            actual.realized_net,
            actual.mismatch,
        ) == (quantity, cost, gross, net, mismatch)
        with localcontext() as division:
            division.prec = 40
            assert average_cost(actual) == (cost / quantity if quantity else None)


# Feature: portfolio-mod-05, Property 3: Conservación del resultado
@settings(max_examples=100)
@given(trades, price)
def test_conservation(rows, valuation_price):
    with localcontext() as ctx:
        ctx.prec = 200
        check_conservation(rows, valuation_price)


def check_conservation(rows, valuation_price):
    valid = []
    quantity = D(0)
    for side, q, p in rows:
        q = q if side == "buy" else min(q, quantity)
        if q:
            valid.append((side, q, p))
            quantity += q if side == "buy" else -q
    if not valid:
        return
    ledger = replay(records(valid))["A"]
    # Exact Decimal equality, with enough precision to evaluate the invariant itself.
    left = ledger.realized_gross + (valuation_price * ledger.qty - ledger.total_cost)
    right = valuation_price * ledger.qty + sum(
        (q * p * (-1 if side == "buy" else 1) for side, q, p in valid), D(0)
    )
    assert left == right


# Feature: portfolio-mod-05, Property 4: Confluencia y determinismo del replay
@settings(max_examples=100)
@given(trades, st.data())
def test_confluence(rows, data):
    items = [
        replace(e, symbol="A" if i % 2 else "B", executed_at=datetime(2026, 1, 1, tzinfo=UTC))
        for i, e in enumerate(records(rows))
    ]
    shuffled = data.draw(st.permutations(items))
    assert replay(items) == replay(shuffled) == replay(items)
