from acciones_ud.wallet.domain.model import Plan


def premium_effect(new_status: str) -> bool | None:
    if new_status in {"active", "trialing"}:
        return True
    if new_status in {"canceled", "unpaid", "incomplete_expired"}:
        return False
    return None


def plans(monthly_id: str, annual_id: str) -> list[Plan]:
    from decimal import Decimal

    return [
        Plan("monthly", Decimal("12.00"), "USD", "month", monthly_id),
        Plan("annual", Decimal("120.00"), "USD", "year", annual_id),
    ]
