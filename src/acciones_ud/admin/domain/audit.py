from datetime import datetime
from typing import Any
from uuid import UUID

from acciones_ud.shared.domain.audit_entry import AuditRecord, RequestMeta, build_record

PAYLOAD_KEYS = {
    "fee_version_created": frozenset({"scope", "version_no", "before", "after"}),
    "fee_version_canceled": frozenset({"scope", "version_no", "reason", "before", "after"}),
    "trading_halt_activated": frozenset({"scope", "starts_at", "ends_at", "reason"}),
    "trading_halt_released": frozenset({"scope", "reason", "before", "after"}),
    "account_restricted": frozenset({"restriction_id", "restriction_type", "reason", "evidence"}),
    "account_rehabilitated": frozenset(
        {"restriction_id", "restriction_type", "reason", "evidence"}
    ),
    "compliance_report_generated": frozenset(
        {"report_id", "period_from", "period_to", "rules_version", "content_sha256"}
    ),
}
SENSITIVE_KEYS = frozenset(
    {
        "totp_code",
        "code",
        "password",
        "password_hash",
        "token",
        "access_token",
        "refresh_token",
        "mfa_token",
        "secret",
        "recovery_code",
        "recovery_codes",
        "tax_id",
        "cookie",
        "cookies",
        "authorization",
        "api_key",
        "api_secret",
        "client_secret",
        "stripe_secret_key",
        "alpaca_broker_api_key",
        "alpaca_broker_api_secret",
        "totp_secret",
        "totp_last_step",
        "totp_secret_encrypted",
        "stripe_webhook_secret",
    }
)


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: sanitize(v) for k, v in value.items() if str(k).lower() not in SENSITIVE_KEYS}
    if isinstance(value, (tuple, list)):
        return [sanitize(v) for v in value]
    return value


def build(
    action: str,
    actor: UUID,
    target_type: str,
    target_id: str,
    payload: dict[str, Any],
    at: datetime,
    meta: RequestMeta,
) -> AuditRecord:
    return build_record(
        action, PAYLOAD_KEYS[action], actor, target_type, target_id, sanitize(payload), at, meta
    )
