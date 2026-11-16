"""MOD-06 RF-13--23, RFP-04/05/09: links, proposals and immutable evidence."""

from alembic import op

revision = "0009_brokers_schema"
down_revision = "0008_portfolio_schema"
branch_labels = None
depends_on = None

TABLES = (
    "broker_profiles",
    "broker_links",
    "broker_trading_authorizations",
    "broker_proposals",
    "broker_proposal_versions",
    "broker_proposal_decisions",
    "broker_proposal_messages",
    "broker_ratings",
    "broker_events",
)
IMMUTABLE = (
    "broker_proposal_versions",
    "broker_proposal_decisions",
    "broker_proposal_messages",
    "broker_events",
)

PREVIOUS_EVENTS = (
    "'market_open','market_close','proposals','approval_requests',"
    "'price_changes','execution_confirmations','daily_summary','balance_changes',"
    "'order_executions','order_updates'"
)

NOTIFICATION_EVENTS = (
    "'market_open','market_close','proposals','approval_requests',"
    "'price_changes','execution_confirmations','daily_summary'"
)


def notification_constraint(extra: str = "") -> None:
    op.drop_constraint("notifications_event_type_check", "notifications", type_="check")
    op.create_check_constraint(
        "notifications_event_type_check",
        "notifications",
        f"event_type IN ({NOTIFICATION_EVENTS}{extra})",
    )


def preference_constraint(extra: str = "") -> None:
    op.drop_constraint(
        "notification_preferences_event_type_check", "notification_preferences", type_="check"
    )
    op.create_check_constraint(
        "notification_preferences_event_type_check",
        "notification_preferences",
        f"event_type IN ({PREVIOUS_EVENTS}{extra})",
    )


