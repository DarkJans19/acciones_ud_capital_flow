import importlib.util
import io
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_identity_schema_renders_postgresql_and_reverses() -> None:
    path = Path("migrations/versions/0001_identity_schema.py")
    spec = importlib.util.spec_from_file_location("identity_schema", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    buffer = io.StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={
            "as_sql": True,
            "output_buffer": buffer,
        },
    )
    with Operations.context(context):
        module.upgrade()
        module.downgrade()
    sql = buffer.getvalue()
    for table in module.TABLES:
        assert f"CREATE TABLE {table}" in sql
        assert f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY' in sql
        assert f"DROP TABLE {table}" in sql
    assert "CREATE UNIQUE INDEX" not in sql or "email_normalized" in sql
    assert "CONSTRAINT uq_users_email_normalized UNIQUE (email_normalized)" in sql
    assert "WHERE used_at is null and invalidated_at is null" in sql
    assert "invalid_recovery_code" in sql
    assert "ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY" in sql


def test_admin_gaps_revision_renders_postgresql_and_reverses() -> None:
    path = Path("migrations/versions/0005_identity_admin_gaps.py")
    spec = importlib.util.spec_from_file_location("identity_admin_gaps", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    buffer = io.StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": buffer},
    )
    with Operations.context(context):
        module.upgrade()
        module.downgrade()
    sql = buffer.getvalue()
    assert "CREATE TABLE admin_audit_log" in sql
    assert 'ALTER TABLE "admin_audit_log" ENABLE ROW LEVEL SECURITY' in sql
    assert "admin_audit_log_immutable" in sql
    assert "status_checked_at" in sql
    assert "ix_users_created_at_id" in sql
    assert "DROP TABLE admin_audit_log" in sql
    for action in module.ACTIONS:
        assert action in sql
