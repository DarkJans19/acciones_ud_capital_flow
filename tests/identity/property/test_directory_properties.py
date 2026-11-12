"""Properties 41 and 42 for the administrative user directory (Requirements 20.8, 21)."""

import re
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.identity.domain.directory import (
    KYC_STATUSES,
    DirectoryQuery,
    kyc_fields,
    like_pattern,
    select,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def user_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": uuid4(),
        "email": "ana@example.com",
        "first_names": "Ana",
        "last_names": "Perez",
        "phone": None,
        "country": "CO",
        "account_status": "active",
        "is_premium": False,
        "broker_requested": False,
        "created_at": NOW,
        "roles": [],
        "kyc": None,
    }
    row.update(overrides)
    return row


# Feature: identity-market-backend, Property 41: The q pattern matches literally
@given(st.text(alphabet="ab%_\\", min_size=1, max_size=6))
def test_like_pattern_escapes_and_round_trips(q: str) -> None:
    pattern = like_pattern(q)
    assert pattern.startswith("%") and pattern.endswith("%")
    assert re.sub(r"\\(.)", r"\1", pattern[1:-1]) == q


def test_wildcards_in_q_are_literal_characters() -> None:
    row = user_row(first_names="a%b")

    assert select([row], DirectoryQuery(q="a%b"), NOW).total == 1
    assert select([row], DirectoryQuery(q="a_b"), NOW).total == 0
    assert select([row], DirectoryQuery(q="a\\b"), NOW).total == 0


@given(
    q=st.text(alphabet="abcABC%_\\", min_size=1, max_size=4),
    name=st.text(alphabet="abcABC%_\\", min_size=0, max_size=8),
)
def test_q_matches_the_literal_substring(q: str, name: str) -> None:
    row = user_row(first_names=name)
    page = select([row], DirectoryQuery(q=q), NOW)
    fields = (name, "ana@example.com", "Perez")
    assert page.total == (1 if any(q.casefold() in value.casefold() for value in fields) else 0)


# Feature: identity-market-backend, Property 42: KYC_Link_State and KYC fields are
# derived from the stored row
@given(
    exists=st.booleans(),
    linked=st.booleans(),
    status=st.sampled_from(KYC_STATUSES + ("STORE_ONLY_VALUE",)),
    checked=st.one_of(st.none(), st.datetimes(timezones=st.just(UTC))),
)
def test_kyc_fields_follow_the_link_state(
    exists: bool, linked: bool, status: str, checked: datetime | None
) -> None:
    reserved = NOW - timedelta(days=1)
    created = NOW - timedelta(days=2)
    kyc = (
        None
        if not exists
        else {
            "alpaca_account_id": "alpaca-account" if linked else None,
            "status": status,
            "status_updated_at": NOW,
            "status_checked_at": checked,
            "reserved_at": reserved,
            "created_at": created,
        }
    )

    fields = kyc_fields(kyc)

    if not exists:
        assert fields["kyc_link_state"] == "none"
        assert all(
            value is None for key, value in fields.items() if key != "kyc_link_state"
        )
    elif not linked:
        assert fields["kyc_link_state"] == "unlinked"
        assert fields["kyc_alpaca_account_id"] is None
        assert fields["kyc_status"] is None
        assert fields["kyc_status_updated_at"] is None
        assert fields["kyc_status_checked_at"] is None
        assert fields["kyc_reserved_at"] == reserved
        assert fields["kyc_created_at"] == created
    else:
        assert fields["kyc_link_state"] == "linked"
        assert fields["kyc_alpaca_account_id"] == "alpaca-account"
        assert fields["kyc_status"] == status
        assert fields["kyc_status_updated_at"] == NOW
        assert fields["kyc_status_checked_at"] == checked
        assert fields["kyc_reserved_at"] == reserved
        assert fields["kyc_created_at"] == created
