"""MOD-07 RF-45/47, RFP-13: restrictions, immutable reports and KPI snapshots."""

from alembic import op

revision = "0012_admin_compliance_bi"
down_revision = "0011_admin_audit_trail_halts"
branch_labels = None
depends_on = None

TABLES = ("admin_account_restrictions", "admin_compliance_reports", "admin_kpi_snapshots")


def upgrade() -> None:
    op.execute("""CREATE TABLE admin_account_restrictions (
        id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id),
        restriction_type text NOT NULL CHECK (restriction_type = 'trading'),
        reason text NOT NULL CHECK (char_length(btrim(reason)) BETWEEN 1 AND 500),
        evidence_text text NOT NULL CHECK (char_length(evidence_text) <= 2000),
        evidence_refs jsonb NOT NULL CHECK
          (jsonb_typeof(evidence_refs) = 'array' AND jsonb_array_length(evidence_refs) <= 20),
        restricted_by uuid NOT NULL REFERENCES users(id), restricted_at timestamptz NOT NULL,
        lifted_at timestamptz, lifted_by uuid REFERENCES users(id),
        lift_reason text CHECK (char_length(btrim(lift_reason)) BETWEEN 1 AND 500),
        lift_evidence_text text CHECK (char_length(lift_evidence_text) <= 2000),
        lift_evidence_refs jsonb CHECK (jsonb_typeof(lift_evidence_refs) = 'array'
          AND jsonb_array_length(lift_evidence_refs) <= 20), CHECK (user_id <> restricted_by),
        CHECK ((lifted_at IS NULL AND lifted_by IS NULL AND lift_reason IS NULL
          AND lift_evidence_text IS NULL AND lift_evidence_refs IS NULL) OR
          (lifted_at IS NOT NULL AND lifted_by IS NOT NULL AND lift_reason IS NOT NULL
          AND lift_evidence_text IS NOT NULL AND lift_evidence_refs IS NOT NULL))
    )""")
    op.execute(
        "CREATE UNIQUE INDEX ux_admin_restrictions_active "
        "ON admin_account_restrictions(user_id,restriction_type) WHERE lifted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX ix_admin_restrictions_history "
        "ON admin_account_restrictions(user_id,restricted_at DESC,id DESC)"
    )
    op.execute("""CREATE FUNCTION admin_restrictions_guard() RETURNS trigger AS $$ BEGIN
        IF TG_OP <> 'UPDATE' THEN RAISE EXCEPTION 'Restriction history cannot be removed'; END IF;
        IF OLD.lifted_at IS NOT NULL OR NEW.lifted_at IS NULL OR NEW.lifted_by IS NULL
          OR NEW.lift_reason IS NULL OR NEW.lift_evidence_text IS NULL
          OR NEW.lift_evidence_refs IS NULL
          OR (to_jsonb(NEW) - ARRAY['lifted_at','lifted_by','lift_reason',
               'lift_evidence_text','lift_evidence_refs']) IS DISTINCT FROM
             (to_jsonb(OLD) - ARRAY['lifted_at','lifted_by','lift_reason',
               'lift_evidence_text','lift_evidence_refs'])
        THEN RAISE EXCEPTION 'Only one restriction lift is permitted'; END IF;
        RETURN NEW; END; $$ LANGUAGE plpgsql""")
    op.execute("""CREATE TRIGGER admin_restrictions_guard BEFORE UPDATE OR DELETE
        ON admin_account_restrictions FOR EACH ROW EXECUTE FUNCTION admin_restrictions_guard()""")
    op.execute("""CREATE TRIGGER admin_restrictions_no_truncate BEFORE TRUNCATE
        ON admin_account_restrictions FOR EACH STATEMENT
        EXECUTE FUNCTION admin_evidence_immutable()""")
    op.execute("""CREATE TABLE admin_compliance_reports (
        id uuid PRIMARY KEY,user_id uuid NOT NULL REFERENCES users(id),
        period_from date NOT NULL,period_to date NOT NULL CHECK (period_to >= period_from),
        rules_version text NOT NULL,content jsonb NOT NULL CHECK (jsonb_typeof(content) = 'object'),
        content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[a-f0-9]{64}$'),
        generated_by uuid NOT NULL REFERENCES users(id),generated_at timestamptz NOT NULL
    )""")
    op.execute(
        "CREATE INDEX ix_admin_reports_user "
        "ON admin_compliance_reports(user_id,generated_at DESC,id DESC)"
    )
    op.execute("""CREATE TRIGGER admin_reports_immutable BEFORE UPDATE OR DELETE
        ON admin_compliance_reports FOR EACH ROW EXECUTE FUNCTION admin_evidence_immutable()""")
    op.execute("""CREATE TRIGGER admin_reports_no_truncate BEFORE TRUNCATE
        ON admin_compliance_reports FOR EACH STATEMENT
        EXECUTE FUNCTION admin_evidence_immutable()""")
    op.execute("""CREATE TABLE admin_kpi_snapshots (
        period_from date NOT NULL,period_to date NOT NULL,
        definitions_version text NOT NULL,payload jsonb NOT NULL,computed_at timestamptz NOT NULL,
        PRIMARY KEY(period_from,period_to,definitions_version)
    )""")
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION admin_restrictions_guard()")
