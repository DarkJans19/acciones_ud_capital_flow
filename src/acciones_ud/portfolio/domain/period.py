from datetime import date

from acciones_ud.portfolio.domain.errors import InvalidPeriodError
from acciones_ud.portfolio.domain.model import Period


def parse(from_: date, to: date) -> Period:
    if from_ > to:
        raise InvalidPeriodError("from", "from_after_to")
    if (to - from_).days + 1 > 366:
        raise InvalidPeriodError("to", "too_long")
    return Period(from_, to)
