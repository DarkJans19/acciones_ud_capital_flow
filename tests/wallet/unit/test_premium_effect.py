import pytest

from acciones_ud.wallet.domain.subscriptions import premium_effect


@pytest.mark.parametrize(
    "status,effect",
    [
        ("active", True),
        ("trialing", True),
        ("canceled", False),
        ("unpaid", False),
        ("incomplete_expired", False),
        ("past_due", None),
        ("incomplete", None),
    ],
)
def test_premium_effect(status: str, effect: bool | None) -> None:
    assert premium_effect(status) is effect
