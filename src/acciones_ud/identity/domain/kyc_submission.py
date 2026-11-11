from dataclasses import dataclass, field
from datetime import datetime

from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.identity.domain.financial_profile import FinancialProfile


@dataclass(frozen=True)
class AccountOpeningRequest:
    identity: Record = field(repr=False)
    contact: Record = field(repr=False)
    financial_profile: FinancialProfile
    employment_status: str
    disclosures: dict[str, bool]
    agreements: dict[str, bool]
    signed_at: datetime
    ip_address: str = field(repr=False)
