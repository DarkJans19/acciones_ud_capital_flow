import logging

from acciones_ud.identity.domain.account_ports import AccountWorkFactory
from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.identity.domain.kyc_cache import serve_cached
from acciones_ud.identity.domain.kyc_ports import AlpacaAccountsPort, KycWorkFactory
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.shared.domain.alpaca_errors import AlpacaError
from acciones_ud.shared.domain.clock import Clock, SystemClock
from acciones_ud.shared.domain.errors import AppError, ErrorCode

logger = logging.getLogger(__name__)


class AccountInfoService:
    def __init__(
        self,
        accounts: AccountWorkFactory,
        kyc: KycWorkFactory,
        alpaca: AlpacaAccountsPort,
        cache_ttl_seconds: int = 60,
        clock: Clock | None = None,
    ) -> None:
        self.accounts, self.kyc, self.alpaca = accounts, kyc, alpaca
        self.cache_ttl_seconds = cache_ttl_seconds
        self.clock = clock or SystemClock()

    async def me(self, current: CurrentUser) -> Record:
        # Both reads happen before any Alpaca call, so a database failure is 503 (6.6).
        async with self.accounts() as work:
            user = await work.account.user(current.user_id)
        async with self.kyc() as work:
            linked = await work.kyc.get(current.user_id)
        status = None
        unavailable = False
        if linked and linked["alpaca_account_id"]:
            now = self.clock.now()
            if serve_cached(
                linked.get("status_checked_at"), now, self.cache_ttl_seconds
            ):
                status = linked["status"]
            else:
                try:
                    live = await self.alpaca.get_account(
                        linked["alpaca_account_id"], timeout=10
                    )
                except AlpacaError:
                    unavailable = True
                else:
                    status = live.status
                    try:
                        async with self.kyc() as work:
                            await work.kyc.record_status_check(live, now)
                    except AppError as exc:
                        if exc.code is not ErrorCode.DATABASE_UNAVAILABLE:
                            raise
                        # The answer is still useful; only the cache stays behind (23.11).
                        logger.warning("KYC status check could not be stored")
        result = {
            key: user[key]
            for key in (
                "first_names",
                "last_names",
                "email",
                "phone",
                "country",
                "account_status",
                "is_premium",
                "broker_requested",
                "interests",
                "investor_level",
            )
        }
        result.update(
            user_id=current.user_id,
            registered_at=user["created_at"],
            contracted_plan=None,
            associated_broker=None,
            roles=sorted(current.roles),
            kyc_status=status,
            kyc_status_unavailable=unavailable,
            mfa_enrolled=user["totp_confirmed_at"] is not None,
        )
        return result
