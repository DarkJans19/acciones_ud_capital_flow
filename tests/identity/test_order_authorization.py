from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from cryptography.fernet import Fernet

from acciones_ud.identity.adapters.outbound.security.cipher import SecretCipher
from acciones_ud.identity.adapters.outbound.security.totp import TotpProvider
from acciones_ud.identity.application.order_authorization import OrderTotpService
from tests.support.clock import FakeClock


async def test_order_totp_requires_enrollment_and_prevents_reuse() -> None:
    clock, cipher, provider = (
        FakeClock(),
        SecretCipher(Fernet.generate_key().decode()),
        TotpProvider(),
    )
    secret, user_id = provider.new_secret(), uuid4()
    record = {
        "totp_secret_enc": cipher.encrypt(secret),
        "totp_confirmed_at": None,
        "totp_last_step": None,
    }
    repo = SimpleNamespace(lock_user=AsyncMock(return_value=record))

    async def update(user_id, changes):
        record.update(changes)

    repo.update_user = update

    @asynccontextmanager
    async def uow():
        yield SimpleNamespace(auth=repo)

    service = OrderTotpService(uow, cipher, provider)
    code = provider.generator(secret).generate(int(clock.now().timestamp()) // 30)
    assert not await service.has_active_totp(user_id)
    assert not await service.verify(user_id, code, clock.now())
    record["totp_confirmed_at"] = clock.now()
    assert await service.has_active_totp(user_id)
    assert await service.verify(user_id, code, clock.now())
    assert not await service.verify(user_id, code, clock.now())
