"""Core query declarations only. Alembic exclusively owns the database schema."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

metadata = sa.MetaData()

markets = sa.Table(
    "markets",
    metadata,
    sa.Column("code", sa.Text(), primary_key=True),
    sa.Column("name", sa.Text()),
    sa.Column("timezone", sa.Text()),
    sa.Column("default_open_time", sa.Time()),
    sa.Column("default_close_time", sa.Time()),
)

schedule_overrides = sa.Table(
    "schedule_overrides",
    metadata,
    sa.Column("id", sa.Uuid()),
    sa.Column("market_code", sa.Text()),
    sa.Column("date", sa.Date()),
    sa.Column("closed", sa.Boolean()),
    sa.Column("open_time", sa.Time()),
    sa.Column("close_time", sa.Time()),
)

instruments = sa.Table(
    "instruments",
    metadata,
    sa.Column("symbol", sa.Text(), primary_key=True),
    sa.Column("alpaca_asset_id", sa.Uuid()),
    *[sa.Column(name, sa.Text()) for name in ("name", "exchange", "asset_class", "status")],
    *[
        sa.Column(name, sa.Boolean())
        for name in ("tradable", "marginable", "shortable", "easy_to_borrow", "fractionable")
    ],
    sa.Column("sector", sa.Text()),
    sa.Column("listed", sa.Boolean()),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)

catalog_state = sa.Table(
    "catalog_state",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("last_reload_at", sa.DateTime(timezone=True)),
)

instrument_snapshots = sa.Table(
    "instrument_snapshots",
    metadata,
    sa.Column("symbol", sa.Text(), primary_key=True),
    *[
        sa.Column(name, sa.Numeric(18, 6))
        for name in ("last_trade_price", "bid_price", "ask_price")
    ],
    *[sa.Column(name, sa.BigInteger()) for name in ("bid_size", "ask_size", "daily_volume")],
    sa.Column("quote_updated_at", sa.DateTime(timezone=True)),
    sa.Column("feed", sa.Text()),
    sa.Column("retrieved_at", sa.DateTime(timezone=True)),
)

market_clock_state = sa.Table(
    "market_clock_state",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("is_open", sa.Boolean()),
    sa.Column("observed_at", sa.DateTime(timezone=True)),
)

watchlists = sa.Table(
    "watchlists",
    metadata,
    sa.Column("id", sa.Uuid()),
    sa.Column("user_id", sa.Uuid()),
    sa.Column("name", sa.Text()),
    sa.Column("created_at", sa.DateTime(timezone=True)),
)

watchlist_items = sa.Table(
    "watchlist_items",
    metadata,
    sa.Column("watchlist_id", sa.Uuid()),
    sa.Column("symbol", sa.Text()),
    sa.Column("added_at", sa.DateTime(timezone=True)),
)

price_alerts = sa.Table(
    "price_alerts",
    metadata,
    sa.Column("id", sa.Uuid()),
    sa.Column("user_id", sa.Uuid()),
    sa.Column("symbol", sa.Text()),
    sa.Column("comparator", sa.Text()),
    sa.Column("threshold", sa.Numeric(18, 6)),
    sa.Column("status", sa.Text()),
    sa.Column("last_evaluated_price", sa.Numeric(18, 6)),
    sa.Column("triggered_at", sa.DateTime(timezone=True)),
    sa.Column("created_at", sa.DateTime(timezone=True)),
)

notifications = sa.Table(
    "notifications",
    metadata,
    sa.Column("id", sa.Uuid()),
    sa.Column("user_id", sa.Uuid()),
    sa.Column("event_type", sa.Text()),
    sa.Column("payload", JSONB()),
    sa.Column("created_at", sa.DateTime(timezone=True)),
)

notification_deliveries = sa.Table(
    "notification_deliveries",
    metadata,
    sa.Column("notification_id", sa.Uuid()),
    sa.Column("channel", sa.Text()),
    sa.Column("status", sa.Text()),
    sa.Column("attempted_at", sa.DateTime(timezone=True)),
    sa.Column("error_code", sa.Text()),
)
