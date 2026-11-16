import json

from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import TypeAdapter

from acciones_ud.portfolio.adapters.inbound.http.schemas.common import DecimalStr
from acciones_ud.portfolio.domain.rounding import money, pct, price, qty


# Feature: portfolio-mod-05, Property 10: Round-trip de decimales serializados
@settings(max_examples=100)
@given(
    st.decimals(
        min_value="-1000000000",
        max_value="1000000000",
        places=9,
        allow_nan=False,
        allow_infinity=False,
    ),
    st.sampled_from([money, pct, price, qty]),
)
def test_decimal_round_trip(value, rounding):
    adapter = TypeAdapter(DecimalStr)
    original = rounding(value)
    raw = adapter.dump_json(original)
    assert isinstance(json.loads(raw), str)
    recovered = adapter.validate_json(raw)
    assert recovered == original
    assert recovered.as_tuple().exponent == original.as_tuple().exponent
