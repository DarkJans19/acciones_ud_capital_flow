import importlib.util
import io
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations


@pytest.mark.parametrize(
    "revision",
    ["0010_admin_fees_audit", "0011_admin_audit_trail_halts", "0012_admin_compliance_bi"],
)
def test_admin_revisions_render_both_directions_offline(revision):
    spec = importlib.util.spec_from_file_location(
        revision, Path("migrations/versions") / f"{revision}.py"
    )
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
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "CREATE TRIGGER" in sql and "DROP" in sql
    if revision.startswith("0011"):
        assert "CREATE VIEW audit_trail" in sql
        assert "UPDATE orders" not in sql  # H3: historical orders never acquire invented terms.
        assert "order_commission_terms_guard" in sql
