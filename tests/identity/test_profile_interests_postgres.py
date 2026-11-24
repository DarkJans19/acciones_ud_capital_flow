import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa

from acciones_ud.identity.adapters.outbound.persistence import tables as t
from acciones_ud.identity.adapters.outbound.persistence.account_repository import AccountRepository
from acciones_ud.identity.adapters.outbound.persistence.kyc_repository import KycRepository
from acciones_ud.identity.application.account import AccountService
from acciones_ud.shared.domain.clock import SystemClock
from acciones_ud.shared.domain.errors import AppError
from tests.identity.test_financial_profile import kyc_payload
from tests.identity.test_postgres_api import client, login, register_and_login
from tests.identity.test_registration_security import payload

pytestmark = pytest.mark.db


async def test_real_catalog_registration_profile_and_kyc_lock(postgres_app):
    app = postgres_app
    symbol = "T" + uuid4().hex[:8].upper()
    sector = "Sector-" + uuid4().hex[:10]
    app.state.test_symbols.append(symbol)
    async with app.state.sql_factory() as session, session.begin():
        await session.execute(
            sa.text("""
            INSERT INTO instruments
            (symbol, name, exchange, asset_class, status, sector, updated_at)
            VALUES (:symbol, 'Test', 'NYSE', 'us_equity', 'active', :sector, now())
        """),
            {"symbol": symbol, "sector": sector},
        )
    email = app.state.test_tag + "-catalog@example.com"
    async with client(app) as http, client(app) as other:
        options = await http.get("/api/v1/auth/interest-options")
        assert options.status_code == 200
        assert "NYSE" in options.json()["markets"]
        assert sector in options.json()["sectors"]
        assert app.state.provider_calls == []
        created = await http.post(
            "/api/v1/auth/register",
            json={
                **payload(),
                "email": email,
                "interests": ["nyse", sector.lower(), "NYSE"],
            },
        )
        assert created.status_code == 201, created.text
        uid = UUID(created.json()["user_id"])
        await login(http, email, "SafePassword123")
        await register_and_login(other, app.state.test_tag + "-foreign@example.com")
        before = (await other.get("/api/v1/users/me")).json()
        assert (await http.get("/api/v1/users/me")).json()["interests"] == ["NYSE", sector]
        replaced = await http.put(
            "/api/v1/users/me/interests",
            json={
                "interests": [sector.lower(), "NYSE", sector],
                "level": "beginner",
            },
        )
        assert replaced.status_code == 200
        assert replaced.json()["interests"] == [sector, "NYSE"]
        assert (await http.get("/api/v1/users/me")).json()["interests"] == [sector, "NYSE"]

        # Independent partial writes are serialized; neither can clobber omitted fields.
        results = await asyncio.gather(
            http.patch("/api/v1/users/me", json={"first_names": "María"}),
            http.patch("/api/v1/users/me", json={"country": "us", "phone": "+15555550123"}),
        )
        assert [r.status_code for r in results] == [200, 200]
        me = (await http.get("/api/v1/users/me")).json()
        assert me["first_names"] == "María" and me["last_names"] == "Perez"
        assert me["country"] == "US" and me["phone"] == "+15555550123"
        assert (await other.get("/api/v1/users/me")).json() == before
        async with app.state.sql_factory() as session:
            row = (
                (await session.execute(sa.select(t.users).where(t.users.c.id == uid)))
                .mappings()
                .one()
            )
            assert row["first_names"] == "María" and row["country"] == "US"
            assert row["interests"] == [sector, "NYSE"] and row["updated_at"] > row["created_at"]

        # Failed mixed patches never commit the allowed part.
        assert (
            await http.patch(
                "/api/v1/users/me",
                json={
                    "first_names": "Not persisted",
                    "roles": ["administrator"],
                },
            )
        ).status_code == 422
        assert (await http.get("/api/v1/users/me")).json()["first_names"] == "María"
        assert (await http.post("/api/v1/kyc/account", json=kyc_payload())).status_code == 201
        calls = list(app.state.provider_calls)
        rejected = await http.patch("/api/v1/users/me", json={"last_names": "Changed"})
        assert rejected.status_code == 409 and rejected.json()["code"] == "PROFILE_KYC_LOCKED"
        assert app.state.provider_calls == calls
        async with app.state.sql_factory() as session:
            assert (
                await session.scalar(sa.select(t.users.c.last_names).where(t.users.c.id == uid))
                == "Perez"
            )


