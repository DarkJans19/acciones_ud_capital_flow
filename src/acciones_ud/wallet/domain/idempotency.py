import hashlib
import json
from decimal import Decimal
from uuid import UUID


def request_hash(direction: str, bank_relationship_id: UUID, amount: Decimal, currency: str) -> str:
    canonical = [
        direction,
        str(bank_relationship_id),
        str(amount.quantize(Decimal("0.01"))),
        currency,
    ]
    return hashlib.sha256(json.dumps(canonical, separators=(",", ":")).encode()).hexdigest()
