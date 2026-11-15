from acciones_ud.identity.domain.preferences import default_preferences, validate_patch


def test_balance_preferences() -> None:
    entries = [p for p in default_preferences() if p["event_type"] == "balance_changes"]
    assert len(entries) == 4
    assert [p["channel"] for p in entries if p["enabled"]] == ["in_app"]
    validate_patch(entries, has_phone=True, has_telegram=True)
