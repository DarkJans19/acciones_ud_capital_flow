"""MOD-01 schema, RBAC seed and private persistence (RF-01..09, RFP-01..03)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0001_identity_schema"
down_revision = None
branch_labels = None
depends_on = None


def uid(name: str = "id", *args: sa.ForeignKey, primary_key: bool = False) -> sa.Column[sa.Uuid]:
    return sa.Column(
        name,
        sa.Uuid(),
        *args,
        primary_key=primary_key,
        nullable=False,
        server_default=sa.text("gen_random_uuid()") if name == "id" else None,
    )


def timestamp(name: str, *, nullable: bool = True, default: bool = False) -> sa.Column[sa.DateTime]:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=nullable,
        server_default=sa.text("now()") if default else None,
    )


def user_fk(*, primary_key: bool = False) -> sa.Column[sa.Uuid]:
    return uid("user_id", sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=primary_key)


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.CheckConstraint("code in ('investor','broker','administrator')"),
    )
    op.create_table(
        "permissions",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column("description", sa.Text(), nullable=False),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_code", sa.Text(), sa.ForeignKey("roles.code"), primary_key=True),
        sa.Column(
            "permission_code", sa.Text(), sa.ForeignKey("permissions.code"), primary_key=True
        ),
    )
    op.create_table(
        "users",
        uid(primary_key=True),
        *[
            sa.Column(n, sa.Text(), nullable=False)
            for n in (
                "first_names",
                "last_names",
                "email",
                "email_normalized",
                "phone",
                "password_hash",
            )
        ],
        sa.Column("country", sa.CHAR(2), nullable=False),
        sa.Column("account_status", sa.Text(), nullable=False, server_default="active"),
        timestamp("terms_accepted_at", nullable=False),
        sa.Column("monthly_report", sa.Boolean(), nullable=False),
        *[
            sa.Column(n, sa.Boolean(), nullable=False, server_default=sa.false())
            for n in ("broker_requested", "premium_requested", "is_premium")
        ],
        sa.Column("investor_level", sa.Text()),
        sa.Column("interests", pg.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        *[
            sa.Column(n, sa.Text())
            for n in ("firm_name", "license_number", "telegram_chat_id", "totp_secret_enc")
        ],
        timestamp("totp_confirmed_at"),
        sa.Column("totp_last_step", sa.BigInteger()),
        timestamp("created_at", nullable=False, default=True),
        timestamp("updated_at", nullable=False, default=True),
        sa.UniqueConstraint("email_normalized", name="uq_users_email_normalized"),
        sa.CheckConstraint("password_hash like '$argon2id$%'"),
        sa.CheckConstraint("account_status in ('active','pending_broker_activation')"),
        sa.CheckConstraint("investor_level in ('beginner','experienced')"),
    )
    op.create_table(
        "role_assignments",
        uid(primary_key=True),
        user_fk(),
        sa.Column("role_code", sa.Text(), sa.ForeignKey("roles.code"), nullable=False),
        timestamp("valid_from", nullable=False),
        timestamp("valid_to"),
        timestamp("created_at", default=True),
        sa.CheckConstraint("valid_to is null or valid_to > valid_from"),
    )
    op.create_index("ix_role_assignments_user", "role_assignments", ["user_id"])
    op.create_index("ix_role_assignments_role", "role_assignments", ["role_code"])
    op.create_table(
        "mfa_challenges",
        uid(primary_key=True),
        user_fk(),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False, unique=True),
        timestamp("expires_at", nullable=False),
        timestamp("used_at"),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        timestamp("invalidated_at"),
        timestamp("created_at", default=True),
    )
    op.create_table(
        "mfa_recovery_codes",
        uid(primary_key=True),
        user_fk(),
        uid("set_id"),
        sa.Column("code_hash", sa.Text(), nullable=False),
        timestamp("used_at"),
        timestamp("invalidated_at"),
        timestamp("created_at", nullable=False, default=True),
        sa.CheckConstraint("code_hash like '$argon2id$%'"),
    )
    op.create_index(
        "ix_recovery_unused",
        "mfa_recovery_codes",
        ["user_id"],
        postgresql_where=sa.text("used_at is null and invalidated_at is null"),
    )
    op.create_table(
        "sessions",
        uid(primary_key=True),
        user_fk(),
        sa.Column("user_agent", sa.String(512), nullable=False),
        sa.Column("ip_address", sa.Text(), nullable=False),
        timestamp("created_at", default=True),
        timestamp("last_used_at", nullable=False),
        timestamp("revoked_at"),
    )
    op.create_index(
        "ix_sessions_active",
        "sessions",
        ["user_id"],
        postgresql_where=sa.text("revoked_at is null"),
    )
    op.create_table(
        "refresh_tokens",
        uid(primary_key=True),
        uid("session_id", sa.ForeignKey("sessions.id", ondelete="CASCADE")),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False, unique=True),
        timestamp("expires_at", nullable=False),
        timestamp("rotated_at"),
        timestamp("created_at", default=True),
    )
    op.create_table(
        "auth_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("kind", sa.Text()),
        timestamp("occurred_at", nullable=False, default=True),
        sa.Column("ip_address", sa.Text()),
        sa.Column("user_agent", sa.String(512)),
        sa.Column("method", sa.Text()),
        sa.Column("result", sa.Text(), nullable=False),
        sa.CheckConstraint("kind in ('login','mfa_verify')"),
        sa.CheckConstraint("method in ('totp','recovery_code')"),
        sa.CheckConstraint(
            "result in ('success','unknown_email','wrong_password',"
            "'invalid_totp','replayed_totp','invalid_recovery_code',"
            "'expired_challenge','invalid_challenge',"
            "'attempt_limit_exceeded')"
        ),
    )
    op.create_table(
        "notification_preferences",
        user_fk(primary_key=True),
        sa.Column("event_type", sa.Text(), primary_key=True),
        sa.Column("channel", sa.Text(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "event_type in ('market_open','market_close','proposals',"
            "'approval_requests','price_changes',"
            "'execution_confirmations','daily_summary')"
        ),
        sa.CheckConstraint("channel in ('in_app','email','sms','telegram')"),
        sa.CheckConstraint("channel <> 'in_app' or enabled"),
    )
    op.create_table(
        "portfolio_view_settings",
        user_fk(primary_key=True),
        sa.Column("view_type", sa.Text(), nullable=False),
        sa.Column("sort_by", sa.Text(), nullable=False),
        sa.Column("sort_direction", sa.Text(), nullable=False),
        sa.Column("hide_threshold", sa.Numeric(11, 2), nullable=False),
        timestamp("updated_at", nullable=False, default=True),
        sa.CheckConstraint("view_type in ('table','cards','chart')"),
        sa.CheckConstraint("sort_by in ('symbol','market_value','gain_loss','allocation')"),
        sa.CheckConstraint("sort_direction in ('asc','desc')"),
        sa.CheckConstraint("hide_threshold between 0 and 999999999.99"),
    )
    op.create_table(
        "order_controls",
        user_fk(primary_key=True),
        sa.Column("default_order_type", sa.Text(), nullable=False),
        sa.Column("daily_order_limit", sa.Integer(), nullable=False),
        sa.Column("high_order_threshold_usd", sa.Numeric(11, 2), nullable=False),
        sa.Column("extra_confirmation", sa.Boolean(), nullable=False),
        timestamp("updated_at", nullable=False, default=True),
        sa.CheckConstraint(
            "default_order_type in ('market','limit','stop','stop_limit','trailing_stop')"
        ),
        sa.CheckConstraint("daily_order_limit between 1 and 1000"),
        sa.CheckConstraint(
            "high_order_threshold_usd > 0 and high_order_threshold_usd <= 999999999.99"
        ),
    )
    op.create_table(
        "kyc_accounts",
        user_fk(primary_key=True),
        sa.Column("alpaca_account_id", sa.Text(), unique=True),
        sa.Column("status", sa.Text()),
        timestamp("status_updated_at"),
        sa.Column("tax_id_last4", sa.String(4)),
        timestamp("reserved_at", nullable=False, default=True),
        timestamp("created_at", default=True),
    )
    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text("ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY"))
    roles = sa.table("roles", sa.column("code", sa.Text()), sa.column("name", sa.Text()))
    op.bulk_insert(
        roles, [{"code": r, "name": r.title()} for r in ("investor", "broker", "administrator")]
    )
    permissions = (
        "account:manage",
        "market:read",
        "watchlist:manage",
        "kyc:submit",
        "admin:users",
        "admin:rbac",
        "admin:markets",
    )
    op.bulk_insert(
        sa.table("permissions", sa.column("code", sa.Text()), sa.column("description", sa.Text())),
        [{"code": p, "description": p} for p in permissions],
    )
    pairs = [
        {"role_code": role, "permission_code": p}
        for role in ("investor", "broker", "administrator")
        for p in permissions
        if (
            p in permissions[:3]
            or (p == "kyc:submit" and role == "investor")
            or (p.startswith("admin:") and role == "administrator")
        )
    ]
    op.bulk_insert(
        sa.table(
            "role_permissions",
            sa.column("role_code", sa.Text()),
            sa.column("permission_code", sa.Text()),
        ),
        pairs,
    )


TABLES = (
    "roles",
    "permissions",
    "role_permissions",
    "users",
    "role_assignments",
    "mfa_challenges",
    "mfa_recovery_codes",
    "sessions",
    "refresh_tokens",
    "auth_events",
    "notification_preferences",
    "portfolio_view_settings",
    "order_controls",
    "kyc_accounts",
)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
