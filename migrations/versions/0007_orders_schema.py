"""MOD-03: immutable PostgreSQL DDL snapshot, orders and execution ledger.

RF-29–35, RFP-10. Provider prices retain precision; see design decision D8.
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_orders_schema"
down_revision = "0006_wallet_schema"
branch_labels = None
depends_on = None

STATEMENTS = (
    """
CREATE TABLE orders (
        id UUID NOT NULL,
        user_id UUID NOT NULL,
        alpaca_account_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        exchange TEXT NOT NULL,
        side TEXT NOT NULL,
        qty NUMERIC(20,  9) NOT NULL,
        type TEXT NOT NULL,
        order_class TEXT NOT NULL,
        time_in_force TEXT NOT NULL,
        reference_price NUMERIC NOT NULL,
        estimated_amount NUMERIC(20,  9) NOT NULL,
        status TEXT NOT NULL,
        client_order_id TEXT NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
        limit_price NUMERIC(18,  4),
        stop_price NUMERIC(18,  4),
        trail_price NUMERIC(18,  4),
        trail_percent NUMERIC(20,  9),
        take_profit_limit_price NUMERIC(18,  4),
        stop_loss_stop_price NUMERIC(18,  4),
        status_cause TEXT,
        provider_status TEXT,
        alpaca_order_id TEXT,
        filled_qty NUMERIC(20,  9) NOT NULL,
        filled_avg_price NUMERIC,
        fully_filled BOOLEAN NOT NULL,
        scheduled_for TIMESTAMP WITH TIME ZONE,
        scheduled_session_end TIMESTAMP WITH TIME ZONE,
        returned_for_changes BOOLEAN NOT NULL,
        submit_attempted_at TIMESTAMP WITH TIME ZONE,
        lookup_misses INTEGER NOT NULL,
        completed_at TIMESTAMP WITH TIME ZONE,
        broker_id UUID,
        broker_signed_at TIMESTAMP WITH TIME ZONE,
        schedule_if_closed BOOLEAN NOT NULL,
        PRIMARY KEY (id),
        CONSTRAINT ck_order_qty CHECK (qty > 0),
        CONSTRAINT ck_order_filled CHECK (filled_qty >= 0 AND filled_qty <= qty),
        CONSTRAINT ck_order_status CHECK (status IN ('PENDING', 'SUBMITTED', 'BROKER_SIGNED',
'EXECUTING', 'CANCELED', 'REJECTED', 'EXPIRED', 'IN_REVIEW', 'FAILED', 'HELD')),
        FOREIGN KEY(user_id) REFERENCES users (id),
        UNIQUE (client_order_id),
        UNIQUE (alpaca_order_id)
)
    """,
    """
CREATE INDEX ix_orders_open ON orders (status) WHERE status IN ('SUBMITTED', 'EXECUTING') AND
NOT fully_filled
    """,
    """
CREATE INDEX ix_orders_owner ON orders (user_id,  created_at DESC,  id)
    """,
    """
CREATE INDEX ix_orders_scheduled ON orders (status,  scheduled_for)
    """,
    """
ALTER TABLE "orders" ENABLE ROW LEVEL SECURITY
    """,
    """
CREATE TABLE order_legs (
        order_id UUID NOT NULL,
        role TEXT NOT NULL,
        alpaca_order_id TEXT,
        price NUMERIC(18,  4) NOT NULL,
        provider_status TEXT,
        PRIMARY KEY (order_id,  role),
        FOREIGN KEY(order_id) REFERENCES orders (id)
)
    """,
    """
ALTER TABLE "order_legs" ENABLE ROW LEVEL SECURITY
    """,
    """
CREATE TABLE order_events (
        id UUID NOT NULL,
        order_id UUID NOT NULL,
        from_status TEXT,
        to_status TEXT NOT NULL,
        cause TEXT NOT NULL,
        actor_type TEXT NOT NULL,
        actor_id UUID,
        at TIMESTAMP WITH TIME ZONE NOT NULL,
        metadata JSONB NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(order_id) REFERENCES orders (id)
)
    """,
    """
CREATE INDEX ix_order_events_at ON order_events (order_id,  at)
    """,
    """
ALTER TABLE "order_events" ENABLE ROW LEVEL SECURITY
    """,
    """
CREATE TABLE order_executions (
        alpaca_execution_id TEXT NOT NULL,
        order_id UUID NOT NULL,
        qty NUMERIC(20,  9) NOT NULL,
        price NUMERIC NOT NULL,
        executed_at TIMESTAMP WITH TIME ZONE NOT NULL,
        recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (alpaca_execution_id),
        CONSTRAINT ck_execution_qty CHECK (qty > 0),
        FOREIGN KEY(order_id) REFERENCES orders (id)
)
    """,
    """
ALTER TABLE "order_executions" ENABLE ROW LEVEL SECURITY
    """,
    """
CREATE TABLE order_reservations (
        order_id UUID NOT NULL,
        user_id UUID NOT NULL,
        kind TEXT NOT NULL,
        symbol TEXT NOT NULL,
        amount NUMERIC(20,  9) NOT NULL,
        status TEXT NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (order_id),
        CONSTRAINT ck_order_reservation_status CHECK (status IN ('active', 'transferred',
'released')),
        CONSTRAINT ck_order_reservation_kind CHECK (kind IN ('usd', 'shares')),
        CONSTRAINT ck_order_reservation_amount CHECK (amount >= 0),
        FOREIGN KEY(order_id) REFERENCES orders (id),
        FOREIGN KEY(user_id) REFERENCES users (id)
)
    """,
    """
