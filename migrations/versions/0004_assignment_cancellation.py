"""RF-03: user-approved future assignment cancellation, preserving original dates.

Additive upgrade: existing assignments remain ACTIVE and all data is retained.
Cancellation records its authenticated actor and time; temporal checks stay intact.
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_assignment_cancellation"
down_revision = "0003_market_data_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "role_assignments", sa.Column("status", sa.Text(), nullable=False, server_default="ACTIVE")
    )
    op.add_column("role_assignments", sa.Column("cancelled_at", sa.DateTime(timezone=True)))
    op.add_column("role_assignments", sa.Column("cancelled_by", sa.Uuid()))
    op.create_foreign_key(
        "fk_assignment_cancelled_by", "role_assignments", "users", ["cancelled_by"], ["id"]
    )
    op.create_check_constraint(
        "ck_assignment_cancellation",
        "role_assignments",
        "(status = 'ACTIVE' and cancelled_at is null and cancelled_by is null) or "
        "(status = 'CANCELLED' and cancelled_at is not null and cancelled_by is not null)",
    )


def downgrade() -> None:
    # Intended only for disposable DBs: cancellation audit would be lost on downgrade.
    op.drop_constraint("ck_assignment_cancellation", "role_assignments", type_="check")
    op.drop_constraint("fk_assignment_cancelled_by", "role_assignments", type_="foreignkey")
    for column in ("cancelled_by", "cancelled_at", "status"):
        op.drop_column("role_assignments", column)