async def test_legacy_data_is_retained_only_for_owner(postgres_app):
    app = postgres_app
    legacy = "Historical-" + uuid4().hex[:10]
    async with client(app) as http, client(app) as other:
        enrolled = await register_and_login(http, app.state.test_tag + "-legacy@example.com")
        await register_and_login(other, app.state.test_tag + "-new@example.com")
        uid = UUID(enrolled["user"]["user_id"])
        async with app.state.sql_factory() as session, session.begin():
            await session.execute(
                t.users.update().where(t.users.c.id == uid).values(interests=[legacy])
            )
        assert (await http.get("/api/v1/users/me")).json()["interests"] == [legacy]
        body = {"interests": [legacy.lower(), "NYSE"], "level": "beginner"}
        retained = await http.put("/api/v1/users/me/interests", json=body)
        assert retained.status_code == 200 and retained.json()["interests"] == [legacy, "NYSE"]
        assert (await other.put("/api/v1/users/me/interests", json=body)).status_code == 422
        assert legacy not in str((await http.get("/api/v1/auth/interest-options")).json())
        invalid_email = app.state.test_tag + "-unknown@example.com"
        result = await http.post(
            "/api/v1/auth/register",
            json={
                **payload(),
                "email": invalid_email,
                "interests": [legacy],
            },
        )
        assert result.status_code == 422
        async with app.state.sql_factory() as session:
            assert (
                await session.scalar(
                    sa.select(t.users.c.id).where(t.users.c.email_normalized == invalid_email)
                )
                is None
            )


async def test_uncommitted_kyc_reservation_serializes_profile_update(postgres_app):
    app = postgres_app
    async with client(app) as http:
        enrolled = await register_and_login(http, app.state.test_tag + "-race@example.com")
    uid = UUID(enrolled["user"]["user_id"])
    attempted = asyncio.Event()

    class ObservedAccountRepository(AccountRepository):
        async def user(self, user_id, *, lock=False):
            attempted.set()
            return await super().user(user_id, lock=lock)

    @asynccontextmanager
    async def work():
        async with app.state.sql_factory() as session, session.begin():
            yield type("Work", (), {"account": ObservedAccountRepository(session)})()

    # KYC holds an uncommitted user lock and reservation. The profile query
    # must wait and then observe the committed row, not a previous empty state.
    async with app.state.sql_factory() as session, session.begin():
        assert await KycRepository(session, SystemClock()).reserve(uid, datetime.now(UTC))
        task = asyncio.create_task(
            AccountService(work).update_profile(uid, {"first_names": "Must not persist"})
        )
        await asyncio.wait_for(attempted.wait(), timeout=5)
    with pytest.raises(AppError) as caught:
        await asyncio.wait_for(task, timeout=5)
    assert caught.value.code == "PROFILE_KYC_LOCKED"
    async with app.state.sql_factory() as session:
        assert (
            await session.scalar(sa.select(t.users.c.first_names).where(t.users.c.id == uid))
            == "Ana"
        )
    assert app.state.provider_calls == []


async def test_profile_write_failure_rolls_back(postgres_app, monkeypatch):
    app = postgres_app
    original = AccountRepository.update_user

    async def fail_after_write(self, user_id, values):
        from acciones_ud.shared.domain.errors import ErrorCode

        await original(self, user_id, values)
        raise AppError(503, ErrorCode.DATABASE_UNAVAILABLE, "Simulated write failure.")

    async with client(app) as http:
        await register_and_login(http, app.state.test_tag + "-profile-rollback@example.com")
        monkeypatch.setattr(AccountRepository, "update_user", fail_after_write)
        result = await http.patch("/api/v1/users/me", json={"first_names": "Rolled back"})
        assert result.status_code == 503 and result.json()["code"] == "DATABASE_UNAVAILABLE"
        assert (await http.get("/api/v1/users/me")).json()["first_names"] == "Ana"


@pytest.mark.parametrize(
    "kind,value",
    [
        ("PASSPORT", "Ab829461"),
        ("PASSPORT", "842617395"),
        ("COL_NIT", "900.123.456-7"),
    ],
)
async def test_document_is_forwarded_without_destructive_normalization(postgres_app, kind, value):
    app = postgres_app
    async with client(app) as http:
        await register_and_login(http, app.state.test_tag + "-document@example.com")
        body = kyc_payload()
        body["identity"].update(
            tax_id_type=kind,
            tax_id=value,
            country_of_tax_residence="COL",
            country_of_citizenship="COL",
        )
        response = await http.post("/api/v1/kyc/account", json=body)
        assert response.status_code == 201, response.text
        assert value not in response.text
        document = app.state.provider_documents[-1]["identity"]
        assert document["tax_id"] == value and document["tax_id_type"] == kind
        assert len(app.state.provider_calls) == 1
