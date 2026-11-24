"""MOD-07 RF-44/46: immutable sources, order terms and trading halts."""

from alembic import op

revision = "0011_admin_audit_trail_halts"
down_revision = "0010_admin_fees_audit"
branch_labels = None
depends_on = None

IMMUTABLE = ("order_events", "order_executions", "auth_events")
EVENTS = (
    "'market_open','market_close','proposals','approval_requests','price_changes',"
    "'execution_confirmations','daily_summary','broker_link_updates','proposal_updates'"
)


def notification_checks(extra: str) -> None:
    for table, values in (
        ("notifications", EVENTS),
        (
            "notification_preferences",
            EVENTS + ",'balance_changes','order_executions','order_updates'",
        ),
    ):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_event_type_check")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_event_type_check "
            f"CHECK (event_type IN ({values}{extra}))"
        )


def upgrade() -> None:
    # H3: additive nullable fields; intentionally NO UPDATE/backfill of historical orders.
    op.execute("""ALTER TABLE orders
        ADD COLUMN fee_version_id uuid REFERENCES admin_fee_versions(id),
        ADD COLUMN commission_rate_pct numeric(6,4) CHECK (commission_rate_pct BETWEEN 0 AND 10),
        ADD COLUMN platform_share_pct numeric(5,2) CHECK (platform_share_pct BETWEEN 0 AND 100),
        ADD CONSTRAINT ck_order_commission_terms CHECK
          ((commission_rate_pct IS NULL AND platform_share_pct IS NULL AND fee_version_id IS NULL)
            OR (commission_rate_pct IS NOT NULL AND platform_share_pct IS NOT NULL))""")
    op.execute("""CREATE FUNCTION order_commission_terms_guard() RETURNS trigger AS $$ BEGIN
        IF ROW(NEW.fee_version_id,NEW.commission_rate_pct,NEW.platform_share_pct)
          IS DISTINCT FROM ROW(OLD.fee_version_id,OLD.commission_rate_pct,OLD.platform_share_pct)
        THEN RAISE EXCEPTION 'Accepted order terms are immutable'; END IF;
        RETURN NEW; END; $$ LANGUAGE plpgsql""")
    op.execute("""CREATE TRIGGER order_commission_terms_guard BEFORE UPDATE ON orders
        FOR EACH ROW EXECUTE FUNCTION order_commission_terms_guard()""")
    for table in IMMUTABLE:
        op.execute(
            f"CREATE TRIGGER {table}_admin_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION admin_evidence_immutable()"
        )
    for table in (*IMMUTABLE, "broker_events"):
        op.execute(
            f"CREATE TRIGGER {table}_admin_no_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION admin_evidence_immutable()"
        )
    op.execute("""CREATE TABLE admin_trading_halts (
        id uuid PRIMARY KEY, market_code text REFERENCES markets(code),
        reason text NOT NULL CHECK (char_length(btrim(reason)) BETWEEN 1 AND 500),
        starts_at timestamptz NOT NULL, ends_at timestamptz,
        created_by uuid NOT NULL REFERENCES users(id), created_at timestamptz NOT NULL,
        released_at timestamptz, released_by uuid REFERENCES users(id),
        release_reason text CHECK (char_length(btrim(release_reason)) BETWEEN 1 AND 500),
        CHECK (ends_at IS NULL OR ends_at > starts_at), CHECK (starts_at >= created_at),
        CHECK ((released_at IS NULL AND released_by IS NULL AND release_reason IS NULL) OR
          (released_at IS NOT NULL AND released_by IS NOT NULL AND release_reason IS NOT NULL))
    )""")
    op.execute(
        "CREATE INDEX ix_admin_halts_active ON admin_trading_halts(market_code,starts_at) "
        "WHERE released_at IS NULL"
    )
    op.execute("""CREATE FUNCTION admin_trading_halts_guard() RETURNS trigger AS $$ BEGIN
        IF TG_OP <> 'UPDATE' THEN RAISE EXCEPTION 'Halt history cannot be removed'; END IF;
        IF OLD.released_at IS NOT NULL OR NEW.released_at IS NULL
          OR NEW.released_by IS NULL OR NEW.release_reason IS NULL
          OR (to_jsonb(NEW) - ARRAY['released_at','released_by','release_reason']) IS DISTINCT FROM
             (to_jsonb(OLD) - ARRAY['released_at','released_by','release_reason'])
        THEN RAISE EXCEPTION 'Only one halt release is permitted'; END IF;
        RETURN NEW; END; $$ LANGUAGE plpgsql""")
    op.execute("""CREATE TRIGGER admin_trading_halts_guard BEFORE UPDATE OR DELETE
        ON admin_trading_halts FOR EACH ROW EXECUTE FUNCTION admin_trading_halts_guard()""")
    op.execute("""CREATE TRIGGER admin_halts_no_truncate BEFORE TRUNCATE ON admin_trading_halts
        FOR EACH STATEMENT EXECUTE FUNCTION admin_evidence_immutable()""")
    op.execute("""CREATE TABLE admin_schedule_dispatches (
        audit_entry_id uuid PRIMARY KEY REFERENCES admin_audit_log(id),
        market_code text NOT NULL REFERENCES markets(code), dispatched_at timestamptz NOT NULL,
        affected_orders integer NOT NULL CHECK (affected_orders >= 0),
        notified_users integer NOT NULL CHECK (notified_users >= 0)
    )""")
    for table in ("admin_trading_halts", "admin_schedule_dispatches"):
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    notification_checks(",'market_schedule_changes'")
    op.execute("""INSERT INTO notification_preferences(user_id,event_type,channel,enabled)
        SELECT id,'market_schedule_changes',c.channel,c.channel = 'in_app' FROM users
        CROSS JOIN (VALUES ('in_app'),('email'),('sms'),('telegram')) c(channel)
        ON CONFLICT DO NOTHING""")
    op.execute("CREATE INDEX ix_order_events_audit ON order_events(at DESC,id DESC)")
    op.execute("CREATE INDEX ix_broker_events_audit ON broker_events(at DESC,id DESC)")
    op.execute("CREATE INDEX ix_auth_events_audit ON auth_events(occurred_at DESC,id DESC)")
    op.execute("CREATE INDEX ix_order_events_actor_at ON order_events(actor_id,at DESC)")
    op.execute("CREATE INDEX ix_broker_events_actor_at ON broker_events(actor_id,at DESC)")
    op.execute("CREATE INDEX ix_auth_events_user_at ON auth_events(user_id,occurred_at DESC)")
    op.execute(
        "CREATE INDEX ix_orders_admin_broker ON orders(broker_id) WHERE broker_id IS NOT NULL"
    )
    op.execute("""CREATE VIEW audit_trail AS
        SELECT 'admin'::text AS source,a.id::text AS event_id,a.occurred_at,
          'user'::text AS actor_type,a.actor_user_id AS actor_id,
          CASE WHEN a.target_type = 'user' THEN a.target_id::uuid END AS subject_user_id,
          NULL::uuid AS related_user_id,a.action,a.target_type AS entity_type,
          a.target_id AS entity_id,NULL::text AS from_state,NULL::text AS to_state,
          a.payload AS details,a.ip_address FROM admin_audit_log a
        UNION ALL
        SELECT 'orders',e.id::text,e.at,e.actor_type,e.actor_id,o.user_id,
          o.broker_id,e.cause,'order',o.id::text,e.from_status,e.to_status,e.metadata,NULL::text
          FROM order_events e JOIN orders o ON o.id = e.order_id
        UNION ALL
        SELECT 'brokers',e.id::text,e.at,e.actor_type,e.actor_id,
          COALESCE(p.investor_id,l.investor_id,al.investor_id),
          COALESCE(p.broker_id,l.broker_id,al.broker_id),
          e.entity_type || '.' || e.to_status,e.entity_type,e.entity_id::text,
          e.from_status,e.to_status,e.details || jsonb_build_object('reason',e.reason),NULL::text
          FROM broker_events e
          LEFT JOIN broker_links l ON e.entity_type = 'link' AND l.id = e.entity_id
          LEFT JOIN broker_proposals p ON e.entity_type = 'proposal' AND p.id = e.entity_id
          LEFT JOIN broker_trading_authorizations a ON e.entity_type = 'trading_authorization'
            AND a.id = e.entity_id LEFT JOIN broker_links al ON al.id = a.link_id
        UNION ALL
        SELECT 'auth',a.id::text,a.occurred_at,'user',a.user_id,a.user_id,NULL::uuid,
          a.kind || '.' || a.result,'session',NULL::text,NULL::text,NULL::text,
          jsonb_build_object('result',a.result,'method',a.method,'user_agent',a.user_agent),
          a.ip_address FROM auth_events a""")


