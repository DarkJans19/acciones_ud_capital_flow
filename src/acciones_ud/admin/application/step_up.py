from uuid import UUID

from acciones_ud.admin.domain.ports import TotpVerifierPort
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import AppError, ErrorCode


class StepUp:
    def __init__(self, verifier: TotpVerifierPort, clock: Clock) -> None:
        self.verifier, self.clock = verifier, clock

    async def verify(self, actor: UUID, code: str | None) -> None:
        if not await self.verifier.has_active_totp(actor):
            raise AppError(409, ErrorCode.MFA_ENROLLMENT_REQUIRED, "Confirmed TOTP required.")
        if not code:
            raise AppError(409, ErrorCode.EXTRA_AUTHORIZATION_REQUIRED, "TOTP required.")
        if not await self.verifier.verify(actor, code, self.clock.now()):
            raise AppError(401, ErrorCode.EXTRA_AUTHORIZATION_INVALID, "Invalid TOTP.")
