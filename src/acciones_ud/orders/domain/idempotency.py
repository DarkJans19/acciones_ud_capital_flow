import hashlib
import json
from dataclasses import asdict
from decimal import Decimal

from acciones_ud.orders.domain.model import OrderRequest


def request_hash(request: OrderRequest) -> str:
    canonical = {
        key: str(value.normalize()) if isinstance(value, Decimal) else value
        for key, value in asdict(request).items()
    }
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
