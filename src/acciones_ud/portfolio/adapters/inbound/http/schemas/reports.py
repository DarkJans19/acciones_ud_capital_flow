from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from acciones_ud.portfolio.adapters.inbound.http.schemas.common import Output
from acciones_ud.portfolio.adapters.inbound.http.schemas.pagination import PageResponse
from acciones_ud.portfolio.domain import model as m
from acciones_ud.portfolio.domain.period import parse


class PeriodInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_: date = Field(alias="from")
    to: date

    def period(self) -> m.Period:
        return parse(self.from_, self.to)


class PeriodResponse(Output):
    from_: date = Field(serialization_alias="from")
    to: date


class ReportSummary(Output):
    id: UUID
    owner_id: UUID
    owner_role: m.OwnerRole
    type: m.ReportType
    period: PeriodResponse
    positions_as_of: datetime
    generated_at: datetime
    notified_at: datetime | None


class ReportResponse(ReportSummary):
    content: dict[str, object]


class ReportPage(PageResponse[ReportSummary]):
    pass
