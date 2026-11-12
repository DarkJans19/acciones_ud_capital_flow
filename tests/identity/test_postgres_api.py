import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pyotp
import pytest
import sqlalchemy as sa

from acciones_ud.identity.adapters.outbound.persistence import tables as t
from acciones_ud.identity.adapters.outbound.persistence.user_repository import UserRepository
from acciones_ud.identity.adapters.outbound.security.passwords import PasswordHasher
from acciones_ud.identity.domain.registration import build_new_user
from tests.identity.test_financial_profile import kyc_payload
from tests.identity.test_registration_security import payload

pytestmark = pytest.mark.db


def client(app: object) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://api.test")


async def register_and_login(http: httpx.AsyncClient, email: str, broker: bool = False) -> dict:
    body = {**payload(), "email": email}
    if broker:
        body.update(firm_name="Test Firm", license_number="TEST123")
    registered = await http.post(
        "/api/v1/auth/register/broker" if broker else "/api/v1/auth/register", json=body
    )
    assert registered.status_code == 201, registered.text
    return await login(http, email, "SafePassword123")


async def login(
    http: httpx.AsyncClient, email: str, password: str, recovery: str | None = None
) -> dict:
    challenge = await http.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert challenge.status_code == 200, challenge.text
    body = challenge.json()
    verification = {"mfa_token": body["mfa_token"]}
    if recovery:
        verification["recovery_code"] = recovery
    else:
        verification["code"] = pyotp.TOTP(body["totp_enrollment"]["secret"]).now()
    verified = await http.post("/api/v1/auth/mfa/verify", json=verification)
    assert verified.status_code == 200, verified.text
    return verified.json()


async def test_full_identity_interests_preferences_and_kyc(postgres_app: object) -> None:
    app = postgres_app
    async with client(app) as http, client(app) as other:
        enrolled = await register_and_login(http, app.state.test_tag + "-one@example.com")
        user_id = UUID(enrolled["user"]["user_id"])
        assert len(enrolled["recovery_codes"]) == 10
        await register_and_login(other, app.state.test_tag + "-two@example.com")
        me = await http.get("/api/v1/users/me")
        assert me.status_code == 200 and me.json()["roles"] == ["investor"]
        assert not app.state.provider_calls
        foreign_sessions = (await other.get("/api/v1/users/me/sessions")).json()
        assert (
            await http.delete("/api/v1/users/me/sessions/" + foreign_sessions[0]["session_id"])
        ).status_code == 404
        assert (await other.get("/api/v1/users/me")).status_code == 200
        assert (await http.get("/api/v1/users/preferences/portfolio")).json()[
            "view_type"
        ] == "table"
        async with app.state.sql_factory() as session:
            assert (
                await session.execute(
                    sa.select(sa.func.count())
                    .select_from(t.portfolio_view_settings)
                    .where(t.portfolio_view_settings.c.user_id == user_id)
                )
            ).scalar() == 0
            assert (
                (
                    await session.execute(
                        sa.select(t.users.c.password_hash).where(t.users.c.id == user_id)
                    )
                )
                .scalar_one()
                .startswith("$argon2id$")
            )
        assert (
            await http.put(
                "/api/v1/users/preferences/orders",
                json={
                    "default_order_type": "limit",
                    "daily_order_limit": 123,
                    "high_order_threshold_usd": "2000.00",
                    "extra_confirmation": False,
                },
            )
        ).status_code == 200
        assert (await other.get("/api/v1/users/preferences/orders")).json()[
            "daily_order_limit"
        ] == 50
        bad_patch = {
            "preferences": [
                {"event_type": "market_open", "channel": "email", "enabled": True},
                {"event_type": "market_open", "channel": "telegram", "enabled": True},
            ]
        }
        before = (await http.get("/api/v1/users/preferences/channels")).json()
        assert (
            await http.put("/api/v1/users/preferences/channels", json=bad_patch)
        ).status_code == 422
        assert (await http.get("/api/v1/users/preferences/channels")).json() == before
        assert (
            await http.put("/api/v1/users/me/telegram", json={"chat_id": "test-chat"})
        ).status_code == 200
        assert (
            await http.put("/api/v1/users/preferences/channels", json=bad_patch)
        ).status_code == 200
        symbol = "T" + uuid4().hex[:8].upper()
        app.state.test_symbols.append(symbol)
        async with app.state.sql_factory() as session, session.begin():
            await session.execute(
                sa.text("""INSERT INTO instruments
                (symbol,name,exchange,asset_class,status,sector,updated_at)
                VALUES (:symbol,'Test instrument','NYSE','us_equity',
                        'active','Technology',now())"""),
                {"symbol": symbol},
            )
        assert (
            await http.put(
                "/api/v1/users/me/interests",
                json={"interests": ["nyse", "technology", "NYSE"], "level": "beginner"},
            )
        ).json() == {"interests": ["NYSE", "Technology"], "level": "beginner"}
        assert (
            await http.put(
                "/api/v1/users/me/interests",
                json={"interests": ["Unknown"], "level": "experienced"},
            )
        ).status_code == 422
        assert (await http.get("/api/v1/users/me")).json()["interests"] == ["NYSE", "Technology"]
        body = kyc_payload()
        opened = await http.post("/api/v1/kyc/account", json=body)
        assert opened.status_code == 201, opened.text
        assert body["identity"]["tax_id"] not in opened.text
        document = app.state.provider_documents[-1]
        assert document["identity"]["annual_income_min"] == "50000.00"
        assert document["identity"]["total_net_worth_max"] == "249999.99"
        assert "annual_income_range" not in document["identity"]
        assert document["disclosures"]["employment_status"] == "student"
        calls = len(app.state.provider_calls)
        assert (await http.post("/api/v1/kyc/account", json=body)).status_code == 409
        assert len(app.state.provider_calls) == calls
        status = await http.get("/api/v1/kyc/status")
        assert status.json()["can_trade"] and not status.json()["stale"]
        async with app.state.sql_factory() as session:
            stored = (
                (
                    await session.execute(
                        sa.select(t.kyc_accounts).where(t.kyc_accounts.c.user_id == user_id)
                    )
                )
                .mappings()
                .one()
            )
            assert stored["tax_id_last4"] == "6789" and stored["status"] == "ACTIVE"
            assert body["identity"]["tax_id"] not in str(dict(stored))
        app.state.provider_outcomes.append((500, {"secret": "must not leak"}))
        degraded = (await http.get("/api/v1/kyc/status")).json()
        assert degraded["stale"] and degraded["can_trade"]
        app.state.provider_outcomes.append((500, {}))
        assert (await http.get("/api/v1/users/me")).json()["kyc_status_unavailable"]


