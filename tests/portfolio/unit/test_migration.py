import importlib.util
import io
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_portfolio_migration_renders_and_reverses():
    spec = importlib.util.spec_from_file_location(
        "portfolio_schema", Path("migrations/versions/0008_portfolio_schema.py")
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
    sql = buffer.getvalue()
    assert module.down_revision == "0007_orders_schema"
    assert "CREATE TABLE portfolio_reports" in sql
    assert "CREATE UNIQUE INDEX uq_portfolio_scheduled" in sql
    assert "to_jsonb(NEW) - 'notified_at'" in sql
    assert "CREATE TRIGGER portfolio_reports_immutable" in sql
    assert "DROP FUNCTION reject_portfolio_report_mutation()" in sql
    assert "DROP TABLE portfolio_reports" in sql
