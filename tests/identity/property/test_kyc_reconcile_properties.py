"""Property 48: reconciliation follows the decision table (Requirement 24)."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.identity.domain.kyc import AlpacaAccountSummary
from acciones_ud.identity.domain.kyc_reconcile import (
    Ambiguous,
    Found,
    KycState,
    NotFound,
    ReconcileDecision,
    pick_candidate,
    precheck,
    reconcile_alpaca_error,
)
from acciones_ud.shared.domain.alpaca_errors import (
    AlpacaAuthError,
    AlpacaNotFound,
    AlpacaRateLimited,
    AlpacaUnavailable,
    AlpacaValidationError,
)
from acciones_ud.shared.domain.errors import AppError, ErrorCode

NOW = datetime(2026, 1, 1, tzinfo=UTC)
STORED = UUID("11111111-1111-1111-1111-111111111111")


# Feature: identity-market-backend, Property 48: Reconciliation follows the decision table
@given(
    link=st.sampled_from(["none", "unlinked", "linked"]),
    has_reservation=st.booleans(),
    reserved_delta=st.integers(min_value=-1000, max_value=1000),
    supplied=st.booleans(),
    same_as_stored=st.booleans(),
)
def test_precheck_follows_the_table(
    link: str,
    has_reservation: bool,
    reserved_delta: int,
    supplied: bool,
    same_as_stored: bool,
) -> None:
    reserved_at = (
        NOW + timedelta(seconds=reserved_delta)
        if link == "unlinked" and has_reservation
        else None
    )
    state = KycState(
        link,
        "11111111-1111-1111-1111-111111111111" if link == "linked" else None,
        "ACTIVE" if link == "linked" else None,
        reserved_at,
    )
    supplied_id = (STORED if same_as_stored else uuid4()) if supplied else None

    if link == "linked" and supplied and not same_as_stored:
        with pytest.raises(AppError) as caught:
            precheck(state, supplied_id, NOW)
        assert caught.value.code is ErrorCode.KYC_ACCOUNT_EXISTS
    elif (
        link == "unlinked"
        and reserved_at is not None
        and (NOW - reserved_at).total_seconds() < 120
    ):
        with pytest.raises(AppError) as caught:
            precheck(state, supplied_id, NOW)
        assert caught.value.code is ErrorCode.KYC_SUBMISSION_IN_PROGRESS
    else:
        expected = (
            ReconcileDecision.ALREADY_LINKED
            if link == "linked"
            else (
                ReconcileDecision.LOOKUP_BY_ID
                if supplied
                else ReconcileDecision.SEARCH_BY_EMAIL
            )
        )
        assert precheck(state, supplied_id, NOW) is expected


@given(
    emails=st.lists(
        st.one_of(st.none(), st.sampled_from(["a@example.com", "A@EXAMPLE.COM ", "b@x.com"])),
        max_size=5,
    )
)
def test_pick_candidate_counts_exact_email_matches(
    emails: list[str | None],
) -> None:
    accounts = [
        AlpacaAccountSummary(str(uuid4()), "ACTIVE", contact_email=email)
        for email in emails
    ]
    matched = [
        account
        for account in accounts
        if (account.contact_email or "").strip().casefold() == "a@example.com"
    ]

    picked = pick_candidate(accounts, " A@example.com ")

    if not matched:
        assert isinstance(picked, NotFound)
    elif len(matched) == 1:
        assert isinstance(picked, Found) and picked.account == matched[0]
    else:
        assert isinstance(picked, Ambiguous) and picked.count == len(matched)


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (AlpacaNotFound(), 404, ErrorCode.KYC_RECONCILE_NOT_FOUND),
        (AlpacaRateLimited(), 503, ErrorCode.ALPACA_RATE_LIMITED),
        (AlpacaUnavailable(), 502, ErrorCode.ALPACA_UNAVAILABLE),
        (AlpacaAuthError(), 500, ErrorCode.INTERNAL_ERROR),
        (AlpacaValidationError("x"), 500, ErrorCode.INTERNAL_ERROR),
    ],
)
def test_alpaca_errors_map_without_symbol_not_found(
    error: Exception, status: int, code: ErrorCode
) -> None:
    mapped = reconcile_alpaca_error(error)  # type: ignore[arg-type]
    assert mapped.status == status and mapped.code is code