@pytest.mark.parametrize(
    "status,code",
    [(422, "ALPACA_REJECTED"), (500, "ALPACA_UNAVAILABLE"), (429, "ALPACA_RATE_LIMITED")],
)
async def test_kyc_failure_cleans_reservation(postgres_app: object, status: int, code: str) -> None:
    app = postgres_app
    async with client(app) as http:
        verified = await register_and_login(http, app.state.test_tag + "-kyc@example.com")
        uid = UUID(verified["user"]["user_id"])
        app.state.provider_outcomes.append(
            (status, {"message": "Invalid tax 123-45-6789 123456789"})
        )
        result = await http.post("/api/v1/kyc/account", json=kyc_payload())
        assert result.json()["code"] == code
        assert "123-45-6789" not in result.text and "123456789" not in result.text
        async with app.state.sql_factory() as session:
            assert not (
                await session.execute(
                    sa.select(t.kyc_accounts).where(t.kyc_accounts.c.user_id == uid)
                )
            ).all()
        assert len(app.state.provider_calls) == 1


async def test_kyc_invalid_body_no_external_call(postgres_app: object) -> None:
    app = postgres_app
    async with client(app) as http:
        await register_and_login(http, app.state.test_tag + "-invalid@example.com")
        body = kyc_payload()
        body["identity"]["date_of_birth"] = datetime.now(UTC).date().isoformat()
        assert (await http.post("/api/v1/kyc/account", json=body)).status_code == 422
        body = kyc_payload()
        body["agreements"]["customer_agreement"] = False
        assert (await http.post("/api/v1/kyc/account", json=body)).status_code == 422
        assert app.state.provider_calls == []


