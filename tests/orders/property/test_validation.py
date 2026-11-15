from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.orders.domain.model import OrderRequest, TradableAsset
from acciones_ud.orders.domain.validation import validate

numbers = st.one_of(
    st.decimals(min_value="-2", max_value="200", places=10),
    st.sampled_from(
        [
            Decimal(x)
            for x in [
                "NaN",
                "Infinity",
                "0",
                "1",
                "0.99",
                "0.9999",
                "1.001",
                "10.00",
                "0.1",
                "50.0",
                "50.1",
            ]
        ]
    ),
)
optional = st.one_of(st.none(), numbers)


def reference(request, asset, base):
    # Acceptance criteria 2.1–2.6, expressed as independent field predicates.
    def positive(value):
        return value is not None and value.is_finite() and value > 0

    def scale(value):
        return len(format(value, "f").partition(".")[2])

    def price(value):
        return positive(value) and scale(value) <= (2 if value >= 1 else 4)

    fractional = (
        asset.fractionable
        and request.order_class == "simple"
        and request.type in ["market", "limit", "stop", "stop_limit"]
        and request.time_in_force == "day"
    )
    ok = {
        "side": request.side in ["buy", "sell"],
        "type": request.type in ["market", "limit", "stop", "stop_limit", "trailing_stop"],
        "order_class": request.order_class in ["simple", "bracket"],
        "time_in_force": request.time_in_force in ["day", "gtc", "ioc", "fok"],
        "qty": positive(request.qty)
        and scale(request.qty) <= 9
        and (fractional or request.qty % 1 == 0),
    }
    required = []
    if request.type in ["limit", "stop_limit"]:
        required.append("limit_price")
    if request.type in ["stop", "stop_limit"]:
        required.append("stop_price")
    for field in ["limit_price", "stop_price", "trail_price", "trail_percent"]:
        value = getattr(request, field)
        applicable = field in required or (
            request.type == "trailing_stop" and field.startswith("trail")
        )
        present = value is not None
        ok[field] = (field not in required or present) and (applicable or not present)
        if present:
            ok[field] &= (
                positive(value) and Decimal("0.1") <= value <= 50
                if field == "trail_percent"
                else price(value)
            )
    if request.type == "trailing_stop":
        if sum(v is not None for v in [request.trail_price, request.trail_percent]) != 1:
            ok["trail_price"] = ok["trail_percent"] = False
    if request.type == "trailing_stop" or request.order_class == "bracket":
        ok["time_in_force"] &= request.time_in_force in ["day", "gtc"]
    tp, sl = request.take_profit_limit_price, request.stop_loss_stop_price
    if request.order_class == "bracket":
        ok["side"] &= request.side == "buy"
        ok["type"] &= request.type in ["market", "limit"]
        ok["qty"] &= positive(request.qty) and request.qty % 1 == 0
        ok["take_profit.limit_price"] = price(tp) and tp >= base + Decimal("0.01")
        ok["stop_loss.stop_price"] = price(sl) and sl <= base - Decimal("0.01")
    else:
        ok["take_profit.limit_price"], ok["stop_loss.stop_price"] = tp is None, sl is None
    return {field for field, valid in ok.items() if not valid}


# Feature: orders-mod-03, Property 1: Validación de parámetros contra el modelo de referencia
@settings(max_examples=200)
@given(
    st.builds(
        OrderRequest,
        symbol=st.just("AAPL"),
        side=st.sampled_from(["buy", "sell", "bad"]),
        qty=numbers,
        type=st.sampled_from(["market", "limit", "stop", "stop_limit", "trailing_stop", "bad"]),
        order_class=st.sampled_from(["simple", "bracket", "bad"]),
        time_in_force=st.sampled_from(["day", "gtc", "ioc", "fok", "bad"]),
        limit_price=optional,
        stop_price=optional,
        trail_price=optional,
        trail_percent=optional,
        take_profit_limit_price=optional,
        stop_loss_stop_price=optional,
    ),
    st.booleans(),
    st.decimals(min_value="0.01", max_value="100", places=2),
)
def test_validation_reference(request, fractionable, base) -> None:
    asset = TradableAsset("AAPL", "NASDAQ", True, True, fractionable)
    result = validate(request, asset, base)
    assert {error.field for error in result} == reference(request, asset, base)
    assert validate(request, asset, base) == result
