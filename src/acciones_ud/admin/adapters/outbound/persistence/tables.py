import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from acciones_ud.admin.domain import model as m
from acciones_ud.shared.infrastructure.entity_repository import entity_table

metadata = sa.MetaData()
fees = entity_table(metadata, "admin_fee_versions", m.FeeVersion, ("id",))
halts = entity_table(metadata, "admin_trading_halts", m.TradingHalt, ("id",))
restrictions = entity_table(metadata, "admin_account_restrictions", m.AccountRestriction, ("id",))
restrictions.c.lift_evidence_refs.type = JSONB(none_as_null=True)
reports = entity_table(metadata, "admin_compliance_reports", m.ComplianceReport, ("id",))
snapshots = entity_table(
    metadata,
    "admin_kpi_snapshots",
    m.KpiSnapshot,
    ("period_from", "period_to", "definitions_version"),
)
for table in (fees,):
    table.c.commission_rate_pct.type = sa.Numeric(6, 4)
    table.c.platform_share_pct.type = sa.Numeric(5, 2)
for table in (reports, snapshots):
    table.c.period_from.type = sa.Date()
    table.c.period_to.type = sa.Date()