CREATE INDEX ix_order_reservations_active ON order_reservations (user_id,  kind,  symbol) WHERE
status = 'active'
    """,
    """
ALTER TABLE "order_reservations" ENABLE ROW LEVEL SECURITY
    """,
    """
CREATE TABLE order_idempotency_keys (
        user_id UUID NOT NULL,
        idempotency_key TEXT NOT NULL,
        request_hash TEXT NOT NULL,
        order_id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (user_id,  idempotency_key),
        FOREIGN KEY(user_id) REFERENCES users (id),
        FOREIGN KEY(order_id) REFERENCES orders (id)
)
    """,
    """
ALTER TABLE "order_idempotency_keys" ENABLE ROW LEVEL SECURITY
    """,
    """
CREATE TABLE order_reauthorizations (
        id UUID NOT NULL,
        order_id UUID NOT NULL,
        previous_price NUMERIC NOT NULL,
        updated_price NUMERIC NOT NULL,
        deadline TIMESTAMP WITH TIME ZONE NOT NULL,
        decision TEXT,
        answered_at TIMESTAMP WITH TIME ZONE,
        resume_status TEXT NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(order_id) REFERENCES orders (id)
)
    """,
    """
CREATE UNIQUE INDEX ix_order_reauthorization_pending ON order_reauthorizations (order_id) WHERE
decision IS NULL
    """,
    """
ALTER TABLE "order_reauthorizations" ENABLE ROW LEVEL SECURITY
    """,
    """
CREATE TABLE order_cancel_requests (
        id UUID NOT NULL,
        order_id UUID NOT NULL,
        previous_status TEXT NOT NULL,
        reason TEXT NOT NULL,
        reason_text TEXT,
        confirmed BOOLEAN NOT NULL,
        requested_at TIMESTAMP WITH TIME ZONE NOT NULL,
        outcome TEXT NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(order_id) REFERENCES orders (id)
)
    """,
    """
CREATE INDEX ix_order_cancels ON order_cancel_requests (order_id)
    """,
    """
ALTER TABLE "order_cancel_requests" ENABLE ROW LEVEL SECURITY
    """,
    """
CREATE TABLE order_review_comments (
        id UUID NOT NULL,
        order_id UUID NOT NULL,
        broker_id UUID NOT NULL,
        comment TEXT NOT NULL,
        at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(order_id) REFERENCES orders (id),
        FOREIGN KEY(broker_id) REFERENCES users (id)
)
    """,
    """
CREATE INDEX ix_order_comments ON order_review_comments (order_id,  at)
    """,
    """
ALTER TABLE "order_review_comments" ENABLE ROW LEVEL SECURITY
    """,
    """
CREATE TABLE order_schedule_changes (
        change_id UUID NOT NULL,
        market_code TEXT NOT NULL,
        applied_at TIMESTAMP WITH TIME ZONE NOT NULL,
        affected_count INTEGER NOT NULL,
        PRIMARY KEY (change_id)
)
    """,
    """
ALTER TABLE "order_schedule_changes" ENABLE ROW LEVEL SECURITY
    """,
    """
CREATE TABLE order_activity_cursors (
        alpaca_account_id TEXT NOT NULL,
        last_activity_id TEXT,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (alpaca_account_id)
)
    """,
    """
ALTER TABLE "order_activity_cursors" ENABLE ROW LEVEL SECURITY
    """,
    """
INSERT INTO notification_preferences(user_id, event_type, channel, enabled) SELECT u.id,
e.event,  c.channel,  c.channel = 'in_app' FROM users u CROSS JOIN (VALUES ('order_executions'),
('order_updates')) e(event) CROSS JOIN (VALUES ('in_app'), ('email'), ('sms'), ('telegram'))
c(channel) ON CONFLICT DO NOTHING
    """,
)


def upgrade() -> None:
    op.drop_constraint(
        "notification_preferences_event_type_check", "notification_preferences", type_="check"
    )
    op.create_check_constraint(
        "notification_preferences_event_type_check",
        "notification_preferences",
        "event_type IN ('market_open','market_close','proposals','approval_requests',"
        "'price_changes','execution_confirmations','daily_summary','balance_changes',"
        "'order_executions','order_updates')",
    )
    for statement in STATEMENTS:
        op.execute(sa.text(statement))


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM notification_preferences "
            "WHERE event_type IN ('order_executions','order_updates')"
        )
    )
    op.drop_constraint(
        "notification_preferences_event_type_check", "notification_preferences", type_="check"
    )
    op.create_check_constraint(
        "notification_preferences_event_type_check",
        "notification_preferences",
        "event_type IN ('market_open','market_close','proposals','approval_requests',"
        "'price_changes','execution_confirmations','daily_summary','balance_changes')",
    )
    for name in (
        "order_activity_cursors",
        "order_schedule_changes",
        "order_review_comments",
        "order_cancel_requests",
        "order_reauthorizations",
        "order_idempotency_keys",
        "order_reservations",
        "order_executions",
        "order_events",
        "order_legs",
        "orders",
    ):
        op.drop_table(name)
