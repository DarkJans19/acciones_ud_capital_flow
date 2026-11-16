import pytest

from acciones_ud.config.settings import require_api_settings


@pytest.mark.parametrize(
    "field,value",
    [
        ("portfolio_risk_window_days", "6"),
        ("portfolio_risk_window_days", "366"),
        ("portfolio_risk_window_days", "secret-value"),
        ("portfolio_report_interval_seconds", "59"),
        ("portfolio_report_interval_seconds", "86401"),
        ("portfolio_report_interval_seconds", "1.2"),
        ("portfolio_jobs_enabled", "invalid"),
    ],
)
def test_invalid_configuration_names_only(api_settings, field, value):
    with pytest.raises(RuntimeError) as caught:
        require_api_settings(api_settings.model_copy(update={field: value}))
    assert str(caught.value) == "Missing or invalid configuration: " + field.upper()
