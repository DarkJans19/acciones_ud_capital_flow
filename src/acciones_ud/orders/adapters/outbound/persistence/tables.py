import sqlalchemy as sa

from acciones_ud.identity.adapters.outbound.persistence.tables import users
from acciones_ud.orders.domain import model as m
from acciones_ud.shared.infrastructure.entity_repository import entity_table

metadata = sa.MetaData()
users.to_metadata(metadata)
orders = entity_table(
    metadata,
    "orders",
    m.Order,
    ("id",),
    unique=("client_order_id", "alpaca_order_id"),
    references={"user_id": "users.id"},
    constraints=(
        sa.CheckConstraint("qty > 0", name="ck_order_qty"),
        sa.CheckConstraint("filled_qty >= 0 AND filled_qty <= qty", name="ck_order_filled"),
        sa.CheckConstraint(
            "status IN ('PENDING','SUBMITTED','BROKER_SIGNED','EXECUTING',"
            "'CANCELED','REJECTED','EXPIRED','IN_REVIEW','FAILED','HELD')",
            name="ck_order_status",
        ),
    ),
)
legs = entity_table(
    metadata, "order_legs", m.OrderLeg, ("order_id", "role"), references={"order_id": "orders.id"}
)
events = entity_table(
    metadata, "order_events", m.OrderEvent, ("id",), references={"order_id": "orders.id"}
)
executions = entity_table(
    metadata,
    "order_executions",
    m.Execution,
    ("alpaca_execution_id",),
    references={"order_id": "orders.id"},
    constraints=(sa.CheckConstraint("qty > 0", name="ck_execution_qty"),),
)
reservations = entity_table(
    metadata,
    "order_reservations",
    m.Reservation,
    ("order_id",),
    references={"order_id": "orders.id", "user_id": "users.id"},
    constraints=(
        sa.CheckConstraint(
            "status IN ('active','transferred','released')", name="ck_order_reservation_status"
        ),
        sa.CheckConstraint("kind IN ('usd','shares')", name="ck_order_reservation_kind"),
        sa.CheckConstraint("amount >= 0", name="ck_order_reservation_amount"),
    ),
)
keys = entity_table(
    metadata,
    "order_idempotency_keys",
    m.IdempotencyEntry,
    ("user_id", "idempotency_key"),
    references={"user_id": "users.id", "order_id": "orders.id"},
)
reauthorizations = entity_table(
    metadata,
    "order_reauthorizations",
    m.ReauthorizationRequest,
    ("id",),
    references={"order_id": "orders.id"},
)
cancels = entity_table(
    metadata,
    "order_cancel_requests",
    m.CancelRequest,
    ("id",),
    references={"order_id": "orders.id"},
)
comments = entity_table(
    metadata,
    "order_review_comments",
    m.ReviewComment,
    ("id",),
    references={"order_id": "orders.id", "broker_id": "users.id"},
)
schedule_changes = entity_table(
    metadata, "order_schedule_changes", m.ScheduleChangeRecord, ("change_id",)
)
cursors = entity_table(metadata, "order_activity_cursors", m.ActivityCursor, ("alpaca_account_id",))

# Provider-derived prices and weighted averages keep their original precision (Req. 15.4).
for table, names in (
    (orders, ("reference_price", "filled_avg_price")),
    (executions, ("price",)),
    (reauthorizations, ("previous_price", "updated_price")),
):
    for name in names:
        table.c[name].type = sa.Numeric()
for name in (
    "limit_price",
    "stop_price",
    "trail_price",
    "take_profit_limit_price",
    "stop_loss_stop_price",
):
    orders.c[name].type = sa.Numeric(18, 4)
legs.c.price.type = sa.Numeric(18, 4)
sa.Index("ix_orders_owner", orders.c.user_id, orders.c.created_at.desc(), orders.c.id)
sa.Index(
    "ix_orders_open",
    orders.c.status,
    postgresql_where=sa.text("status IN ('SUBMITTED','EXECUTING') AND NOT fully_filled"),
)
sa.Index("ix_orders_scheduled", orders.c.status, orders.c.scheduled_for)
sa.Index("ix_order_events_at", events.c.order_id, events.c.at)
sa.Index(
    "ix_order_reservations_active",
    reservations.c.user_id,
    reservations.c.kind,
    reservations.c.symbol,
    postgresql_where=reservations.c.status == "active",
)
sa.Index(
    "ix_order_reauthorization_pending",
    reauthorizations.c.order_id,
    unique=True,
    postgresql_where=reauthorizations.c.decision.is_(None),
)
sa.Index("ix_order_cancels", cancels.c.order_id)
sa.Index("ix_order_comments", comments.c.order_id, comments.c.at)

TABLES = (
    orders,
    legs,
    events,
    executions,
    reservations,
    keys,
    reauthorizations,
    cancels,
    comments,
    schedule_changes,
    cursors,
)
