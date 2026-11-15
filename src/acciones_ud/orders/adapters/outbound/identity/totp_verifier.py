from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from acciones_ud.identity.application.order_authorization import OrderTotpService


class IdentityTotpVerifier:
    def __init__(self, service: OrderTotpService | Callable[[], OrderTotpService]) -> None:
        self._service = service

    @property
    def service(self) -> OrderTotpService:
        return self._service() if callable(self._service) else self._service

    async def has_active_totp(self, user_id: UUID) -> bool:
        return await self.service.has_active_totp(user_id)

    async def verify(self, user_id: UUID, code: str, at: datetime) -> bool:
        return await self.service.verify(user_id, code, at)
