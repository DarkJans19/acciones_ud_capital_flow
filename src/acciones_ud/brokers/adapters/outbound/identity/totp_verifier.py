from collections.abc import Callable
from uuid import UUID

from acciones_ud.identity.application.order_authorization import OrderTotpService
from acciones_ud.shared.domain.clock import Clock


class TotpVerifier:
    def __init__(self, service: Callable[[], OrderTotpService], clock: Clock) -> None:
        self.service, self.clock = service, clock

    async def verify(self, user_id: UUID, code: str) -> bool:
        return await self.service().verify(user_id, code, self.clock.now())
