import pytest

from acciones_ud.config.settings import Settings, require_api_settings


@pytest.mark.parametrize(
    "field,value",
    [
        ("broker_link_request_ttl_days", "0"),
        ("broker_link_request_ttl_days", "91"),
        ("proposal_ttl_hours", "0"),
        ("proposal_ttl_hours", "721"),
        ("brokers_expiry_interval_seconds", "9"),
        ("brokers_expiry_interval_seconds", "86401"),
        ("brokers_expiry_interval_seconds", "invalid"),
        ("broker_link_consent_version", ""),
        ("broker_trading_consent_version", "x" * 33),
        ("brokers_jobs_enabled", "maybe"),
    ],
)
def test_invalid_brokers_configuration_refuses_startup(api_settings, field, value):
    with pytest.raises(RuntimeError, match=field.upper()):
        require_api_settings(api_settings.model_copy(update={field: value}))


def test_default_brokers_configuration(api_settings):
    require_api_settings(api_settings)
    assert api_settings.broker_link_request_ttl_days == "7"
    assert api_settings.proposal_ttl_hours == "72"
    assert api_settings.brokers_expiry_interval_seconds == "300"
    assert Settings(_env_file=None).brokers_jobs_enabled == "true"
