from decimal import Decimal
from uuid import uuid4

from acciones_ud.wallet.domain.idempotency import request_hash


def test_hash_is_canonical() -> None:
    bank = uuid4()
    assert request_hash("INCOMING", bank, Decimal("10"), "USD") == request_hash(
        "INCOMING", bank, Decimal("10.00"), "USD"
    )
    assert request_hash("OUTGOING", bank, Decimal("10"), "USD") != request_hash(
        "INCOMING", bank, Decimal("10"), "USD"
    )
