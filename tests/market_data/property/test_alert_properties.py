# Feature: identity-market-backend, Property 24: Alert engine triggers once

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.market_data.domain.alerts import evaluate
from acciones_ud.market_data.domain.entities import AlertStatus, Comparator

THRESHOLD = Decimal("100")
PRICES = st.one_of(
    st.none(), st.decimals(min_value=Decimal("1"), max_value=Decimal("200"), places=2)
)
INITIAL = st.sampled_from(list(AlertStatus))


@given(
    comparator=st.sampled_from(list(Comparator)),
    initial=INITIAL,
    prices=st.lists(PRICES, max_size=20),
)
def test_alert_engine_triggers_at_most_once(
    comparator: Comparator, initial: AlertStatus, prices: list[Decimal | None]
) -> None:
    status = initial
    previous: Decimal | None = None
    triggers = 0
    for price in prices:
        before = (status, previous)
        status, previous, triggered = evaluate(status, comparator, THRESHOLD, previous, price)
        if price is None:
            assert (status, previous) == before
            assert triggered is False
            continue
        if before[0] is not AlertStatus.ACTIVE:
            assert (status, previous) == before
            assert triggered is False
            continue
        if triggered:
            triggers += 1
            assert status is AlertStatus.TRIGGERED
            if comparator is Comparator.CROSSES:
                assert price == THRESHOLD or before[1] is not None
        else:
            assert status is AlertStatus.ACTIVE
    assert triggers <= 1
    if initial is not AlertStatus.ACTIVE:
        assert triggers == 0


def test_above_and_below_boundaries_are_inclusive() -> None:
    status, _, triggered = evaluate(
        AlertStatus.ACTIVE, Comparator.ABOVE, THRESHOLD, None, THRESHOLD
    )
    assert triggered and status is AlertStatus.TRIGGERED
    status, _, triggered = evaluate(
        AlertStatus.ACTIVE, Comparator.BELOW, THRESHOLD, None, THRESHOLD
    )
    assert triggered and status is AlertStatus.TRIGGERED


def test_crosses_requires_opposite_sides_or_equality() -> None:
    assert evaluate(AlertStatus.ACTIVE, Comparator.CROSSES, THRESHOLD, Decimal("90"), THRESHOLD)[2]
    assert evaluate(
        AlertStatus.ACTIVE, Comparator.CROSSES, THRESHOLD, Decimal("90"), Decimal("110")
    )[2]
    assert evaluate(
        AlertStatus.ACTIVE, Comparator.CROSSES, THRESHOLD, Decimal("110"), Decimal("90")
    )[2]
    assert not evaluate(
        AlertStatus.ACTIVE, Comparator.CROSSES, THRESHOLD, Decimal("110"), Decimal("120")
    )[2]
    assert not evaluate(
        AlertStatus.ACTIVE, Comparator.CROSSES, THRESHOLD, None, Decimal("120")
    )[2]
