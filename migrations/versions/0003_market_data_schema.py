"""Shared catalog infrastructure required by Identity interests (RFP-08).

No Market Data endpoint, use case or background job is introduced here.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003_market_data_schema"
down_revision = "0002_initial_admin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "markets",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False, server_default="America/New_York"),
        sa.Column("default_open_time", sa.Time()),
        sa.Column("default_close_time", sa.Time()),
        sa.CheckConstraint("(default_open_time is null) = (default_close_time is null)"),
        sa.CheckConstraint("default_close_time > default_open_time"),
    )
    op.create_table(
        "schedule_overrides",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "market_code",
            sa.Text(),
            sa.ForeignKey("markets.code", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("closed", sa.Boolean(), nullable=False),
        sa.Column("open_time", sa.Time()),
        sa.Column("close_time", sa.Time()),
        sa.UniqueConstraint("market_code", "date"),
        sa.CheckConstraint(
            "(closed and open_time is null and close_time is null) or "
            "(not closed and open_time is not null and close_time is not null "
            "and close_time > open_time)"
        ),
    )
    op.create_table(
        "instruments",
        sa.Column("symbol", sa.Text(), primary_key=True),
        sa.Column("alpaca_asset_id", sa.Uuid()),
        *[
            sa.Column(n, sa.Text(), nullable=False)
            for n in ("name", "exchange", "asset_class", "status")
        ],
        *[
            sa.Column(n, sa.Boolean())
            for n in ("tradable", "marginable", "shortable", "easy_to_borrow", "fractionable")
        ],
        sa.Column("sector", sa.Text()),
        sa.Column("listed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("symbol = upper(symbol)"),
        sa.CheckConstraint("status in ('active','inactive')"),
    )
    op.create_index("ix_instruments_exchange", "instruments", ["exchange"])
    op.execute("CREATE INDEX ix_instruments_name ON instruments (lower(name) text_pattern_ops)")
    op.create_table(
        "catalog_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("last_reload_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("id = 1"),
    )
    op.create_table(
        "instrument_snapshots",
        sa.Column("symbol", sa.Text(), sa.ForeignKey("instruments.symbol"), primary_key=True),
        *[sa.Column(n, sa.Numeric(18, 6)) for n in ("last_trade_price", "bid_price", "ask_price")],
        *[sa.Column(n, sa.BigInteger()) for n in ("bid_size", "ask_size", "daily_volume")],
        sa.Column("quote_updated_at", sa.DateTime(timezone=True)),
        sa.Column("feed", sa.Text(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("feed in ('iex','sip','delayed_sip')"),
    )
    op.create_table(
        "market_clock_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("is_open", sa.Boolean()),
        sa.Column("observed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("id = 1"),
    )
    op.create_table(
        "watchlists",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("char_length(name) between 1 and 100"),
    )
    op.create_table(
        "watchlist_items",
        sa.Column(
            "watchlist_id",
            sa.Uuid(),
            sa.ForeignKey("watchlists.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("symbol", sa.Text(), sa.ForeignKey("instruments.symbol"), primary_key=True),
        sa.Column("added_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "price_alerts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("symbol", sa.Text(), sa.ForeignKey("instruments.symbol"), nullable=False),
        sa.Column("comparator", sa.Text(), nullable=False),
        sa.Column("threshold", sa.Numeric(18, 6), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("last_evaluated_price", sa.Numeric(18, 6)),
        sa.Column("triggered_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("comparator in ('above','below','crosses')"),
        sa.CheckConstraint("threshold > 0 and threshold <= 999999999.99"),
        sa.CheckConstraint("status in ('active','inactive','triggered')"),
    )
    op.create_index(
        "ix_price_alerts_active",
        "price_alerts",
        ["status"],
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "event_type in ('market_open','market_close','proposals','approval_requests',"
            "'price_changes','execution_confirmations','daily_summary')"
        ),
    )
    op.execute(
        "CREATE INDEX ix_notifications_user_created ON notifications (user_id, created_at DESC)"
    )
    op.create_table(
        "notification_deliveries",
        sa.Column(
            "notification_id",
            sa.Uuid(),
            sa.ForeignKey("notifications.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("channel", sa.Text(), primary_key=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.Text()),
        sa.CheckConstraint("channel in ('in_app','email','sms','telegram')"),
        sa.CheckConstraint("status in ('pending','sent','failed')"),
    )
    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    op.bulk_insert(
        sa.table("markets", sa.column("code", sa.Text()), sa.column("name", sa.Text())),
        [
            {"code": code, "name": name}
            for code, name in (
                ("AMEX", "NYSE American"),
                ("ARCA", "NYSE Arca"),
                ("BATS", "Cboe BZX"),
                ("NYSE", "New York Stock Exchange"),
                ("NASDAQ", "Nasdaq"),
                ("NYSEARCA", "NYSE Arca"),
                ("OTC", "Over the counter"),
            )
        ],
    )
    for table in ("catalog_state", "market_clock_state"):
        op.execute(sa.text(f"INSERT INTO {table} (id) VALUES (1)"))


TABLES = (
    "markets",
    "schedule_overrides",
    "instruments",
    "catalog_state",
    "instrument_snapshots",
    "market_clock_state",
    "watchlists",
    "watchlist_items",
    "price_alerts",
    "notifications",
    "notification_deliveries",
)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
