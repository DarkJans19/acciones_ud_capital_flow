import asyncio
import os
import shutil
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

pytestmark = pytest.mark.db


def scalar(url: str, query: str) -> object:
    async def run() -> object:
        from acciones_ud.shared.infrastructure.db import build_engine

        engine = build_engine(url)
        try:
            async with engine.connect() as connection:
                return (await connection.execute(sa.text(query))).scalar_one()
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_migration_round_trip_and_failed_revision_keeps_previous(
    migrated_database: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    assert (
        scalar(
            migrated_database,
            "SELECT count(*) FROM pg_tables WHERE schemaname='public' "
            "AND tablename <> 'alembic_version'",
        )
        == 0
    )
    command.upgrade(config, "head")
    assert (
        scalar(migrated_database, "SELECT version_num FROM alembic_version")
        == "0005_identity_admin_gaps"
    )
    assert scalar(migrated_database, "SELECT count(*) FROM markets") == 7
    assert scalar(migrated_database, "SELECT count(*) FROM notification_preferences") == 28
    command.downgrade(config, "base")
    phone = os.environ["INITIAL_ADMIN_PHONE"]
    monkeypatch.setenv("INITIAL_ADMIN_PHONE", "")
    with pytest.raises(RuntimeError, match="INITIAL_ADMIN_PHONE"):
        command.upgrade(config, "head")
    assert (
        scalar(migrated_database, "SELECT version_num FROM alembic_version")
        == "0001_identity_schema"
    )
    monkeypatch.setenv("INITIAL_ADMIN_PHONE", phone)
    command.upgrade(config, "head")
    assert (
        scalar(migrated_database, "SELECT version_num FROM alembic_version")
        == "0005_identity_admin_gaps"
    )


def test_cancellation_upgrade_preserves_existing_assignments(migrated_database: str) -> None:
    config = Config("alembic.ini")
    command.downgrade(config, "0003_market_data_schema")
    original = scalar(migrated_database, "SELECT valid_from FROM role_assignments LIMIT 1")
    command.upgrade(config, "head")
    assert scalar(migrated_database, "SELECT valid_from FROM role_assignments LIMIT 1") == original
    assert scalar(migrated_database, "SELECT status FROM role_assignments LIMIT 1") == "ACTIVE"


def test_failing_ddl_revision_rolls_back_only_that_revision(
    migrated_database: str, tmp_path: Path
) -> None:
    from sqlalchemy.exc import SQLAlchemyError

    location = tmp_path / "migrations"
    shutil.copytree("migrations", location)
    (location / "versions" / "0006_probe_failure.py").write_text(
        """
from alembic import op
import sqlalchemy as sa
revision = "0006_probe_failure"
down_revision = "0005_identity_admin_gaps"
branch_labels = None
depends_on = None
def upgrade():
    op.create_table("identity_failed_probe", sa.Column("id", sa.Integer()))
    op.execute("SELECT identity_function_that_does_not_exist()")
def downgrade():
    pass
""",
        encoding="utf-8",
    )
    config = Config("alembic.ini")
    config.set_main_option("script_location", str(location))
    with pytest.raises(SQLAlchemyError):
        command.upgrade(config, "head")
    assert (
        scalar(migrated_database, "SELECT version_num FROM alembic_version")
        == "0005_identity_admin_gaps"
    )
    assert scalar(migrated_database, "SELECT to_regclass('public.identity_failed_probe')") is None