async def test_sessions_refresh_and_mfa_recovery_race(postgres_app: object) -> None:
    app = postgres_app
    email = app.state.test_tag + "-sessions@example.com"
    async with client(app) as first, client(app) as second:
        enrolled = await register_and_login(first, email)
        codes = enrolled["recovery_codes"]

        async def recovery_login(http: httpx.AsyncClient) -> httpx.Response:
            challenge = (
                await http.post(
                    "/api/v1/auth/login", json={"email": email, "password": "SafePassword123"}
                )
            ).json()
            return await http.post(
                "/api/v1/auth/mfa/verify",
                json={"mfa_token": challenge["mfa_token"], "recovery_code": codes[0]},
            )

        outcomes = await asyncio.gather(recovery_login(first), recovery_login(second))
        assert sorted(r.status_code for r in outcomes) == [200, 401]
        await login(second, email, "SafePassword123", codes[1])
        listing = (await first.get("/api/v1/users/me/sessions")).json()
        assert sum(s["current"] for s in listing) == 1
        times = [datetime.fromisoformat(s["last_used_at"]) for s in listing]
        assert times == sorted(times, reverse=True)
        assert (await first.delete(f"/api/v1/users/me/sessions/{uuid4()}")).status_code == 404
        assert (await first.post("/api/v1/users/me/sessions/revoke-others")).json()[
            "revoked_count"
        ] >= 1
        assert (await second.get("/api/v1/users/me")).status_code == 401
        old = first.cookies.get("refresh_token")
        async with client(app) as a, client(app) as b:
            for http in (a, b):
                http.cookies.set("refresh_token", old, path="/api/v1/auth")
            results = await asyncio.gather(
                a.post("/api/v1/auth/refresh"), b.post("/api/v1/auth/refresh")
            )
            assert sorted(r.status_code for r in results) == [200, 401]
        assert (await first.get("/api/v1/users/me")).status_code == 401


async def test_future_cancellation_preserves_dates_and_is_never_effective(
    postgres_app: object,
) -> None:
    app = postgres_app
    admin_email = app.state.test_tag + "-admin@example.com"
    record, _ = build_new_user("administrator", {**payload(), "email": admin_email})
    record.update(
        password_hash=PasswordHasher().hash("SafePassword123"), terms_accepted_at=datetime.now(UTC)
    )
    async with app.state.sql_factory() as session, session.begin():
        admin_id = await UserRepository(session).insert(record, "administrator")
    async with client(app) as admin, client(app) as broker:
        await login(admin, admin_email, "SafePassword123")
        registered = await register_and_login(
            broker, app.state.test_tag + "-broker@example.com", broker=True
        )
        uid = registered["user"]["user_id"]
        assert (await broker.get("/api/v1/users/preferences/orders")).status_code == 403
        assert (await admin.post(f"/api/v1/admin/users/{uid}/broker-activation")).status_code == 200
        assert (await broker.get("/api/v1/users/preferences/orders")).status_code == 200
        start = datetime.now(UTC) + timedelta(days=1)
        end = start + timedelta(days=1)
        assigned = await admin.post(
            f"/api/v1/admin/users/{uid}/roles",
            json={
                "role": "administrator",
                "valid_from": start.isoformat(),
                "valid_to": end.isoformat(),
            },
        )
        assert assigned.status_code == 201, assigned.text
        aid = assigned.json()["id"]
        cancelled = await admin.post(f"/api/v1/admin/users/{uid}/roles/{aid}/revoke")
        assert cancelled.status_code == 200, cancelled.text
        body = cancelled.json()
        assert body["status"] == "CANCELLED" and not body["effective"]
        assert (
            body["valid_from"] == assigned.json()["valid_from"]
            and body["valid_to"] == assigned.json()["valid_to"]
        )
        assert body["cancelled_by"] == str(admin_id) and body["cancelled_at"]
        assert (
            await admin.put(
                f"/api/v1/admin/users/{uid}/roles/{aid}",
                json={"valid_from": datetime.now(UTC).isoformat(), "valid_to": None},
            )
        ).status_code == 409
        assert (await broker.get("/api/v1/users/me")).json()["roles"] == [
            "broker",
            "investor",
        ]
        from acciones_ud.identity.adapters.outbound.persistence.auth_context_repository import (
            AuthContextRepository,
        )
        from tests.support.clock import FakeClock

        async with app.state.sql_factory() as session:
            sid = (
                await session.execute(
                    sa.select(t.sessions.c.id).where(
                        t.sessions.c.user_id == UUID(uid), t.sessions.c.revoked_at.is_(None)
                    )
                )
            ).scalar_one()
            future = await AuthContextRepository(
                session, FakeClock(start + timedelta(hours=1))
            ).get(UUID(uid), sid)
            assert future is not None and future.roles == frozenset({"broker"})
            assert "admin:users" not in future.permissions


