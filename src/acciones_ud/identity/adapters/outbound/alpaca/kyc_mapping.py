from decimal import Decimal

from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.identity.domain.financial_profile import FinancialProfile
from acciones_ud.identity.domain.kyc_submission import AccountOpeningRequest


def decimal_string(value: Decimal) -> str:
    """Serialize exactly, without floats, exponent notation or rounding CUSTOM values."""
    result = format(value, "f")
    whole, dot, fraction = result.partition(".")
    return whole + "." + fraction.ljust(2, "0") if dot else result + ".00"


def financial_fields(profile: FinancialProfile) -> dict[str, str]:
    result: dict[str, str] = {}
    for prefix, selected in (
        ("annual_income", profile.annual_income),
        ("liquid_net_worth", profile.liquid_net_worth),
        ("total_net_worth", profile.total_net_worth),
    ):
        low, high = selected.limits
        result[prefix + "_min"] = decimal_string(low)
        result[prefix + "_max"] = decimal_string(high)
    return result


def account_opening_document(request: AccountOpeningRequest) -> Record:
    return {
        "identity": {**request.identity, **financial_fields(request.financial_profile)},
        "contact": dict(request.contact),
        "disclosures": {**request.disclosures, "employment_status": request.employment_status},
        "agreements": [
            {
                "agreement": name,
                "signed_at": request.signed_at.isoformat(),
                "ip_address": request.ip_address,
            }
            for name, accepted in request.agreements.items()
            if accepted
        ],
    }
