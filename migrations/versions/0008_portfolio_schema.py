"""MOD-05 RF-42: immutable investment reports; additive to 0007_orders_schema."""

from alembic import op

revision = "0008_portfolio_schema"
down_revision = "0007_orders_schema"
branch_labels = None
depends_on = None

STATEMENTS = (
    """CREATE TABLE portfolio_reports (
        id uuid PRIMARY KEY,
        owner_id uuid NOT NULL REFERENCES users(id),
        owner_role text NOT NULL CHECK (owner_role IN ('investor','broker')),
        type text NOT NULL CHECK (type IN ('on_demand','daily_summary','monthly','broker')),
        period_from date NOT NULL,
        period_to date NOT NULL,
        positions_as_of timestamptz NOT NULL,
        content jsonb NOT NULL,
        generated_at timestamptz NOT NULL,
        notified_at timestamptz,
        CONSTRAINT ck_portfolio_period CHECK (period_from <= period_to)
    )""",
    "CREATE INDEX ix_portfolio_owner ON portfolio_reports (owner_id, generated_at DESC, id)",
    "CREATE INDEX ix_portfolio_type ON portfolio_reports (owner_id, type, generated_at DESC)",
    """CREATE UNIQUE INDEX uq_portfolio_scheduled ON portfolio_reports
        (owner_id, type, period_from, period_to) WHERE type IN ('daily_summary','monthly')""",
    """CREATE INDEX ix_portfolio_pending ON portfolio_reports (generated_at)
        WHERE notified_at IS NULL""",
    'ALTER TABLE "portfolio_reports" ENABLE ROW LEVEL SECURITY',
    """CREATE FUNCTION reject_portfolio_report_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
            IF (to_jsonb(NEW) - 'notified_at') IS DISTINCT FROM
               (to_jsonb(OLD) - 'notified_at') THEN
                RAISE EXCEPTION 'portfolio_reports are immutable';
            END IF;
            RETURN NEW;
        END $$""",
    """CREATE TRIGGER portfolio_reports_immutable BEFORE UPDATE ON portfolio_reports
        FOR EACH ROW EXECUTE FUNCTION reject_portfolio_report_mutation()""",
)


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TRIGGER portfolio_reports_immutable ON portfolio_reports")
    op.execute("DROP FUNCTION reject_portfolio_report_mutation()")
    op.drop_table("portfolio_reports")
