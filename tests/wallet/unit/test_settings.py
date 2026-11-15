import pytest

from acciones_ud.config.settings import Settings, require_api_settings


@pytest.mark.parametrize(
    "field,value",
    [
        ("stripe_secret_key", "sk_live_do_not_echo"),
        ("stripe_webhook_secret", None),
        ("stripe_price_monthly_id", "bad"),
        ("stripe_price_annual_id", "bad"),
        ("wallet_max_transfer_amount", "1.001"),
        ("wallet_max_transfer_amount", "1.000"),
        ("wallet_max_transfer_amount", "NaN"),
        ("wallet_reconcile_interval_seconds", "9"),
        ("wallet_reconcile_interval_seconds", "3601"),
        ("wallet_reconciler_enabled", "yes"),
    ],
)
def test_invalid_configuration_names_only(api_settings: Settings, field: str, value: str) -> None:
    with pytest.raises(RuntimeError) as caught:
        require_api_settings(api_settings.model_copy(update={field: value}))
    assert str(caught.value) == "Missing or invalid configuration: " + field.upper()
