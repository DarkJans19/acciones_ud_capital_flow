import hashlib
import hmac
from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.wallet.domain.errors import InvalidSignatureError
from acciones_ud.wallet.domain.stripe_signature import verify


# Feature: wallet-mod-04, Property 7: Verificación de firma del webhook
@settings(max_examples=100)
@given(st.binary(), st.text(min_size=1), st.integers(-1000, 1000))
def test_signature(payload: bytes, secret: str, offset: int) -> None:
    at = datetime(2026, 1, 1, tzinfo=UTC)
    timestamp = int(at.timestamp()) + offset
    signature = hmac.new(
        secret.encode(), str(timestamp).encode() + b"." + payload, hashlib.sha256
    ).hexdigest()
    header = f"t={timestamp},v1=invalid,v1={signature}"
    if abs(offset) <= 300:
        verify(payload, header, secret, at)
    else:
        with pytest.raises(InvalidSignatureError):
            verify(payload, header, secret, at)
    for body, signed, key in [
        (payload + b"!", header, secret),
        (payload, None, secret),
        (payload, header, secret + "!"),
    ]:
        with pytest.raises(InvalidSignatureError):
            verify(body, signed, key, at)
