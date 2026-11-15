from acciones_ud.main import create_app


def test_orders_openapi_is_complete(api_settings) -> None:
    app = create_app(api_settings)
    document = app.openapi()
    schemas = document["components"]["schemas"]
    for schema, field in [
        ("OrderIn", "qty"),
        ("OrderOut", "qty"),
        ("ExecutionOut", "price"),
        ("PreviewOut", "reference_price"),
    ]:
        assert schemas[schema]["properties"][field]["type"] == "string"
    assert len(schemas["OrderStatus"]["enum"]) == 10
    assert "totp_code" not in schemas["OrderOut"]["properties"]
    selected = {
        path: methods
        for path, methods in document["paths"].items()
        if path.startswith(("/api/v1/orders", "/api/v1/broker/order-reviews"))
    }
    assert sum(len(methods) for methods in selected.values()) == 11
    for methods in selected.values():
        for operation in methods.values():
            assert operation["tags"][0] in {"orders", "broker-reviews"}
            assert operation["security"] == [{"AccessTokenCookie": []}]
            for status, response in operation["responses"].items():
                if int(status) >= 400:
                    assert response["content"]["application/json"]["schema"]["$ref"].endswith(
                        "/ErrorBody"
                    )
    cancellation = document["paths"]["/api/v1/orders/{id}/cancel"]["post"]
    assert {"200", "202"} <= cancellation["responses"].keys()
    create = document["paths"]["/api/v1/orders"]["post"]
    key = next(
        parameter for parameter in create["parameters"] if parameter["name"] == "Idempotency-Key"
    )
    assert key["required"] and "pattern" in key["schema"]
