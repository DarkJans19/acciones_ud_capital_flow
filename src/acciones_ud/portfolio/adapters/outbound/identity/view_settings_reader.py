from decimal import Decimal
from uuid import UUID

from acciones_ud.identity.application.account import AccountService
from acciones_ud.identity.domain.settings import PORTFOLIO_DEFAULTS
from acciones_ud.portfolio.domain.model import ViewSettings


class ViewSettingsReader:
    def __init__(self, service: AccountService) -> None:
        self.service = service

    async def get(self, user_id: UUID) -> ViewSettings:
        values = {**PORTFOLIO_DEFAULTS, **await self.service.settings(user_id, "portfolio")}
        values["hide_threshold"] = Decimal(str(values["hide_threshold"]))
        return ViewSettings(**values)
