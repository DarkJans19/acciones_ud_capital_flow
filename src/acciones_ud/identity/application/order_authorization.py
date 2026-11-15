"""RF-30: verify an enrolled TOTP without creating a login session."""

from datetime import datetime
from uuid import UUID

from acciones_ud.identity.domain.auth_ports import AuthWorkFactory, TotpProvider
from acciones_ud.identity.domain.ports import SecretCipher
from acciones_ud.identity.domain.totp_window import match


class OrderTotpService:
    def __init__(self, uow: AuthWorkFactory, cipher: SecretCipher, totp: TotpProvider) -> None:
        self.uow, self.cipher, self.totp = uow, cipher, totp

    async def has_active_totp(self, user_id: UUID) -> bool:
        async with self.uow() as work:
            user = await work.auth.lock_user(user_id)
            return bool(user.get("totp_confirmed_at") and user.get("totp_secret_enc"))

    async def verify(self, user_id: UUID, code: str, at: datetime) -> bool:
        async with self.uow() as work:
            user = await work.auth.lock_user(user_id)
            if not user.get("totp_confirmed_at") or not user.get("totp_secret_enc"):
                return False
            generator = self.totp.generator(self.cipher.decrypt(user["totp_secret_enc"]))
            step = match(generator, code, at, user.get("totp_last_step"))
            if step is None:
                return False
            await work.auth.update_user(user_id, {"totp_last_step": step})
            return True
