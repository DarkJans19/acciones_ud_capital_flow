import importlib.util
import io
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_orders_migration_renders_and_reverses() -> None:
    spec = importlib.util.spec_from_file_location(
        "orders_schema", Path("migrations/versions/0007_orders_schema.py")
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    buffer = io.StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": buffer}
    )
    with Operations.context(context):
        module.upgrade()
        module.downgrade()
    sql = " ".join(buffer.getvalue().split())
    names = [
        "orders",
        "order_legs",
        "order_events",
        "order_executions",
        "order_reservations",
        "order_idempotency_keys",
        "order_reauthorizations",
        "order_cancel_requests",
        "order_review_comments",
        "order_schedule_changes",
        "order_activity_cursors",
    ]
    for name in names:
        assert f"CREATE TABLE {name}" in sql and f"DROP TABLE {name}" in sql
        assert f'ALTER TABLE "{name}" ENABLE ROW LEVEL SECURITY' in sql
    assert "UNIQUE (client_order_id)" in sql
    assert "filled_qty >= 0 AND filled_qty <= qty" in sql
    assert "WHERE decision IS NULL" in sql
    assert "filled_avg_price NUMERIC," in sql
    assert "order_executions" in sql and "order_updates" in sql
    upgrade, downgrade = sql.split("DELETE FROM notification_preferences", 1)
    assert upgrade.index("ADD CONSTRAINT notification_preferences_event_type_check") < (
        upgrade.index("INSERT INTO notification_preferences")
    )
    vocabulary = upgrade.split("ADD CONSTRAINT notification_preferences_event_type_check", 1)[1]
    assert "'order_updates'" in vocabulary.split(";", 1)[0]
    restored = downgrade.split("ADD CONSTRAINT notification_preferences_event_type_check", 1)[1]
    assert "'balance_changes'" in restored.split(";", 1)[0]
    assert "'order_updates'" not in restored.split(";", 1)[0]