async def test_totp_reuse_and_regeneration_concurrency(postgres_app: object) -> None:
    app = postgres_app
    email = app.state.test_tag + "-totp@example.com"
    async with client(app) as first, client(app) as second:
        assert (
            await first.post("/api/v1/auth/register", json={**payload(), "email": email})
        ).status_code == 201
        challenges = await asyncio.gather(
            *(
                http.post(
                    "/api/v1/auth/login", json={"email": email, "password": "SafePassword123"}
                )
                for http in (first, second)
            )
        )
        documents = [r.json() for r in challenges]
        assert (
            documents[0]["totp_enrollment"]["secret"] == documents[1]["totp_enrollment"]["secret"]
        )
        code = pyotp.TOTP(documents[0]["totp_enrollment"]["secret"]).now()
        outcomes = await asyncio.gather(
            *(
                http.post(
                    "/api/v1/auth/mfa/verify", json={"mfa_token": doc["mfa_token"], "code": code}
                )
                for http, doc in zip((first, second), documents, strict=True)
            )
        )
        assert sorted(r.status_code for r in outcomes) == [200, 401]
        winner = first if outcomes[0].status_code == 200 else second
        uid = UUID(next(r.json()["user"]["user_id"] for r in outcomes if r.status_code == 200))
        regenerated = await asyncio.gather(
            *(winner.post("/api/v1/users/me/mfa/recovery-codes") for _ in range(2))
        )
        assert all(
            r.status_code == 200 and len(r.json()["recovery_codes"]) == 10 for r in regenerated
        )
        async with app.state.sql_factory() as session:
            remaining = (
                await session.execute(
                    sa.select(sa.func.count())
                    .select_from(t.mfa_recovery_codes)
                    .where(
                        t.mfa_recovery_codes.c.user_id == uid,
                        t.mfa_recovery_codes.c.invalidated_at.is_(None),
                    )
                )
            ).scalar()
            assert remaining == 10
            failed = (
                (
                    await session.execute(
                        sa.select(t.mfa_challenges.c.failed_attempts).where(
                            t.mfa_challenges.c.user_id == uid
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert sorted(failed) == [0, 1]


async def test_kyc_reservation_concurrency_and_stale_recovery(postgres_app: object) -> None:
    app = postgres_app
    async with client(app) as http:
        issued = await register_and_login(http, app.state.test_tag + "-reserve@example.com")
        uid = UUID(issued["user"]["user_id"])
        async with app.state.sql_factory() as session, session.begin():
            await session.execute(
                t.kyc_accounts.insert().values(
                    user_id=uid, reserved_at=datetime.now(UTC) - timedelta(seconds=121)
                )
            )
        responses = await asyncio.gather(
            *(http.post("/api/v1/kyc/account", json=kyc_payload()) for _ in range(2))
        )
        assert sorted(r.status_code for r in responses) == [201, 409]
        assert len(app.state.provider_calls) == 1
        await http.get("/api/v1/kyc/status")
        async with app.state.sql_factory() as session:
            before = (
                await session.execute(
                    sa.select(t.kyc_accounts.c.status_updated_at).where(
                        t.kyc_accounts.c.user_id == uid
                    )
                )
            ).scalar_one()
        await http.get("/api/v1/kyc/status")
        async with app.state.sql_factory() as session:
            after = (
                await session.execute(
                    sa.select(t.kyc_accounts.c.status_updated_at).where(
                        t.kyc_accounts.c.user_id == uid
                    )
                )
            ).scalar_one()
        assert before == after


async def test_last_administrator_race_and_fresh_permissions(postgres_app: object) -> None:
    app = postgres_app
    ids = []
    for suffix in ("admin-one", "admin-two"):
        email = app.state.test_tag + "-" + suffix + "@example.com"
        record, _ = build_new_user("administrator", {**payload(), "email": email})
        record.update(
            password_hash=PasswordHasher().hash("SafePassword123"),
            terms_accepted_at=datetime.now(UTC),
        )
        async with app.state.sql_factory() as session, session.begin():
            ids.append(await UserRepository(session).insert(record, "administrator"))
    async with client(app) as one, client(app) as two:
        await login(one, app.state.test_tag + "-admin-one@example.com", "SafePassword123")
        await login(two, app.state.test_tag + "-admin-two@example.com", "SafePassword123")
        async with app.state.sql_factory() as session, session.begin():
            # This test runs exclusively in disposable PostgreSQL. Restore bootstrap dates below.
            bootstrap = (
                (
                    await session.execute(
                        sa.select(t.role_assignments).where(
                            t.role_assignments.c.role_code == "administrator",
                            t.role_assignments.c.user_id.not_in(ids),
                        )
                    )
                )
                .mappings()
                .all()
            )
            for row in bootstrap:
                await session.execute(
                    t.role_assignments.update()
                    .where(t.role_assignments.c.id == row["id"])
                    .values(valid_to=datetime.now(UTC))
                )
            assignment_ids = [
                (
                    await session.execute(
                        sa.select(t.role_assignments.c.id).where(
                            t.role_assignments.c.user_id == uid
                        )
                    )
                ).scalar_one()
                for uid in ids
            ]
        try:
            responses = await asyncio.gather(
                *(
                    http.post(f"/api/v1/admin/users/{uid}/roles/{aid}/revoke")
                    for http, uid, aid in zip((one, two), ids, assignment_ids, strict=True)
                )
            )
            assert sorted(r.status_code for r in responses) == [200, 409]
            loser = one if responses[0].status_code == 200 else two
            survivor = two if responses[0].status_code == 200 else one
            assert (await loser.get("/api/v1/admin/roles")).status_code == 403
            assert (await loser.get("/api/v1/users/me")).status_code == 200
            assert (await survivor.get("/api/v1/admin/roles")).status_code == 200
        finally:
            async with app.state.sql_factory() as session, session.begin():
                for row in bootstrap:
                    await session.execute(
                        t.role_assignments.update()
                        .where(t.role_assignments.c.id == row["id"])
                        .values(valid_to=row["valid_to"])
                    )


async def test_administrator_registration_and_permission_changes(postgres_app: object) -> None:
    app = postgres_app
    actor_email = app.state.test_tag + "-actor@example.com"
    record, _ = build_new_user("administrator", {**payload(), "email": actor_email})
    record.update(
        password_hash=PasswordHasher().hash("SafePassword123"), terms_accepted_at=datetime.now(UTC)
    )
    async with app.state.sql_factory() as session, session.begin():
        await UserRepository(session).insert(record, "administrator")
    async with client(app) as admin, client(app) as investor:
        await login(admin, actor_email, "SafePassword123")
        created = await admin.post(
            "/api/v1/admin/users/administrators",
            json={
                **payload(),
                "email": app.state.test_tag + "-created-admin@example.com",
                "role": "broker",
            },
        )
        assert created.status_code == 201
        assignments = (
            await admin.get(f"/api/v1/admin/users/{created.json()['user_id']}/roles")
        ).json()
        assert len(assignments) == 1 and assignments[0]["role"] == "administrator"
        await register_and_login(investor, app.state.test_tag + "-permissions@example.com")
        try:
            removed = await admin.delete("/api/v1/admin/roles/investor/permissions/account:manage")
            assert (
                removed.status_code == 200 and "account:manage" not in removed.json()["permissions"]
            )
            assert (await investor.get("/api/v1/users/preferences/orders")).status_code == 403
            assert (await investor.get("/api/v1/users/me")).status_code == 200
        finally:
            restored = await admin.post(
                "/api/v1/admin/roles/investor/permissions",
                json={"permission_code": "account:manage"},
            )
            assert restored.status_code == 200
        assert (await investor.get("/api/v1/users/preferences/orders")).status_code == 200


async def test_registration_partial_write_is_rolled_back(postgres_app: object) -> None:
    from acciones_ud.shared.domain.errors import AppError
    from acciones_ud.shared.infrastructure.db import unit_of_work

    app = postgres_app
    email = app.state.test_tag + "-rollback@example.com"
    record, _ = build_new_user("investor", {**payload(), "email": email})
    record.update(
        password_hash=PasswordHasher().hash("SafePassword123"), terms_accepted_at=datetime.now(UTC)
    )
    with pytest.raises(AppError) as failed:
        async with unit_of_work() as session:
            # User insert succeeds; role FK fails next. Neither user nor preferences may survive.
            await UserRepository(session).insert(record, "unknown-role")
    assert failed.value.code == "DATABASE_UNAVAILABLE"
    async with app.state.sql_factory() as session:
        assert not (
            await session.execute(
                sa.select(t.users.c.id).where(t.users.c.email_normalized == email)
            )
        ).all()
