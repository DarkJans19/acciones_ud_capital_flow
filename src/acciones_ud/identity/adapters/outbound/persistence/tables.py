"""Core query declarations only. Alembic exclusively owns the database schema."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

metadata = sa.MetaData()


users = sa.Table(
    "users",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    *[
        sa.Column(n, sa.Text())
        for n in (
            "first_names",
            "last_names",
            "email",
            "email_normalized",
            "phone",
            "country",
            "password_hash",
            "account_status",
            "investor_level",
            "firm_name",
            "license_number",
            "telegram_chat_id",
            "totp_secret_enc",
        )
    ],
    *[
        sa.Column(n, sa.Boolean())
        for n in ("monthly_report", "broker_requested", "premium_requested", "is_premium")
    ],
    sa.Column("interests", ARRAY(sa.Text())),
    sa.Column("totp_last_step", sa.BigInteger()),
    *[
        sa.Column(n, sa.DateTime(timezone=True))
        for n in ("terms_accepted_at", "totp_confirmed_at", "created_at", "updated_at")
    ],
)
roles = sa.Table("roles", metadata, sa.Column("code", sa.Text()), sa.Column("name", sa.Text()))
permissions = sa.Table(
    "permissions", metadata, sa.Column("code", sa.Text()), sa.Column("description", sa.Text())
)
role_permissions = sa.Table(
    "role_permissions",
    metadata,
    sa.Column("role_code", sa.Text()),
    sa.Column("permission_code", sa.Text()),
)
role_assignments = sa.Table(
    "role_assignments",
    metadata,
    sa.Column("id", sa.Uuid()),
    sa.Column("user_id", sa.Uuid()),
    sa.Column("role_code", sa.Text()),
    sa.Column("status", sa.Text()),
    sa.Column("cancelled_at", sa.DateTime(timezone=True)),
    sa.Column("cancelled_by", sa.Uuid()),
    *[sa.Column(n, sa.DateTime(timezone=True)) for n in ("valid_from", "valid_to", "created_at")],
)
notification_preferences = sa.Table(
    "notification_preferences",
    metadata,
    sa.Column("user_id", sa.Uuid()),
    sa.Column("event_type", sa.Text()),
    sa.Column("channel", sa.Text()),
    sa.Column("enabled", sa.Boolean()),
)
sessions = sa.Table(
    "sessions",
    metadata,
    sa.Column("id", sa.Uuid()),
    sa.Column("user_id", sa.Uuid()),
    sa.Column("user_agent", sa.Text()),
    sa.Column("ip_address", sa.Text()),
    *[
        sa.Column(n, sa.DateTime(timezone=True))
        for n in ("created_at", "last_used_at", "revoked_at")
    ],
)
refresh_tokens = sa.Table(
    "refresh_tokens",
    metadata,
    sa.Column("id", sa.Uuid()),
    sa.Column("session_id", sa.Uuid()),
    sa.Column("token_hash", sa.LargeBinary()),
    *[sa.Column(n, sa.DateTime(timezone=True)) for n in ("expires_at", "rotated_at", "created_at")],
)
mfa_challenges = sa.Table(
    "mfa_challenges",
    metadata,
    sa.Column("id", sa.Uuid()),
    sa.Column("user_id", sa.Uuid()),
    sa.Column("token_hash", sa.LargeBinary()),
    sa.Column("failed_attempts", sa.Integer()),
    *[
        sa.Column(n, sa.DateTime(timezone=True))
        for n in ("expires_at", "used_at", "invalidated_at", "created_at")
    ],
)
mfa_recovery_codes = sa.Table(
    "mfa_recovery_codes",
    metadata,
    sa.Column("id", sa.Uuid()),
    sa.Column("user_id", sa.Uuid()),
    sa.Column("set_id", sa.Uuid()),
    sa.Column("code_hash", sa.Text()),
    *[
        sa.Column(n, sa.DateTime(timezone=True))
        for n in ("used_at", "invalidated_at", "created_at")
    ],
)
auth_events = sa.Table(
    "auth_events",
    metadata,
    sa.Column("id", sa.BigInteger()),
    sa.Column("user_id", sa.Uuid()),
    *[sa.Column(n, sa.Text()) for n in ("kind", "ip_address", "user_agent", "method", "result")],
    sa.Column("occurred_at", sa.DateTime(timezone=True)),
)
portfolio_view_settings = sa.Table(
    "portfolio_view_settings",
    metadata,
    sa.Column("user_id", sa.Uuid()),
    *[sa.Column(n, sa.Text()) for n in ("view_type", "sort_by", "sort_direction")],
    sa.Column("hide_threshold", sa.Numeric(11, 2)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)
order_controls = sa.Table(
    "order_controls",
    metadata,
    sa.Column("user_id", sa.Uuid()),
    sa.Column("default_order_type", sa.Text()),
    sa.Column("daily_order_limit", sa.Integer()),
    sa.Column("high_order_threshold_usd", sa.Numeric(11, 2)),
    sa.Column("extra_confirmation", sa.Boolean()),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)
kyc_accounts = sa.Table(
    "kyc_accounts",
    metadata,
    sa.Column("user_id", sa.Uuid()),
    *[sa.Column(n, sa.Text()) for n in ("alpaca_account_id", "status", "tax_id_last4")],
    *[
        sa.Column(n, sa.DateTime(timezone=True))
        for n in ("status_updated_at", "reserved_at", "created_at")
    ],
)
