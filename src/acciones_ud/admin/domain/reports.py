import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID


def canonical_value(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return canonical_value(asdict(value))
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Non-finite decimal")
        if value == 0:
            return "0"
        text = format(value, "f")
        return text.rstrip("0").rstrip(".") if "." in text else text
    if isinstance(value, datetime):
        if value.utcoffset() is None:
            raise ValueError("Timezone required")
        return value.astimezone(UTC).isoformat()
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(k): canonical_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical_value(v) for v in value]
    return value


def canonical_json(content: Any) -> bytes:
    return json.dumps(
        canonical_value(content),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def digest(content: Any) -> str:
    return hashlib.sha256(canonical_json(content)).hexdigest()
