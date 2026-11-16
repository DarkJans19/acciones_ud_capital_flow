import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

metadata = sa.MetaData()
reports = sa.Table(
    "portfolio_reports",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("owner_id", sa.Uuid(), nullable=False),
    sa.Column("owner_role", sa.Text(), nullable=False),
    sa.Column("type", sa.Text(), nullable=False),
    sa.Column("period_from", sa.Date(), nullable=False),
    sa.Column("period_to", sa.Date(), nullable=False),
    sa.Column("positions_as_of", sa.DateTime(timezone=True), nullable=False),
    sa.Column("content", JSONB(), nullable=False),
    sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("notified_at", sa.DateTime(timezone=True)),
    sa.CheckConstraint("period_from <= period_to", name="ck_portfolio_period"),
    sa.CheckConstraint("owner_role IN ('investor','broker')"),
    sa.CheckConstraint("type IN ('on_demand','daily_summary','monthly','broker')"),
)
scheduled_predicate = reports.c.type.in_(["daily_summary", "monthly"])
sa.Index("ix_portfolio_owner", reports.c.owner_id, reports.c.generated_at.desc(), reports.c.id)
sa.Index("ix_portfolio_type", reports.c.owner_id, reports.c.type, reports.c.generated_at.desc())
sa.Index(
    "uq_portfolio_scheduled",
    reports.c.owner_id,
    reports.c.type,
    reports.c.period_from,
    reports.c.period_to,
    unique=True,
    postgresql_where=scheduled_predicate,
)
sa.Index(
    "ix_portfolio_pending", reports.c.generated_at, postgresql_where=reports.c.notified_at.is_(None)
)
