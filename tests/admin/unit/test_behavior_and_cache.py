from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from acciones_ud.admin.application.compliance_service import ComplianceService
from acciones_ud.admin.application.kpi_service import KpiService
from acciones_ud.admin.application.step_up import StepUp
from acciones_ud.admin.domain.atypical import AtypicalConfig, behavior_flags
from acciones_ud.admin.domain.model import BehaviorEvent
from acciones_ud.admin.domain.periods import Period
from acciones_ud.admin.domain.reports import digest
from acciones_ud.config.settings import require_api_settings
from acciones_ud.main import create_app
from acciones_ud.shared.domain.audit_entry import RequestMeta
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from tests.admin.fakes import Ledger, Totp, Users, setup
from tests.admin.property.test_rules import execution


def test_behavior_windows_thresholds_simultaneity_and_external_failures():
    _, clock, user, _ = setup()
    now = clock.now()
    cfg = AtypicalConfig(frequency_count=3, cancellation_count=2, rejection_count=3)
    created = [BehaviorEvent(str(i), user, uuid4(), now, "created") for i in range(3)]
    signals = behavior_flags(created, cfg)
    assert len(signals) == 3
    assert all(s.reasons == ("order_frequency",) and s.observed["count"] == 3 for s in signals)
    assert behavior_flags(created[::-1], cfg) == signals
    old = replace(created[0], at=now - timedelta(seconds=cfg.frequency_seconds))
    assert not behavior_flags([old, *created[1:]], cfg)
    canceled = [replace(e, kind="canceled") for e in created[:2]]
    assert len(behavior_flags(canceled, cfg)) == 2
    repeated_same_order = [replace(e, order_id=created[0].order_id) for e in canceled]
    assert not behavior_flags(repeated_same_order, cfg)
    rejects = [
        replace(e, kind="rejected", at=now + timedelta(seconds=i), user_rejection=True)
        for i, e in enumerate(created)
    ]
    assert len(behavior_flags(rejects, cfg)) == 1
    for kind in ("failed", "accepted"):
        intervening = BehaviorEvent("external", user, uuid4(), now + timedelta(seconds=1.5), kind)
        assert not behavior_flags([*rejects, intervening], cfg)
    external_rejection = replace(rejects[1], user_rejection=False)
    assert not behavior_flags([rejects[0], external_rejection, rejects[2]], cfg)


class Source:
    def __init__(self):
        self.fail, self.calls = False, 0

    async def inputs(self, period, now):
        self.calls += 1
        if self.fail:
            raise AppError(503, ErrorCode.DATABASE_UNAVAILABLE, "Unavailable")
        return dict(
            registered_users=2,
            active_users=1,
            registrations=[],
            investors=[],
            payments=[],
            active_subscriptions=0,
        )


async def test_kpi_ttl_refresh_stale_missing_and_definition_change():
    uow, clock, _, _ = setup()
    source = Source()
    service = KpiService(uow, source, Ledger(), clock, 300)
    period = Period(clock.now().date(), clock.now().date())
    first = await service.dashboard(period)
    assert not first["cache_hit"]
    assert (await service.dashboard(period))["cache_hit"]
    assert source.calls == 1
    assert not (await service.dashboard(period, True))["cache_hit"]
    source.fail = True
    clock.advance(301)
    stale = await service.dashboard(period)
    assert stale["stale"] and stale["computed_at"] == first["computed_at"]
    uow.work.snapshots.rows.clear()
    with pytest.raises(AppError) as caught:
        await service.dashboard(period)
    assert caught.value.code == ErrorCode.DATABASE_UNAVAILABLE
    source.fail = False
    zero = KpiService(uow, source, Ledger(), clock, 0)
    assert not (await zero.dashboard(period))["cache_hit"]
    assert not (await zero.dashboard(period))["cache_hit"]
    snapshot = next(iter(uow.work.snapshots.rows.values()))
    uow.work.snapshots.rows.clear()
    await uow.work.snapshots.upsert(replace(snapshot, definitions_version="kpi-old"))
    assert not (await service.dashboard(period))["cache_hit"]


class Trail:
    async def behavior(self, start, end):
        return []

    async def counts(self, user, start, end):
        return [{"source": "orders", "action": "created", "count": 2}]


async def test_report_snapshot_digest_unknown_terms_and_atomic_failure():
    uow, clock, actor, _ = setup()
    clock.advance(12 * 3600)
    user = uuid4()
    e = execution(1, Decimal(100), user=user)
    e = replace(e, executed_at=clock.now())
    old = replace(
        e,
        execution_id="old",
        commission_rate_pct=None,
        fee_version_id=None,
        platform_share_pct=None,
    )
    ledger = Ledger([e, old])
    service = ComplianceService(uow, ledger, Trail(), Users(), clock, AtypicalConfig())
    period = Period(clock.now().date(), clock.now().date())
    first = await service.generate_report(user, period, actor, RequestMeta())
    assert digest(first["content"]) == first["content_sha256"]
    assert first["content"]["historical_terms_unknown_count"] == 1
    ledger.rows.clear()
    assert (await service.get_report(first["id"])) == first
    assert (await service.reports_for_user(user, None, 20))["items"] == [first]
    uow.work.audit.fail = True
    with pytest.raises(AppError):
        await service.generate_report(user, period, actor, RequestMeta())
    assert len(uow.work.reports.rows) == 1


@pytest.mark.parametrize(
    "enrolled,code,valid,expected",
    [
        (False, "123456", True, ErrorCode.MFA_ENROLLMENT_REQUIRED),
        (True, None, True, ErrorCode.EXTRA_AUTHORIZATION_REQUIRED),
        (True, "invalid-sensitive", False, ErrorCode.EXTRA_AUTHORIZATION_INVALID),
    ],
)
async def test_step_up_rejections_do_not_expose_codes(enrolled, code, valid, expected):
    _, clock, actor, _ = setup()
    totp = Totp()
    totp.enrolled, totp.valid = enrolled, valid
    with pytest.raises(AppError) as caught:
        await StepUp(totp, clock).verify(actor, code)
    assert caught.value.code == expected
    assert "invalid-sensitive" not in str(caught.value)


@pytest.mark.parametrize(
    "name,value",
    [
        ("admin_atypical_absolute_usd", "NaN"),
        ("admin_atypical_absolute_usd", "1.001"),
        ("admin_atypical_multiplier", "secret-invalid-value"),
        ("admin_atypical_window_days", "6"),
        ("admin_kpi_cache_ttl_seconds", "-1"),
        ("admin_order_frequency_count", "1"),
        ("admin_jobs_enabled", "invalid-sensitive"),
        ("admin_rejection_seconds", "0"),
    ],
)
def test_configuration_rejected_by_name_only(api_settings, name, value):
    settings = api_settings.model_copy(update={name: value})
    for operation in (require_api_settings, create_app):
        with pytest.raises(RuntimeError) as caught:
            operation(settings)
        assert name.upper() in str(caught.value)
        assert "secret-invalid-value" not in str(caught.value)
        assert "invalid-sensitive" not in str(caught.value)