STATEMENTS = (
    """CREATE TABLE broker_profiles (
        broker_id uuid PRIMARY KEY REFERENCES users(id),
        specialty text NOT NULL CHECK (char_length(specialty) BETWEEN 1 AND 100),
        years_experience smallint NOT NULL CHECK (years_experience BETWEEN 0 AND 60),
        certifications text[] NOT NULL CHECK (cardinality(certifications) <= 10),
        description text NOT NULL CHECK (char_length(description) <= 1000),
        updated_at timestamptz NOT NULL
    )""",
    """CREATE TABLE broker_links (
        id uuid PRIMARY KEY,
        investor_id uuid NOT NULL REFERENCES users(id),
        broker_id uuid NOT NULL REFERENCES users(id),
        status text NOT NULL CHECK (status IN
            ('requested','active','declined','canceled','expired','ended')),
        requested_at timestamptz NOT NULL,
        expires_at timestamptz NOT NULL,
        consent_version text NOT NULL CHECK (char_length(consent_version) BETWEEN 1 AND 32),
        consent_accepted_at timestamptz NOT NULL,
        responded_at timestamptz, started_at timestamptz, ended_at timestamptz,
        decline_reason text CHECK (char_length(decline_reason) BETWEEN 1 AND 500),
        end_reason text CHECK (char_length(end_reason) BETWEEN 1 AND 500),
        order_review_enabled boolean NOT NULL DEFAULT false,
        CHECK (investor_id <> broker_id)
    )""",
    """CREATE UNIQUE INDEX ux_broker_links_open_investor ON broker_links(investor_id)
        WHERE status IN ('requested','active')""",
    "CREATE INDEX ix_broker_links_broker ON broker_links(broker_id, status)",
    "CREATE INDEX ix_broker_links_history ON broker_links(investor_id, requested_at DESC, id)",
    """CREATE INDEX ix_broker_links_expiry ON broker_links(expires_at)
        WHERE status = 'requested'""",
    """CREATE TABLE broker_trading_authorizations (
        id uuid PRIMARY KEY, link_id uuid NOT NULL REFERENCES broker_links(id),
        consent_version text NOT NULL CHECK (char_length(consent_version) BETWEEN 1 AND 32),
        granted_at timestamptz NOT NULL, revoked_at timestamptz,
        revoke_reason text CHECK (revoke_reason IN ('investor','link_ended')),
        CHECK ((revoked_at IS NULL) = (revoke_reason IS NULL))
    )""",
    """CREATE UNIQUE INDEX ux_trading_auth_active_link
        ON broker_trading_authorizations(link_id) WHERE revoked_at IS NULL""",
    """CREATE TABLE broker_proposals (
        id uuid PRIMARY KEY, link_id uuid NOT NULL REFERENCES broker_links(id),
        broker_id uuid NOT NULL REFERENCES users(id),
        investor_id uuid NOT NULL REFERENCES users(id),
        status text NOT NULL CHECK (status IN
            ('sent','accepted','rejected','withdrawn','approved',
             'declined_by_broker','conversion_failed','expired')),
        current_version integer NOT NULL CHECK (current_version > 0),
        created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
        last_version_at timestamptz NOT NULL, expires_at timestamptz NOT NULL,
        status_reason text, accepted_version integer,
        order_id uuid UNIQUE REFERENCES orders(id), failure_code text,
        CHECK ((status = 'approved') = (order_id IS NOT NULL))
    )""",
    "CREATE INDEX ix_broker_proposals_investor "
    "ON broker_proposals(investor_id, created_at DESC, id)",
    "CREATE INDEX ix_broker_proposals_broker ON broker_proposals(broker_id, created_at DESC, id)",
    """CREATE INDEX ix_broker_proposals_expiry ON broker_proposals(expires_at)
        WHERE status IN ('sent','accepted')""",
    """CREATE TABLE broker_proposal_versions (
        proposal_id uuid NOT NULL REFERENCES broker_proposals(id),
        version integer NOT NULL CHECK (version > 0),
        symbol text NOT NULL, side text NOT NULL CHECK (side IN ('buy','sell')),
        qty numeric(20,9) NOT NULL CHECK (qty > 0),
        type text NOT NULL CHECK (type IN ('market','limit')),
        limit_price numeric(18,4) CHECK (limit_price > 0),
        reference_price numeric(18,4) NOT NULL CHECK (reference_price > 0),
        estimated_cost numeric(20,2) NOT NULL CHECK (estimated_cost >= 0),
        created_at timestamptz NOT NULL,
        time_in_force text NOT NULL CHECK (time_in_force = 'day'),
        PRIMARY KEY (proposal_id, version),
        CHECK ((type = 'limit') = (limit_price IS NOT NULL))
    )""",
    """CREATE TABLE broker_proposal_decisions (
        id uuid PRIMARY KEY, proposal_id uuid NOT NULL,
        version integer NOT NULL, actor_id uuid NOT NULL REFERENCES users(id),
        actor_role text NOT NULL CHECK (actor_role IN ('investor','broker')),
        decision text NOT NULL CHECK (decision IN ('accept','reject','approve','decline')),
        at timestamptz NOT NULL,
        comment text NOT NULL CHECK (char_length(comment) <= 500),
        evidence_message_ids uuid[] NOT NULL,
        evidence_text text NOT NULL CHECK (char_length(evidence_text) <= 1000),
        FOREIGN KEY (proposal_id, version) REFERENCES broker_proposal_versions(proposal_id, version)
    )""",
    "CREATE INDEX ix_broker_decisions_proposal ON broker_proposal_decisions(proposal_id, at)",
    """CREATE TABLE broker_proposal_messages (
        id uuid PRIMARY KEY, proposal_id uuid NOT NULL REFERENCES broker_proposals(id),
        author_id uuid NOT NULL REFERENCES users(id),
        body text NOT NULL CHECK (char_length(body) BETWEEN 1 AND 1000),
        created_at timestamptz NOT NULL
    )""",
    """CREATE INDEX ix_broker_messages_thread
        ON broker_proposal_messages(proposal_id, created_at, id)""",
    """CREATE TABLE broker_ratings (
        link_id uuid PRIMARY KEY REFERENCES broker_links(id),
        investor_id uuid NOT NULL REFERENCES users(id),
        broker_id uuid NOT NULL REFERENCES users(id),
        stars smallint NOT NULL CHECK (stars BETWEEN 1 AND 5),
        comment text NOT NULL CHECK (char_length(comment) <= 1000),
        created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL
    )""",
    "CREATE INDEX ix_broker_ratings_reviews ON broker_ratings(broker_id, updated_at DESC, link_id)",
    """CREATE TABLE broker_events (
        id uuid PRIMARY KEY, entity_type text NOT NULL
            CHECK (entity_type IN ('link','trading_authorization','proposal')),
        entity_id uuid NOT NULL, from_status text, to_status text NOT NULL,
        actor_type text NOT NULL CHECK (actor_type IN ('investor','broker','system')),
        actor_id uuid REFERENCES users(id), reason text, at timestamptz NOT NULL,
        details jsonb NOT NULL
    )""",
    "CREATE INDEX ix_broker_events_entity ON broker_events(entity_type, entity_id, at)",
)


def upgrade() -> None:
    preference_constraint(", 'broker_link_updates','proposal_updates'")
    notification_constraint(", 'broker_link_updates','proposal_updates'")
    for statement in STATEMENTS:
        op.execute(statement)
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    for table in IMMUTABLE:
        op.execute(f"""CREATE FUNCTION {table}_immutable() RETURNS trigger AS $$
            BEGIN RAISE EXCEPTION 'Immutable broker evidence'; END;
            $$ LANGUAGE plpgsql""")
        op.execute(f"""CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION {table}_immutable()""")
    op.execute("""INSERT INTO notification_preferences(user_id, event_type, channel, enabled)
        SELECT u.id, e.event_type, c.channel, c.channel = 'in_app'
        FROM users u CROSS JOIN
            (VALUES ('broker_link_updates'), ('proposal_updates')) AS e(event_type)
        CROSS JOIN (VALUES ('in_app'), ('email'), ('sms'), ('telegram')) AS c(channel)
        ON CONFLICT DO NOTHING""")


def downgrade() -> None:
    op.execute(
        "DELETE FROM notifications WHERE event_type IN ('broker_link_updates','proposal_updates')"
    )
    notification_constraint()
    op.execute("""DELETE FROM notification_preferences
        WHERE event_type IN ('broker_link_updates','proposal_updates')""")
    preference_constraint()
    for table in reversed(IMMUTABLE):
        op.execute(f"DROP TRIGGER {table}_immutable ON {table}")
        op.execute(f"DROP FUNCTION {table}_immutable()")
    for table in reversed(TABLES):
        op.execute(f'DROP TABLE "{table}"')
