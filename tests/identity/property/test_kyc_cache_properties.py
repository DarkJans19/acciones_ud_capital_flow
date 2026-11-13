"""Properties 45 and 46: cache freshness and monotonic status checks (Requirement 23)."""

from datetime import UTC, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.identity.domain.kyc import AlpacaAccount
from acciones_ud.identity.domain.kyc_cache import (
    CycleAction,
    KycStatusState,
    apply_status_check,
    cycle_action,
    serve_cached,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)
STATUSES = ["INACTIVE", "SUBMITTED", "APPROVED", "ACTIVE", "REJECTED"]


# Feature: identity-market-backend, Property 45: KYC status cache freshness decision
@given(
    checked_delta=st.one_of(st.none(), st.integers(min_value=-100_000, max_value=100_000)),
    ttl=st.integers(min_value=-100, max_value=5000),
)
def test_serve_cached_follows_the_ttl_rule(checked_delta: int | None, ttl: int) -> None:
    checked_at = None if checked_delta is None else NOW + timedelta(seconds=checked_delta)
    expected = (
        ttl > 0
        and checked_at is not None
        and (NOW - checked_at).total_seconds() <= ttl
    )
    assert serve_cached(checked_at, NOW, ttl) is expected


# Feature: identity-market-backend, Property 46: Status checks never move backwards and
# failures change nothing
@given(
    stored_status=st.one_of(st.none(), st.sampled_from(STATUSES)),
    retrieved_status=st.sampled_from(STATUSES),
    checked_delta=st.one_of(st.none(), st.integers(min_value=-1000, max_value=1000)),
    retrieved_delta=st.integers(min_value=-1000, max_value=1000),
    updated=st.one_of(st.none(), st.datetimes(timezones=st.just(UTC))),
)
def test_apply_status_check_never_moves_backwards(
    stored_status: str | None,
    retrieved_status: str,
    checked_delta: int | None,
    retrieved_delta: int,
    updated: datetime | None,
) -> None:
    checked_at = None if checked_delta is None else NOW + timedelta(seconds=checked_delta)
    retrieved_at = NOW + timedelta(seconds=retrieved_delta)
    stored = KycStatusState(stored_status, NOW - timedelta(days=1), checked_at)

    state = apply_status_check(
        stored, AlpacaAccount("account", retrieved_status, updated), retrieved_at
    )

    if checked_at is not None and checked_at > retrieved_at:
        assert state is None
        return
    assert state is not None
    assert state.checked_at == retrieved_at
    if retrieved_status == stored_status:
        assert state.status == stored_status
        assert state.status_updated_at == stored.status_updated_at
    else:
        assert state.status == retrieved_status
        assert state.status_updated_at == (updated or retrieved_at)


# Feature: identity-market-backend, Property 47: A KYC_Refresh_Job cycle follows its outcome script
@given(st.sampled_from(["ok", "rate_limited", "error"]))
def test_cycle_action_maps_each_outcome(outcome: str) -> None:
    expected = {
        "ok": CycleAction.STORE,
        "rate_limited": CycleAction.END_CYCLE,
        "error": CycleAction.SKIP,
    }
    assert cycle_action(outcome) is expected[outcome]
