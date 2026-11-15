from acciones_ud.main import create_app


def test_wallet_openapi(api_settings) -> None:
    app = create_app(api_settings)
    document = app.openapi()
    schemas = document["components"]["schemas"]
    assert schemas["TransferOut"]["properties"]["amount"]["type"] == "string"
    assert schemas["TransferIn"]["properties"]["amount"]["type"] == "string"
    assert "bank_account_number" not in schemas["BankOut"]["properties"]
    webhook = document["paths"]["/api/v1/webhooks/stripe"]["post"]
    assert not webhook.get("security")
    for path, methods in document["paths"].items():
        if path.startswith(("/api/v1/wallet", "/api/v1/subscriptions")):
            for operation in methods.values():
                assert operation["tags"][0] in {"wallet", "subscriptions"}
                assert "401" in operation["responses"] and "403" in operation["responses"]
