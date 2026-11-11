from acciones_ud.identity.domain.account_ports import AccountWorkFactory
from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.identity.domain.kyc_ports import AlpacaAccountsPort, KycWorkFactory
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.shared.domain.alpaca_errors import AlpacaError


class AccountInfoService:
    def __init__(
        self, accounts: AccountWorkFactory, kyc: KycWorkFactory, alpaca: AlpacaAccountsPort
    ) -> None:
        self.accounts, self.kyc, self.alpaca = accounts, kyc, alpaca

    async def me(self, current: CurrentUser) -> Record:
        async with self.accounts() as work:
            user = await work.account.user(current.user_id)
        async with self.kyc() as work:
            linked = await work.kyc.get(current.user_id)
        status = None
        unavailable = False
        if linked and linked["alpaca_account_id"]:
            try:
                status = (await self.alpaca.get_account(linked["alpaca_account_id"])).status
            except AlpacaError:
                unavailable = True
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
