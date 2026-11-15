import sqlalchemy as sa

from acciones_ud.identity.adapters.outbound.persistence.tables import users
from acciones_ud.shared.infrastructure.entity_repository import entity_table
from acciones_ud.wallet.domain.model import (
    ActivityCursor,
    BankRelationship,
    IdempotencyEntry,
    NotificationMarker,
    Payment,
    StripeEvent,
    Subscription,
    Transfer,
)

metadata = sa.MetaData()
users.to_metadata(metadata)
banks = entity_table(
    metadata,
    "wallet_bank_relationships",
    BankRelationship,
    ("id",),
    unique=("alpaca_relationship_id",),
    references={"user_id": "users.id"},
)
transfers = entity_table(
    metadata,
    "wallet_transfers",
    Transfer,
    ("id",),
    unique=("alpaca_transfer_id",),
    references={"user_id": "users.id", "bank_relationship_id": "wallet_bank_relationships.id"},
    constraints=(
        sa.CheckConstraint("amount >= 1", name="ck_wallet_amount"),
        sa.CheckConstraint("direction IN ('INCOMING','OUTGOING')", name="ck_wallet_direction"),
    ),
)
keys = entity_table(
    metadata, "wallet_idempotency_keys", IdempotencyEntry, ("user_id", "idempotency_key")
)
subscriptions = entity_table(
    metadata,
    "subscriptions",
    Subscription,
    ("id",),
    unique=("stripe_checkout_session_id", "stripe_subscription_id"),
    references={"user_id": "users.id"},
    constraints=(sa.CheckConstraint("plan IN ('monthly','annual')", name="ck_subscription_plan"),),
)
payments = entity_table(
    metadata,
    "subscription_payments",
    Payment,
    ("id",),
    unique=("stripe_invoice_id",),
    references={"user_id": "users.id", "subscription_id": "subscriptions.id"},
)
events = entity_table(metadata, "stripe_events", StripeEvent, ("event_id",))
markers = entity_table(
    metadata, "wallet_balance_notifications", NotificationMarker, ("source", "external_id")
)
cursors = entity_table(metadata, "wallet_activity_cursors", ActivityCursor, ("alpaca_account_id",))
sa.Index(
    "ix_wallet_transfers_owner", transfers.c.user_id, transfers.c.created_at.desc(), transfers.c.id
)
sa.Index(
    "ix_wallet_transfers_open",
    transfers.c.status,
    postgresql_where=transfers.c.status.not_in(["COMPLETE", "CANCELED", "RETURNED", "REJECTED"]),
)
sa.Index(
    "ix_subscription_current",
    subscriptions.c.user_id,
    unique=True,
    postgresql_where=subscriptions.c.status.in_(["active", "trialing", "past_due"]),
)

# Match the immutable Alembic schema, including infrastructure audit timestamps.
for table in (transfers, payments):
    table.c.amount.type = sa.Numeric(14, 2)
    table.c.currency.type = sa.String(3)
banks.c.account_last4.type = sa.String(4)
keys.c.idempotency_key.type = sa.String(128)
keys.c.request_hash.type = sa.String(64)
keys.c.user_id.append_foreign_key(sa.ForeignKey("users.id"))
keys.c.transfer_id.append_foreign_key(sa.ForeignKey("wallet_transfers.id"))
keys.append_constraint(
    sa.CheckConstraint("state IN ('in_progress','completed')", name="ck_wallet_key_state")
)
markers.c.user_id.append_foreign_key(sa.ForeignKey("users.id"))
markers.append_constraint(
    sa.CheckConstraint("source IN ('transfer','activity')", name="ck_wallet_marker_source")
)
for table in (banks, transfers, subscriptions):
    table.append_column(
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        )
    )
subscriptions.append_column(
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
)
