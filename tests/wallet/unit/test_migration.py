import importlib.util
import io
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_wallet_migration_reverses() -> None:
    spec = importlib.util.spec_from_file_location(
        "wallet_schema", Path("migrations/versions/0006_wallet_schema.py")
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = io.StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )
    with Operations.context(context):
        module.upgrade()
        module.downgrade()
    sql = output.getvalue()
    for table in (
        "wallet_transfers",
        "subscriptions",
        "stripe_events",
        "wallet_idempotency_keys",
        "subscription_payments",
    ):
        assert f"CREATE TABLE {table}" in sql
        assert f"DROP TABLE {table}" in sql
    assert "ON CONFLICT DO NOTHING" in sql
    assert "WHERE status IN ('active','trialing','past_due')" in sql
    upgrade, downgrade = sql.split("DELETE FROM notification_preferences", 1)
    assert upgrade.index("ADD CONSTRAINT notification_preferences_event_type_check") < (
        upgrade.index("INSERT INTO notification_preferences")
    )
    assert "'balance_changes'" in upgrade.split("CHECK (", 1)[1].split(";", 1)[0]
    restored = downgrade.split("ADD CONSTRAINT notification_preferences_event_type_check", 1)[1]
    assert "balance_changes" not in restored.split(";", 1)[0]
