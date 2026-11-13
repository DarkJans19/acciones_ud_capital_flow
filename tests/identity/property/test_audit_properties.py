"""Properties 49, 50 and 51 for the Audit_Log (Requirement 25)."""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.identity.application.rbac_admin import RbacService
from acciones_ud.identity.domain.audit import (
    PAYLOAD_KEYS,
    AuditAction,
    AuditEntry,
    AuditQuery,
    build_entry,
    select,
)
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from tests.support.clock import FakeClock

NOW = datetime(2026, 1, 1, tzinfo=UTC)
ACTOR = uuid4()


def payload_value(key: str) -> object:
    if key in {"valid_from", "valid_to", "previous_valid_from", "previous_valid_to"}:
        return NOW
    if key.endswith("_id"):
        return uuid4()
    if key == "is_premium":
        return True
    if key == "role":
        return "broker"
    if key == "permission_code":
        return "admin:users"
    if key == "outcome":
        return "linked"
    if key == "alpaca_account_id":
        return str(uuid4())
    return "value"


# Feature: identity-market-backend, Property 49: Audit payloads hold exactly the whitelisted keys
@given(st.sampled_from(list(AuditAction)))
def test_build_entry_enforces_the_payload_whitelist(action: AuditAction) -> None:
    expected = PAYLOAD_KEYS[action]
    payload = {key: payload_value(key) for key in expected}

    entry = build_entry(action, ACTOR, "user", "target", payload, NOW)

    assert set(entry.payload) == expected
    json.dumps(entry.payload)  # every value is a JSON type
    if expected:
        missing = dict(payload)
        missing.pop(next(iter(expected)))
        with pytest.raises(ValueError):
            build_entry(action, ACTOR, "user", "target", missing, NOW)
    with pytest.raises(ValueError):
        build_entry(action, ACTOR, "user", "target", {**payload, "secret": "x"}, NOW)


# Feature: identity-market-backend, Property 51: Audit log listing matches a reference model
@given(
    entries=st.lists(
        st.builds(
            lambda action, actor, occurred_at, target_id: AuditEntry(
                uuid4(),
                actor,
                action,
                "user",
                target_id,
                {},
                occurred_at,
            ),
            action=st.sampled_from(list(AuditAction)),
            actor=st.sampled_from([ACTOR, uuid4()]),
            occurred_at=st.datetimes(
                min_value=datetime(2026, 1, 1),
                max_value=datetime(2026, 1, 4),
                timezones=st.just(UTC),
            ),
            target_id=st.sampled_from(["user-a", "user-b"]),
        ),
        max_size=12,
    ),
    action=st.one_of(st.none(), st.sampled_from(list(AuditAction))),
    actor=st.one_of(st.none(), st.just(ACTOR)),
    target_id=st.one_of(st.none(), st.sampled_from(["user-a", "user-b"])),
    limit=st.integers(min_value=1, max_value=5),
    offset=st.integers(min_value=0, max_value=5),
)
def test_listing_matches_a_reference_model(
    entries: list[AuditEntry],
    action: AuditAction | None,
    actor: UUID | None,
    target_id: str | None,
    limit: int,
    offset: int,
) -> None:
    query = AuditQuery(
        action=action,
        actor_user_id=actor,
        target_id=target_id,
        limit=limit,
        offset=offset,
    )
    matched = [
        entry
        for entry in entries
        if (action is None or entry.action == action)
        and (actor is None or entry.actor_user_id == actor)
        and (target_id is None or entry.target_id == target_id)
    ]
    ordered = sorted(
        matched, key=lambda entry: (entry.occurred_at, str(entry.id)), reverse=True
    )
    expected = ordered[offset : offset + limit]

    page = select(entries, query)

    assert page.total == len(matched)
    assert [entry.id for entry in page.items] == [entry.id for entry in expected]


class FakeAdmin:
    def __init__(self) -> None:
        self.user_id = uuid4()
        self.premium: dict[UUID, bool] = {}
        self.entries: list[AuditEntry] = []
        self.fail_audit = False

    async def user(self, user_id: UUID) -> dict[str, object]:
        return {"account_status": "active"}

    async def lock_admin_guard(self) -> None:
        pass

    async def assignments(self, user_id: UUID | None = None) -> list[dict[str, object]]:
        return []

    async def save_assignment(
        self, user_id: UUID, role: str, valid_from: datetime, valid_to: datetime | None, _id: None
    ) -> dict[str, object]:
        return {
            "id": uuid4(),
            "user_id": user_id,
            "role_code": role,
            "valid_from": valid_from,
            "valid_to": valid_to,
        }

    async def change_permission(
        self, role: str, permission: str, remove: bool
    ) -> dict[str, object]:
        return {"role": role, "permissions": []}

    async def set_premium(self, user_id: UUID, value: bool) -> dict[str, object]:
        self.premium[user_id] = value
        return {"user_id": user_id, "is_premium": value}

    async def append(self, entry: AuditEntry) -> None:
        if self.fail_audit:
            raise AppError(
                503, ErrorCode.DATABASE_UNAVAILABLE, "Database operation could not complete."
            )
        self.entries.append(entry)

    @asynccontextmanager
    async def work(self) -> AsyncIterator[object]:
        repo = self
        before = deepcopy(self.premium)

        class Work:
            admin = repo
            audit = repo

        try:
            yield Work()
        except BaseException:
            self.premium = before
            raise


# Feature: identity-market-backend, Property 50: Audit entries are atomic with their
# administrative change
@given(st.lists(st.tuples(st.booleans(), st.booleans()), max_size=6))
def test_atomicity_across_administrative_operations(
    script: list[tuple[bool, bool]],
) -> None:
    repo = FakeAdmin()
    service = RbacService(repo.work, FakeClock(NOW))
    stored: dict[UUID, bool] = {}
    successes = 0

    for fail_audit, value in script:
        repo.fail_audit = fail_audit
        before = dict(repo.premium)
        succeeded = True
        try:
            asyncio.run(service.premium(repo.user_id, value, ACTOR))
        except AppError:
            succeeded = False

        if succeeded:
            stored = {repo.user_id: value}
            successes += 1
        assert repo.premium == (stored if succeeded else before)
        assert len(repo.entries) == successes


async def test_a_failing_audit_write_rolls_back_the_change() -> None:
    repo = FakeAdmin()
    repo.fail_audit = True
    service = RbacService(repo.work, FakeClock(NOW))

    with pytest.raises(AppError) as caught:
        await service.premium(repo.user_id, True, ACTOR)

    assert caught.value.code is ErrorCode.DATABASE_UNAVAILABLE
    assert repo.premium == {} and repo.entries == []


async def test_a_successful_change_writes_exactly_one_entry() -> None:
    repo = FakeAdmin()
    service = RbacService(repo.work, FakeClock(NOW))

    await service.premium(repo.user_id, True, ACTOR)

    assert len(repo.entries) == 1
    entry = repo.entries[0]
    assert entry.action is AuditAction.PREMIUM_CHANGED
    assert entry.actor_user_id == ACTOR
    assert entry.target_id == str(repo.user_id)
    assert entry.payload == {"is_premium": True}
