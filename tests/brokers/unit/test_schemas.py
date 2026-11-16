from decimal import Decimal

import pytest
from pydantic import ValidationError

from acciones_ud.brokers.adapters.inbound.http.schemas.requests import InvestorDecisionIn, RatingIn
from acciones_ud.brokers.adapters.inbound.http.schemas.responses import ProposalVersion
from tests.brokers.unit.test_proposals import proposal_fixture


async def test_decimal_output_is_string_and_totp_is_redacted():
    ctx, _, _, _, _, _, proposal = await proposal_fixture()
    version = await ctx.uow.work.versions.get(proposal_id=proposal.id, version=1)
    output = ProposalVersion.model_validate(version).model_dump(mode="json")
    assert output["qty"] == "2" and output["estimated_cost"] == "204.00"
    assert Decimal(output["reference_price"]) == Decimal(100)
    request = InvestorDecisionIn(version=1, decision="accept", totp_code="private-value")
    assert "private-value" not in repr(request)
    with pytest.raises(ValidationError):
        RatingIn(stars=True)