def downgrade() -> None:
    op.execute("DROP VIEW audit_trail")
    for index in ("ix_order_events_audit", "ix_broker_events_audit", "ix_auth_events_audit"):
        op.execute(f"DROP INDEX {index}")
    for index in (
        "ix_order_events_actor_at",
        "ix_broker_events_actor_at",
        "ix_auth_events_user_at",
        "ix_orders_admin_broker",
    ):
        op.execute(f"DROP INDEX {index}")
    op.execute("DELETE FROM notifications WHERE event_type = 'market_schedule_changes'")
    op.execute("DELETE FROM notification_preferences WHERE event_type = 'market_schedule_changes'")
    notification_checks("")
    op.execute("DROP TABLE admin_schedule_dispatches")
    op.execute("DROP TABLE admin_trading_halts")
    op.execute("DROP FUNCTION admin_trading_halts_guard()")
    for table in (*IMMUTABLE, "broker_events"):
        op.execute(f"DROP TRIGGER {table}_admin_no_truncate ON {table}")
    for table in IMMUTABLE:
        op.execute(f"DROP TRIGGER {table}_admin_immutable ON {table}")
    op.execute("DROP TRIGGER order_commission_terms_guard ON orders")
    op.execute("DROP FUNCTION order_commission_terms_guard()")
    op.execute("""ALTER TABLE orders DROP CONSTRAINT ck_order_commission_terms,
        DROP COLUMN fee_version_id,DROP COLUMN commission_rate_pct,
        DROP COLUMN platform_share_pct""")
