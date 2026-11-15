import pytest

from acciones_ud.config.settings import Settings, require_api_settings


@pytest.mark.parametrize(
    "name,raw",
    [
        ("order_reference_commission_rate", "1.01"),
        ("order_reference_commission_rate", "-0.01"),
        ("order_reauth_price_deviation_pct", "0"),
        ("order_reauth_price_deviation_pct", "101"),
        ("order_reauth_window_minutes", "0"),
        ("order_reauth_window_minutes", "1441"),
        ("order_local_max_age_days", "0"),
        ("order_local_max_age_days", "91"),
        ("order_reconcile_interval_seconds", "4"),
        ("order_reconcile_interval_seconds", "3601"),
        ("order_scheduler_interval_seconds", "4"),
        ("order_scheduler_interval_seconds", "3601"),
        ("order_alpaca_submit_timeout_seconds", "0.9"),
        ("order_alpaca_submit_timeout_seconds", "4.1"),
        ("orders_jobs_enabled", "invalid"),
        ("order_reference_commission_rate", "NaN"),
    ],
)
def test_invalid_order_configuration(api_settings, name, raw) -> None:
    with pytest.raises(RuntimeError) as caught:
        require_api_settings(api_settings.model_copy(update={name: raw}))
    assert str(caught.value) == "Missing or invalid configuration: " + name.upper()


@pytest.mark.parametrize(
    "name,default",
    [
        ("order_reference_commission_rate", "0.02"),
        ("order_reauth_price_deviation_pct", "1.00"),
        ("order_reauth_window_minutes", "30"),
        ("order_local_max_age_days", "5"),
        ("order_reconcile_interval_seconds", "15"),
        ("order_scheduler_interval_seconds", "30"),
        ("order_alpaca_submit_timeout_seconds", "4"),
        ("orders_jobs_enabled", "true"),
    ],
)
def test_independent_default(monkeypatch, name, default) -> None:
    for field in Settings.model_fields:
        if field.startswith("order"):
            monkeypatch.setenv(field.upper(), "17")
    monkeypatch.delenv(name.upper(), raising=False)
    assert getattr(Settings(_env_file=None), name) == default
