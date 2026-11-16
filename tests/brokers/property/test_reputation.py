from decimal import Decimal
from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.brokers.domain.reputation import average


# Feature: brokers-mod-06, Property 12: Promedio de reputacion
@settings(max_examples=100)
@given(st.lists(st.integers(min_value=1, max_value=5), max_size=500))
def test_average_matches_exact_rational_rounding(stars):
    actual = average(stars)
    if not stars:
        assert actual is None
        return
    expected = Decimal(round(Fraction(sum(stars) * 100, len(stars)))) / 100
    assert actual == expected
    assert Decimal(1) <= actual <= Decimal(5)
    assert actual == average(list(reversed(stars)))
