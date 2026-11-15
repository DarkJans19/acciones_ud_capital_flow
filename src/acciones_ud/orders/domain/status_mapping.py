from decimal import Decimal

from acciones_ud.orders.domain.model import OrderStatus as S


def map_alpaca(provider_status: str, filled_qty: Decimal) -> S | None:
    if provider_status in {
        "new",
        "accepted",
        "pending_new",
        "accepted_for_bidding",
        "calculated",
        "held",
        "stopped",
        "suspended",
        "pending_cancel",
        "pending_replace",
    }:
        return S.SUBMITTED
    if provider_status in {"partially_filled", "filled"}:
        return S.EXECUTING
    if provider_status == "done_for_day":
        return S.EXECUTING if filled_qty > 0 else S.SUBMITTED
    return {"canceled": S.CANCELED, "expired": S.EXPIRED, "rejected": S.REJECTED}.get(
        provider_status
    )
