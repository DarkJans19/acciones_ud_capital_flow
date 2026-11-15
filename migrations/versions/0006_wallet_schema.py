"""MOD-04: sandbox funding, subscriptions and notification preferences."""

import sqlalchemy as sa
from alembic import op

revision = "0006_wallet_schema"
down_revision = "0005_identity_admin_gaps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wallet_bank_relationships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("alpaca_account_id", sa.Text(), nullable=False),
        sa.Column("alpaca_relationship_id", sa.Text(), nullable=False, unique=True),
        sa.Column("owner_name", sa.Text(), nullable=False),
        sa.Column("account_type", sa.Text(), nullable=False),
        sa.Column("account_last4", sa.String(4), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "wallet_transfers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("alpaca_account_id", sa.Text(), nullable=False),
        sa.Column("alpaca_transfer_id", sa.Text(), nullable=False, unique=True),
        sa.Column(
            "bank_relationship_id",
            sa.Uuid(),
            sa.ForeignKey("wallet_bank_relationships.id"),
            nullable=False,
        ),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("alpaca_updated_at", sa.DateTime(timezone=True)),
        sa.Column("last_confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount >= 1", name="ck_wallet_amount"),
        sa.CheckConstraint("direction IN ('INCOMING','OUTGOING')", name="ck_wallet_direction"),
    )
    op.create_index(
        "ix_wallet_transfers_owner",
        "wallet_transfers",
        ["user_id", sa.text("created_at DESC"), "id"],
    )
    op.create_index(
        "ix_wallet_transfers_open",
        "wallet_transfers",
        ["status"],
        postgresql_where=sa.text("status NOT IN ('COMPLETE','CANCELED','RETURNED','REJECTED')"),
    )
    op.create_table(
        "wallet_idempotency_keys",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("idempotency_key", sa.String(128), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("transfer_id", sa.Uuid(), sa.ForeignKey("wallet_transfers.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("state IN ('in_progress','completed')", name="ck_wallet_key_state"),
    )
    op.create_table(
        "wallet_activity_cursors",
        sa.Column("alpaca_account_id", sa.Text(), primary_key=True),
        sa.Column("last_activity_id", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "wallet_balance_notifications",
        sa.Column("source", sa.Text(), primary_key=True),
        sa.Column("external_id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("source IN ('transfer','activity')", name="ck_wallet_marker_source"),
    )
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("plan", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("stripe_checkout_session_id", sa.Text(), nullable=False, unique=True),
        sa.Column("stripe_subscription_id", sa.Text(), unique=True),
        sa.Column("stripe_customer_id", sa.Text()),
        sa.Column("current_period_start", sa.DateTime(timezone=True)),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False),
        sa.Column("cancel_reason", sa.Text()),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True)),
        sa.Column("stripe_event_created_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("plan IN ('monthly','annual')", name="ck_subscription_plan"),
    )
    op.create_index(
        "ix_subscription_current",
        "subscriptions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('active','trialing','past_due')"),
    )
    op.create_table(
        "subscription_payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), sa.ForeignKey("subscriptions.id"), nullable=False),
        sa.Column("stripe_invoice_id", sa.Text(), nullable=False, unique=True),
        sa.Column("plan", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True)),
        sa.Column("period_end", sa.DateTime(timezone=True)),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "stripe_events",
        sa.Column("event_id", sa.Text(), primary_key=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    )
    for name in ("wallet_bank_relationships", "wallet_transfers", "subscriptions"):
        op.add_column(
            name,
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
    op.add_column(
        "subscriptions",
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    # Confirmed in task 1.2: preferences are persisted as one row per channel.
    op.execute(
        sa.text(
            "INSERT INTO notification_preferences(user_id,event_type,channel,enabled) "
            "SELECT u.id, 'balance_changes', c.channel, c.channel = 'in_app' FROM users u "
            "CROSS JOIN (VALUES ('in_app'),('email'),('sms'),('telegram')) c(channel) "
            "ON CONFLICT DO NOTHING"
        )
    )
    for name in (
        "wallet_bank_relationships",
        "wallet_transfers",
        "wallet_idempotency_keys",
        "wallet_activity_cursors",
        "wallet_balance_notifications",
        "subscriptions",
        "subscription_payments",
        "stripe_events",
    ):
        op.execute(sa.text(f'ALTER TABLE "{name}" ENABLE ROW LEVEL SECURITY'))


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM notification_preferences WHERE event_type='balance_changes'"))
    for name in (
        "stripe_events",
        "subscription_payments",
        "subscriptions",
        "wallet_balance_notifications",
        "wallet_activity_cursors",
        "wallet_idempotency_keys",
        "wallet_transfers",
        "wallet_bank_relationships",
    ):
        op.drop_table(name)
