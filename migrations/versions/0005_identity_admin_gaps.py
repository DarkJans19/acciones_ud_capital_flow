"""MOD-01: KYC status cache column, admin user directory index and audit log (R20-R25).

Additive upgrade: no existing row is rewritten and no column is dropped. The audit
log is append-only enforced by a trigger, so a downgrade loses audit history.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0005_identity_admin_gaps"
down_revision = "0004_assignment_cancellation"
branch_labels = None
depends_on = None

# Requirement 25.1 enumerates these action codes. Revoked and cancelled are
# distinct actions, so the Migration_Set stores exactly the listed set.
ACTIONS = (
    "administrator_created",
    "broker_activated",
    "premium_changed",
    "role_assignment_created",
    "role_assignment_updated",
    "role_assignment_revoked",
    "role_assignment_cancelled",
    "role_permission_added",
    "role_permission_removed",
    "kyc_reconciled",
)


def upgrade() -> None:
    op.add_column("kyc_accounts", sa.Column("status_checked_at", sa.DateTime(timezone=True)))
    op.create_table(
        "admin_audit_log",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=False),
        sa.Column("payload", pg.JSONB(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "action in (" + ",".join(f"'{action}'" for action in ACTIONS) + ")",
            name="ck_admin_audit_action",
        ),
        sa.CheckConstraint(
            "target_type in ('user','role')", name="ck_admin_audit_target_type"
        ),
        sa.CheckConstraint(
            "char_length(target_id) between 1 and 100", name="ck_admin_audit_target_id"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object'", name="ck_admin_audit_payload"
        ),
    )
    op.create_index(
        "ix_admin_audit_log_occurred",
        "admin_audit_log",
        [sa.text("occurred_at desc"), sa.text("id desc")],
    )
    op.create_index(
        "ix_admin_audit_log_actor", "admin_audit_log", ["actor_user_id"]
    )
    op.create_index(
        "ix_admin_audit_log_target", "admin_audit_log", ["target_type", "target_id"]
    )
    op.create_index("ix_admin_audit_log_action", "admin_audit_log", ["action"])
    op.create_index(
        "ix_users_created_at_id",
        "users",
        [sa.text("created_at desc"), sa.text("id asc")],
    )
    op.execute(sa.text('ALTER TABLE "admin_audit_log" ENABLE ROW LEVEL SECURITY'))
    op.execute(
        sa.text(
            "CREATE FUNCTION admin_audit_log_immutable() RETURNS trigger AS $$ "
            "BEGIN RAISE EXCEPTION 'admin_audit_log is append-only'; END; "
            "$$ LANGUAGE plpgsql"
        )
    )
    op.execute(
        sa.text(
            "CREATE TRIGGER trg_admin_audit_log_immutable "
            "BEFORE UPDATE OR DELETE ON admin_audit_log "
            "FOR EACH ROW EXECUTE FUNCTION admin_audit_log_immutable()"
        )
    )


def downgrade() -> None:
    # Intended only for disposable DBs: audit history would be lost on downgrade.
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_admin_audit_log_immutable ON admin_audit_log"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS admin_audit_log_immutable()"))
    op.drop_index("ix_users_created_at_id", table_name="users")
    op.drop_index("ix_admin_audit_log_action", table_name="admin_audit_log")
    op.drop_index("ix_admin_audit_log_target", table_name="admin_audit_log")
    op.drop_index("ix_admin_audit_log_actor", table_name="admin_audit_log")
    op.drop_index("ix_admin_audit_log_occurred", table_name="admin_audit_log")
    op.drop_table("admin_audit_log")
    op.drop_column("kyc_accounts", "status_checked_at")
