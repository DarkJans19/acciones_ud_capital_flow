from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt

from acciones_ud.brokers.application.commands import ProposalContent


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BrokerProfileIn(RequestModel):
    specialty: str = Field(min_length=1, max_length=100)
    years_experience: StrictInt = Field(ge=0, le=60)
    certifications: tuple[Annotated[str, Field(min_length=1, max_length=100)], ...] = Field(
        default=(), max_length=10
    )
    description: str = Field(default="", max_length=1000)


class ConsentIn(RequestModel):
    consent_accepted: StrictBool = False


class LinkIn(ConsentIn):
    broker_id: UUID


class ReasonIn(RequestModel):
    reason: str = Field(min_length=1, max_length=500)


class EndLinkIn(ReasonIn):
    confirmed: StrictBool = False


class OrderReviewIn(RequestModel):
    enabled: StrictBool


class ProposalContentIn(RequestModel):
    symbol: str = Field(min_length=1, max_length=32)
    side: Literal["buy", "sell"]
    qty: Decimal = Field(gt=0, max_digits=20, decimal_places=9, allow_inf_nan=False)
    type: Literal["market", "limit"]
    limit_price: Decimal | None = Field(
        default=None, gt=0, max_digits=18, decimal_places=4, allow_inf_nan=False
    )

    def content(self) -> ProposalContent:
        return ProposalContent(self.symbol, self.side, self.qty, self.type, self.limit_price)


class ProposalIn(ProposalContentIn):
    investor_id: UUID


class ModifyProposalIn(ProposalContentIn):
    version: int = Field(ge=1)


class WithdrawProposalIn(EndLinkIn):
    version: int = Field(ge=1)


class InvestorDecisionIn(RequestModel):
    version: int = Field(ge=1)
    decision: Literal["accept", "reject"]
    comment: str = Field(default="", max_length=500)
    totp_code: SecretStr | None = Field(default=None, max_length=128)


class BrokerDecisionIn(RequestModel):
    version: int = Field(ge=1)
    decision: Literal["approve", "decline"]
    evidence_message_ids: tuple[UUID, ...] = ()
    evidence_text: str = Field(default="", max_length=1000)


class MessageIn(RequestModel):
    body: str = Field(min_length=1, max_length=1000)


class RatingIn(RequestModel):
    stars: StrictInt = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=1000)
