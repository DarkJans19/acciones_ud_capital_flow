"""MOD-07 RF-03/43/44/46: fees, RBAC separation and audit envelope."""

from alembic import op

revision = "0010_admin_fees_audit"
down_revision = "0009_brokers_schema"
branch_labels = None
depends_on = None

OLD_ACTIONS = (
    "administrator_created",
    "broker_activated",
    "premium_changed",
    "role_assignment_created",
    "role_assignment_updated",
    "role_assignment_revoked",
    "role_assignment_cancelled",
    "role_permission_added",
    "role_permission_removed",
    "kyc_reconciled",
)
NEW_ACTIONS = (
    "fee_version_created",
    "fee_version_canceled",
    "trading_halt_activated",
    "trading_halt_released",
    "account_restricted",
    "account_rehabilitated",
    "compliance_report_generated",
    "market_default_schedule_set",
    "market_default_schedule_cleared",
    "schedule_override_created",
    "schedule_override_updated",
    "schedule_override_deleted",
)
PERMISSIONS = (
    "admin:fees",
    "admin:commissions",
    "admin:halts",
    "admin:audit",
    "admin:compliance",
    "admin:compliance:read",
    "admin:bi",
)


def audit_constraints(actions: tuple[str, ...], targets: tuple[str, ...]) -> None:
    for name, column, values in (
        ("ck_admin_audit_action", "action", actions),
        ("ck_admin_audit_target_type", "target_type", targets),
    ):
        op.execute(f"ALTER TABLE admin_audit_log DROP CONSTRAINT {name}")
        quoted = ",".join(f"'{v}'" for v in values)
        op.execute(
            f"ALTER TABLE admin_audit_log ADD CONSTRAINT {name} CHECK ({column} IN ({quoted}))"
        )


def roles_constraint(values: str) -> None:
    # 0001 used an unnamed CHECK; PostgreSQL chooses its name.
    op.execute("""DO $$ DECLARE c record; BEGIN
        FOR c IN SELECT conname FROM pg_constraint
          WHERE conrelid = 'roles'::regclass AND contype = 'c'
        LOOP EXECUTE format('ALTER TABLE roles DROP CONSTRAINT %I', c.conname); END LOOP;
        END $$""")
    op.execute(f"ALTER TABLE roles ADD CONSTRAINT ck_roles_code CHECK (code IN ({values}))")


