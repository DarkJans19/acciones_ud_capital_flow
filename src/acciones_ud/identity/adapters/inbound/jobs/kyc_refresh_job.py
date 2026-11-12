"""KYC status refresh job (Requirement 23, D8).

Owned by the identity module, it reuses one stored row as the cache and never
holds a database transaction while waiting on Alpaca.
"""

import asyncio
import logging

from acciones_ud.identity.domain.kyc_ports import AlpacaAccountsPort, KycWorkFactory
from acciones_ud.shared.domain.alpaca_errors import AlpacaError, AlpacaRateLimited
from acciones_ud.shared.domain.clock import Clock

logger = logging.getLogger(__name__)

STOP_TIMEOUT_SECONDS = 10.0
STATUS_TIMEOUT_SECONDS = 10.0


class KycRefreshJob:
    def __init__(
        self,
        accounts: AlpacaAccountsPort,
        uow: KycWorkFactory,
        clock: Clock,
        interval_seconds: int,
    ) -> None:
        self.accounts, self.uow, self.clock = accounts, uow, clock
        self.interval_seconds = interval_seconds
        self._stopping = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def run(self) -> None:
        # First cycle one interval after start; the next sleep starts after a cycle
        # ends, so cycles never overlap (23.2, 23.14).
        while not await self._stopped_within(self.interval_seconds):
            try:
                await self.run_cycle()
            except Exception:
                # Database down or unexpected: end the cycle, keep running (23.9).
                logger.exception("kyc refresh cycle failed")

    async def _stopped_within(self, seconds: float) -> bool:
        try:
            await asyncio.wait_for(self._stopping.wait(), seconds)
        except TimeoutError:
            return False
        return True

    async def run_cycle(self) -> None:
        async with self.uow() as work:
            account_ids = await work.kyc.linked_account_ids()
        for account_id in account_ids:
            if self._stopping.is_set():
                return
            try:
                account = await self.accounts.get_account(
                    account_id, timeout=STATUS_TIMEOUT_SECONDS
                )
            except AlpacaRateLimited:
                return
            except AlpacaError:
                continue
            # One transaction per account, so earlier updates survive a later failure.
            async with self.uow() as work:
                await work.kyc.record_status_check(account, self.clock.now())

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        self._stopping.set()
        task = self._task
        self._task = None
        if task is None:
            return
        try:
            await asyncio.wait_for(task, timeout=STOP_TIMEOUT_SECONDS)
        except TimeoutError:
            # wait_for already cancelled the task; an in-flight request writes nothing.
            pass
