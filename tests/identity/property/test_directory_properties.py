"""Properties 41, 42 and 40 for the administrative user directory (Requirements 20, 21)."""

import asyncio
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.identity.application.user_directory import UserDirectoryService
from acciones_ud.identity.domain.directory import (
    KYC_STATUSES,
    DirectoryQuery,
    kyc_fields,
    like_pattern,
    select,
)
from tests.support.clock import FakeClock
from tests.support.identity_fakes import FakeDirectoryRepository, FakeDirectoryWorkFactory

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


def make_user(
    user_id: UUID,
    created_at: datetime,
    status: str,
    broker: bool,
    first: str,
    last: str,
    role_code: str,
    role_status: str,
    kyc_kind: str,
    kyc_status: str,
) -> dict[str, object]:
    kyc = None
    if kyc_kind != "none":
        kyc = {
            "alpaca_account_id": "acc" if kyc_kind == "linked" else None,
            "status": kyc_status if kyc_kind == "linked" else None,
            "status_updated_at": NOW if kyc_kind == "linked" else None,
            "status_checked_at": NOW if kyc_kind == "linked" else None,
            "reserved_at": NOW,
            "created_at": NOW,
        }
    return {
        "id": user_id,
        "email": f"{user_id.hex[:8]}@example.com",
        "first_names": first,
        "last_names": last,
        "phone": None,
        "country": "CO",
        "account_status": status,
        "is_premium": False,
        "broker_requested": broker,
        "created_at": created_at,
        "roles": (
            []
            if role_code == "none"
            else [
                {
                    "role_code": role_code,
                    "status": role_status,
                    "valid_from": NOW - timedelta(hours=1),
                    "valid_to": None,
                }
            ]
        ),
        "kyc": kyc,
    }


def reference(users: list[dict[str, object]], query: DirectoryQuery) -> list[UUID]:
    """Independent model: filters, effective roles, ordering and paging (20.1-20.10)."""
    rows: list[tuple[dict[str, object], tuple[str, ...]]] = []
    for user in users:
        if user["account_status"] != "active":
            roles: tuple[str, ...] = ()
        else:
            roles = tuple(
                sorted(
                    {
                        str(assignment["role_code"])
                        for assignment in user["roles"]  # type: ignore[union-attr]
                        if assignment["status"] == "ACTIVE"
                        and assignment["valid_from"] <= NOW
                        and (
                            assignment["valid_to"] is None
                            or NOW < assignment["valid_to"]
                        )
                    }
                )
            )
        if query.account_status is not None and user["account_status"] != query.account_status:
            continue
        if query.role is not None and query.role not in roles:
            continue
        if query.q is not None:
            needle = query.q.casefold()
            if not any(
                needle in str(user[key]).casefold()
                for key in ("email", "first_names", "last_names")
            ):
                continue
        if (
            query.broker_requested is not None
            and bool(user["broker_requested"]) != query.broker_requested
        ):
            continue
        kyc = user["kyc"]
        link = (
            "none"
            if kyc is None
            else ("unlinked" if kyc["alpaca_account_id"] is None else "linked")  # type: ignore[index]
        )
        if query.kyc_status is not None and (
            link != "linked" or kyc["status"] != query.kyc_status  # type: ignore[index]
        ):
            continue
        if query.kyc_link_state is not None and link != query.kyc_link_state:
            continue
        rows.append((user, roles))

    rows.sort(key=lambda pair: str(pair[0]["id"]))
    rows.sort(key=lambda pair: pair[0]["created_at"], reverse=True)  # type: ignore[arg-type,return-value]
    page = rows[query.offset : query.offset + query.limit]
    return [pair[0]["id"] for pair in page]  # type: ignore[misc]


# Feature: identity-market-backend, Property 40: User directory listing matches a reference model
@given(
    users=st.lists(
        st.builds(
            make_user,
            user_id=st.uuids(),
            created_at=st.datetimes(
                min_value=datetime(2026, 1, 1),
                max_value=datetime(2026, 1, 4),
                timezones=st.just(UTC),
            ),
            status=st.sampled_from(["active", "pending_broker_activation"]),
            broker=st.booleans(),
            first=st.sampled_from(["Ana", "Beto", "Carla"]),
            last=st.sampled_from(["Perez", "Gomez"]),
            role_code=st.sampled_from(["none", "investor", "broker"]),
            role_status=st.sampled_from(["ACTIVE", "CANCELLED"]),
            kyc_kind=st.sampled_from(["none", "unlinked", "linked"]),
            kyc_status=st.sampled_from(KYC_STATUSES),
        ),
        max_size=8,
    ),
    account_status=st.one_of(
        st.none(), st.sampled_from(["active", "pending_broker_activation"])
    ),
    role=st.one_of(st.none(), st.sampled_from(["investor", "broker"])),
    q=st.one_of(st.none(), st.sampled_from(["ana", "beto", "perez", "example"])),
    broker_requested=st.one_of(st.none(), st.booleans()),
    kyc_link_state=st.one_of(st.none(), st.sampled_from(["none", "unlinked", "linked"])),
    kyc_status=st.one_of(st.none(), st.sampled_from(KYC_STATUSES)),
    limit=st.integers(min_value=1, max_value=5),
    offset=st.integers(min_value=0, max_value=5),
)
def test_listing_matches_the_reference_model(
    users: list[dict[str, object]],
    account_status: str | None,
    role: str | None,
    q: str | None,
    broker_requested: bool | None,
    kyc_link_state: str | None,
    kyc_status: str | None,
    limit: int,
    offset: int,
) -> None:
    query = DirectoryQuery(
        account_status=account_status,
        role=role,
        q=q,
        broker_requested=broker_requested,
        kyc_link_state=kyc_link_state,
        kyc_status=kyc_status,
        limit=limit,
        offset=offset,
    )
    service = UserDirectoryService(
        FakeDirectoryWorkFactory(FakeDirectoryRepository(users)), FakeClock(NOW)
    )

    page = asyncio.run(service.list(query))

    assert [entry.user_id for entry in page.items] == reference(users, query)
    assert page.total == len(
        reference(
            users,
            DirectoryQuery(
                account_status=account_status,
                role=role,
                q=q,
                broker_requested=broker_requested,
                kyc_link_state=kyc_link_state,
                kyc_status=kyc_status,
                limit=100,
                offset=0,
            ),
        )
    )
    for entry in page.items:
        assert entry.kyc_link_state in {"none", "unlinked", "linked"}