def upgrade() -> None:
    roles_constraint("'investor','broker','administrator','auditor','analyst'")
    op.execute("INSERT INTO roles(code,name) VALUES ('auditor','Auditor'),('analyst','Analyst')")
    for permission in PERMISSIONS:
        op.execute(
            f"INSERT INTO permissions(code,description) VALUES ('{permission}','{permission}')"
        )
        op.execute(
            f"INSERT INTO role_permissions(role_code,permission_code) "
            f"VALUES ('administrator','{permission}')"
        )
    op.execute("""INSERT INTO role_permissions(role_code,permission_code) VALUES
        ('auditor','admin:audit'),('auditor','admin:compliance:read'),('analyst','admin:bi')""")
    # No legacy broad grants survive as a route to control privileges.
    op.execute("""DELETE FROM role_permissions WHERE permission_code LIKE 'admin:%'
        AND role_code <> 'administrator' AND NOT
        ((role_code = 'auditor' AND permission_code IN ('admin:audit','admin:compliance:read'))
          OR (role_code = 'analyst' AND permission_code = 'admin:bi'))""")
    op.execute(
        "ALTER TABLE admin_audit_log ADD COLUMN ip_address text "
        "CHECK (char_length(ip_address) <= 64), ADD COLUMN request_id text "
        "CHECK (char_length(request_id) <= 64)"
    )
    audit_constraints(
        OLD_ACTIONS + NEW_ACTIONS, ("user", "role", "fee_version", "market", "trading_halt")
    )
    op.execute("""CREATE FUNCTION admin_evidence_immutable() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'Audit evidence is append-only'; END; $$ LANGUAGE plpgsql""")
    op.execute("""CREATE TRIGGER admin_audit_no_truncate BEFORE TRUNCATE ON admin_audit_log
        FOR EACH STATEMENT EXECUTE FUNCTION admin_evidence_immutable()""")
    op.execute("""CREATE TABLE admin_fee_versions (
        id uuid PRIMARY KEY, market_code text REFERENCES markets(code) ON DELETE RESTRICT,
        version_no integer NOT NULL CHECK (version_no > 0),
        commission_rate_pct numeric(6,4) NOT NULL CHECK (commission_rate_pct BETWEEN 0 AND 10),
        platform_share_pct numeric(5,2) NOT NULL CHECK (platform_share_pct BETWEEN 0 AND 100),
        effective_from timestamptz NOT NULL,
        reason text NOT NULL CHECK (char_length(btrim(reason)) BETWEEN 1 AND 500),
        created_by uuid REFERENCES users(id), created_at timestamptz NOT NULL,
        canceled_at timestamptz, canceled_by uuid REFERENCES users(id),
        cancel_reason text CHECK (char_length(btrim(cancel_reason)) BETWEEN 1 AND 500),
        CHECK ((created_by IS NULL) = (version_no = 1 AND market_code IS NULL)),
        CHECK (created_by IS NULL OR effective_from >= created_at),
        CHECK ((canceled_at IS NULL AND canceled_by IS NULL AND cancel_reason IS NULL)
            OR (canceled_at IS NOT NULL AND canceled_by IS NOT NULL AND cancel_reason IS NOT NULL))
    )""")
    op.execute(
        "CREATE UNIQUE INDEX ux_fee_versions_scope_no ON admin_fee_versions "
        "(COALESCE(market_code,'~default'),version_no)"
    )
    op.execute(
        "CREATE UNIQUE INDEX ux_fee_versions_scope_from ON admin_fee_versions "
        "(COALESCE(market_code,'~default'),effective_from) WHERE canceled_at IS NULL"
    )
    op.execute("""INSERT INTO admin_fee_versions VALUES
        ('00000000-0000-0000-0000-000000000701',NULL,1,2.0000,60.00,
         '1970-01-01T00:00:00Z','Tarifa base del catálogo (RF-43)',NULL,now(),NULL,NULL,NULL)""")
    op.execute('ALTER TABLE "admin_fee_versions" ENABLE ROW LEVEL SECURITY')
    op.execute("""CREATE FUNCTION admin_fee_versions_guard() RETURNS trigger AS $$ BEGIN
        IF TG_OP <> 'UPDATE' THEN RAISE EXCEPTION 'Fee history cannot be removed'; END IF;
        IF OLD.canceled_at IS NOT NULL OR OLD.effective_from <= clock_timestamp()
          OR NEW.canceled_at IS NULL OR NEW.canceled_by IS NULL OR NEW.cancel_reason IS NULL
          OR (to_jsonb(NEW) - ARRAY['canceled_at','canceled_by','cancel_reason']) IS DISTINCT FROM
             (to_jsonb(OLD) - ARRAY['canceled_at','canceled_by','cancel_reason'])
        THEN RAISE EXCEPTION 'Only future fees can be canceled once'; END IF;
        RETURN NEW; END; $$ LANGUAGE plpgsql""")
    op.execute("""CREATE TRIGGER admin_fee_versions_guard BEFORE UPDATE OR DELETE
        ON admin_fee_versions FOR EACH ROW EXECUTE FUNCTION admin_fee_versions_guard()""")
    op.execute("""CREATE TRIGGER admin_fees_no_truncate BEFORE TRUNCATE ON admin_fee_versions
        FOR EACH STATEMENT EXECUTE FUNCTION admin_evidence_immutable()""")


def downgrade() -> None:
    op.execute("DROP TABLE admin_fee_versions")
    op.execute("DROP FUNCTION admin_fee_versions_guard()")
    # Downgrade is explicitly destructive, only for disposable databases.
    op.execute("DROP TRIGGER trg_admin_audit_log_immutable ON admin_audit_log")
    actions = ",".join(f"'{v}'" for v in NEW_ACTIONS)
    op.execute(f"DELETE FROM admin_audit_log WHERE action IN ({actions})")
    op.execute("""CREATE TRIGGER trg_admin_audit_log_immutable BEFORE UPDATE OR DELETE
        ON admin_audit_log FOR EACH ROW EXECUTE FUNCTION admin_audit_log_immutable()""")
    audit_constraints(OLD_ACTIONS, ("user", "role"))
    op.execute("DROP TRIGGER admin_audit_no_truncate ON admin_audit_log")
    op.execute("DROP FUNCTION admin_evidence_immutable()")
    op.execute("ALTER TABLE admin_audit_log DROP COLUMN ip_address, DROP COLUMN request_id")
    for permission in PERMISSIONS:
        op.execute(f"DELETE FROM role_permissions WHERE permission_code = '{permission}'")
        op.execute(f"DELETE FROM permissions WHERE code = '{permission}'")
    op.execute("DELETE FROM role_assignments WHERE role_code IN ('auditor','analyst')")
    op.execute("DELETE FROM role_permissions WHERE role_code IN ('auditor','analyst')")
    op.execute("DELETE FROM roles WHERE code IN ('auditor','analyst')")
    roles_constraint("'investor','broker','administrator'")
