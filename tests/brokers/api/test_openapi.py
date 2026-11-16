import asyncio
from decimal import Decimal

from fastapi.testclient import TestClient

from tests.brokers.api.support import app_for
from tests.brokers.support import context
from tests.brokers.unit.test_proposals import proposal_fixture


def test_openapi_declares_safe_error_bodies_and_public_profile_exception():
    schema = app_for(context()).openapi()
    operations = [operation for path in schema["paths"].values() for operation in path.values()]
    assert len(operations) == 33
    for operation in operations:
        for code, response in operation["responses"].items():
            if int(code) >= 400:
                assert response["content"]["application/json"]["schema"]["$ref"].endswith(
                    "/ErrorBody"
                )
    public = schema["paths"]["/api/v1/brokers/{broker_id}"]["get"]
    assert "401" not in public["responses"] and not public.get("security")
    for item in schema["paths"].values():
        for operation in item.values():
            if operation is not public:
                assert "401" in operation["responses"]
    version = schema["components"]["schemas"]["ProposalVersion"]
    assert version["properties"]["qty"]["type"] == "string"
    assert version["properties"]["estimated_cost"]["type"] == "string"


def test_invalid_totp_and_validation_bodies_do_not_echo_secrets(caplog):
    ctx, investor, _, _, _, _, proposal = asyncio.run(proposal_fixture())
    ctx.controls.threshold = Decimal("204")
    client = TestClient(app_for(ctx))
    client.cookies.set("access_token", str(investor))
    secret = "private-code-value"
    response = client.post(
        f"/api/v1/proposals/{proposal.id}/decision",
        json={
            "version": 1,
            "decision": "accept",
            "totp_code": secret,
        },
    )
    assert response.status_code == 401 and response.json()["code"] == "EXTRA_AUTHORIZATION_INVALID"
    invalid = client.post(
        f"/api/v1/proposals/{proposal.id}/decision",
        json={
            "version": secret,
            "decision": "accept",
            "totp_code": secret,
        },
    )
    assert invalid.status_code == 422 and invalid.json()["code"] == "VALIDATION_ERROR"
    records = repr(ctx.uow.work.events.values) + repr(ctx.uow.work.decisions.values)
    assert secret not in response.text + invalid.text + caplog.text + records
    assert "alpaca_account_id" not in response.text + invalid.text + records
