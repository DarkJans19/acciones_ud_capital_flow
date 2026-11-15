import hashlib
import hmac
from datetime import datetime

from acciones_ud.wallet.domain.errors import InvalidSignatureError


def verify(
    payload: bytes, header: str | None, secret: str, now: datetime, tolerance_s: int = 300
) -> None:
    try:
        parts = [part.strip().split("=", 1) for part in (header or "").split(",")]
        timestamps = [value for key, value in parts if key == "t"]
        if len(timestamps) != 1:
            raise ValueError()
        timestamp = int(timestamps[0])
        if abs(now.timestamp() - timestamp) > tolerance_s:
            raise ValueError()
        message = str(timestamp).encode() + b"." + payload
        expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(expected, value) for key, value in parts if key == "v1"):
            raise ValueError()
    except (ValueError, TypeError, UnicodeError, OverflowError):
        raise InvalidSignatureError() from None
