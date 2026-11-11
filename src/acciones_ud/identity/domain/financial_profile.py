"""Acciones UD's USD catalog (RFP-01); these codes are not Alpaca enums."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from acciones_ud.shared.domain.errors import AppError, ErrorCode


class FinancialRangeCode(StrEnum):
    RANGE_1 = "RANGE_1"
    RANGE_2 = "RANGE_2"
    RANGE_3 = "RANGE_3"
    RANGE_4 = "RANGE_4"
    RANGE_5 = "RANGE_5"
    RANGE_6 = "RANGE_6"
    CUSTOM = "CUSTOM"


CATALOG: dict[FinancialRangeCode, tuple[Decimal, Decimal]] = {
    FinancialRangeCode.RANGE_1: (Decimal("0.00"), Decimal("24999.99")),
    FinancialRangeCode.RANGE_2: (Decimal("25000.00"), Decimal("49999.99")),
    FinancialRangeCode.RANGE_3: (Decimal("50000.00"), Decimal("99999.99")),
    FinancialRangeCode.RANGE_4: (Decimal("100000.00"), Decimal("249999.99")),
    FinancialRangeCode.RANGE_5: (Decimal("250000.00"), Decimal("499999.99")),
    FinancialRangeCode.RANGE_6: (Decimal("500000.00"), Decimal("999999.99")),
}


@dataclass(frozen=True)
class FinancialRange:
    code: FinancialRangeCode
    custom_min: Decimal | None = None
    custom_max: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, FinancialRangeCode):
            self._invalid("range")
        if self.code == FinancialRangeCode.CUSTOM:
            low, high = self.custom_min, self.custom_max
            if (
                not isinstance(low, Decimal)
                or not isinstance(high, Decimal)
                or not low.is_finite()
                or not high.is_finite()
                or low < 0
                or high < low
            ):
                self._invalid("custom_min, custom_max")
        elif self.custom_min is not None or self.custom_max is not None:
            self._invalid("custom_min, custom_max")

    @staticmethod
    def _invalid(field: str) -> None:
        raise AppError(422, ErrorCode.VALIDATION_ERROR, "Invalid financial field: " + field)

    @property
    def limits(self) -> tuple[Decimal, Decimal]:
        if self.code == FinancialRangeCode.CUSTOM:
            assert self.custom_min is not None and self.custom_max is not None
            return self.custom_min, self.custom_max
        return CATALOG[self.code]


@dataclass(frozen=True)
class FinancialProfile:
    annual_income: FinancialRange
    liquid_net_worth: FinancialRange
    total_net_worth: FinancialRange

    def __post_init__(self) -> None:
        liquid_min, liquid_max = self.liquid_net_worth.limits
        total_min, total_max = self.total_net_worth.limits
        if liquid_min > total_min or liquid_max > total_max:
            raise AppError(
                422,
                ErrorCode.VALIDATION_ERROR,
                "Invalid field: liquid_net_worth; bounds exceed total_net_worth.",
            )
