"""Bootstrap administrator (RFP-02); credentials come only from environment."""

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

from acciones_ud.config.settings import InitialAdminSettings
from acciones_ud.identity.domain.preferences import default_preferences
from acciones_ud.identity.domain.validation import (
    normalize_email,
    valid_country,
    valid_email,
    valid_name,
    valid_phone,
)

revision = "0002_initial_admin"
down_revision = "0001_identity_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    settings = InitialAdminSettings()
    invalid = []
    for name, validator in (
        ("email", valid_email),
        ("first_names", valid_name),
        ("last_names", valid_name),
        ("phone", valid_phone),
        ("country", valid_country),
    ):
        value = getattr(settings, name)
        if not value or not validator(value):
            invalid.append("INITIAL_ADMIN_" + name.upper())
    encoded = settings.password_hash.get_secret_value() if settings.password_hash else ""
    if not encoded.startswith("$argon2id$"):
        invalid.append("INITIAL_ADMIN_PASSWORD_HASH")
    if invalid:
        raise RuntimeError("Missing or invalid configuration: " + ", ".join(sorted(invalid)))
    assert settings.email and settings.country and settings.first_names and settings.last_names
    bind = op.get_bind()
    normalized = normalize_email(settings.email)
    if bind.execute(
        sa.text("SELECT 1 FROM users WHERE email_normalized = :email"), {"email": normalized}
    ).first():
        return
    user_id = uuid4()
    bind.execute(
        sa.text("""
        INSERT INTO users (id, first_names, last_names, email, email_normalized, phone, country,
                           password_hash, account_status, terms_accepted_at, monthly_report)
        VALUES (:id, :first, :last, :email, :normalized, :phone, :country,
                :hash, 'active', now(), false)
    """),
        {
            "id": user_id,
            "first": settings.first_names.strip(),
            "last": settings.last_names.strip(),
            "email": settings.email.strip(),
            "normalized": normalized,
            "phone": settings.phone,
            "country": settings.country.upper(),
            "hash": encoded,
        },
    )
    bind.execute(
        sa.text("""
        INSERT INTO role_assignments (id, user_id, role_code, valid_from)
        VALUES (:id, :user, 'administrator', now())
    """),
        {"id": uuid4(), "user": user_id},
    )
    bind.execute(
        sa.text("""
        INSERT INTO notification_preferences (user_id, event_type, channel, enabled)
        VALUES (:user_id, :event_type, :channel, :enabled)
    """),
        [{"user_id": user_id, **p} for p in default_preferences()],
    )


def downgrade() -> None:
    # Preserve accounts that may have acquired sessions and other data after bootstrap.
    pass
