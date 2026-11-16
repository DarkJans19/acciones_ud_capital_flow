import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest


def test_bootstrap_uses_historical_preferences(monkeypatch: pytest.MonkeyPatch) -> None:
    """0002 must still run before the wallet/orders vocabulary exists in SQL."""
    spec = importlib.util.spec_from_file_location(
        "initial_admin_snapshot", Path("migrations/versions/0002_initial_admin.py")
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, value in {
        "EMAIL": "bootstrap@example.com",
        "PASSWORD_HASH": "$argon2id$historical-test-hash",
        "FIRST_NAMES": "Bootstrap",
        "LAST_NAMES": "Admin",
        "PHONE": "+573001234567",
        "COUNTRY": "CO",
    }.items():
        monkeypatch.setenv("INITIAL_ADMIN_" + name, value)
    connection = Mock()
    connection.execute.return_value.first.return_value = None
    monkeypatch.setattr(module.op, "get_bind", lambda: connection)
    module.upgrade()
    preferences = connection.execute.call_args_list[-1].args[1]
    assert len(preferences) == 28
    assert {p["event_type"] for p in preferences} == {
        "market_open",
        "market_close",
        "proposals",
        "approval_requests",
        "price_changes",
        "execution_confirmations",
        "daily_summary",
    }
    assert all(p["enabled"] == (p["channel"] == "in_app") for p in preferences)
