"""Composición de puertos y adaptadores de identidad."""

import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from uuid import UUID

from fastapi import FastAPI, Request

from acciones_ud.config.settings import kyc_refresh_config
from acciones_ud.identity.adapters.inbound.jobs.kyc_refresh_job import KycRefreshJob
from acciones_ud.identity.adapters.outbound.alpaca.accounts_client import AlpacaAccountsClient
from acciones_ud.identity.adapters.outbound.persistence.account_repository import AccountRepository
from acciones_ud.identity.adapters.outbound.persistence.audit_log_repository import (
    AuditLogRepository,
)
from acciones_ud.identity.adapters.outbound.persistence.auth_context_repository import (
    AuthContextRepository,
)
from acciones_ud.identity.adapters.outbound.persistence.auth_repository import AuthRepository
from acciones_ud.identity.adapters.outbound.persistence.kyc_repository import KycRepository
from acciones_ud.identity.adapters.outbound.persistence.rbac_repository import RbacRepository
from acciones_ud.identity.adapters.outbound.persistence.user_directory_repository import (
    UserDirectoryRepository,
)
from acciones_ud.identity.adapters.outbound.persistence.user_repository import UserRepository
from acciones_ud.identity.adapters.outbound.security.cipher import SecretCipher
from acciones_ud.identity.adapters.outbound.security.passwords import PasswordHasher
from acciones_ud.identity.adapters.outbound.security.tokens import AccessTokenCodec, TokenGenerator
from acciones_ud.identity.adapters.outbound.security.totp import TotpProvider
from acciones_ud.identity.application.account import AccountService
from acciones_ud.identity.application.account_info import AccountInfoService
from acciones_ud.identity.application.audit_log import AuditLogService
from acciones_ud.identity.application.broker_activation import BrokerActivationService
from acciones_ud.identity.application.kyc import KycService
from acciones_ud.identity.application.kyc_reconcile import KycReconcileService
from acciones_ud.identity.application.login import AuthService
from acciones_ud.identity.application.rbac_admin import RbacService
from acciones_ud.identity.application.register import RegistrationService
from acciones_ud.identity.application.sessions import SessionService
from acciones_ud.identity.application.user_directory import UserDirectoryService
from acciones_ud.identity.domain.account_ports import AccountWork
from acciones_ud.identity.domain.admin_ports import AdminWork, DirectoryWork
from acciones_ud.identity.domain.auth_ports import AuthWork
from acciones_ud.identity.domain.kyc_ports import KycWork
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.identity.domain.ports import IdentityUnitOfWork
from acciones_ud.shared.domain.clock import SystemClock


def register(app: FastAPI) -> None:
    from acciones_ud.identity.adapters.inbound.http.routers import (
        admin,
        auth,
        kyc,
        preferences,
        sessions,
        users,
    )

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    app.include_router(sessions.router, prefix="/api/v1")
    app.include_router(users.router, prefix="/api/v1")
    app.include_router(preferences.router, prefix="/api/v1")
    app.include_router(kyc.router, prefix="/api/v1")


@lru_cache
def password_hasher() -> PasswordHasher:
    return PasswordHasher()


@asynccontextmanager
async def identity_uow() -> AsyncIterator[IdentityUnitOfWork]:
    from acciones_ud.shared.infrastructure.db import unit_of_work

    async with unit_of_work() as session:

        class Work:
            users = UserRepository(session)
            audit = AuditLogRepository(session)

        yield Work()


def registration_service(request: Request) -> RegistrationService:
    override = getattr(request.app.state, "registration_service", None)
    if isinstance(override, RegistrationService):
        return override
    return RegistrationService(identity_uow, password_hasher(), SystemClock())


def token_codec(request: Request) -> AccessTokenCodec:
    settings = request.app.state.settings
    return AccessTokenCodec(
        settings.jwt_secret.get_secret_value(),
        int(settings.access_token_ttl_seconds),
        SystemClock(),
    )


async def auth_context(request: Request, user_id: UUID, session_id: UUID) -> CurrentUser | None:
    from acciones_ud.shared.infrastructure.db import unit_of_work

    async with unit_of_work() as session:
        return await AuthContextRepository(session, SystemClock()).get(user_id, session_id)


@asynccontextmanager
async def auth_uow() -> AsyncIterator[AuthWork]:
    from acciones_ud.shared.infrastructure.db import unit_of_work

    async with unit_of_work() as session:

        class Work:
            auth = AuthRepository(session)

        yield Work()


def auth_service(request: Request) -> AuthService:
    override = getattr(request.app.state, "auth_service", None)
    if isinstance(override, AuthService):
        return override
    settings = request.app.state.settings
    return AuthService(
        auth_uow,
        password_hasher(),
        SecretCipher(settings.totp_encryption_key.get_secret_value()),
        token_codec(request),
        TokenGenerator(),
        TotpProvider(),
        SystemClock(),
        int(settings.refresh_token_ttl_seconds),
    )


def session_service(request: Request) -> SessionService:
    override = getattr(request.app.state, "session_service", None)
    if isinstance(override, SessionService):
        return override
    settings = request.app.state.settings
    return SessionService(
        auth_uow,
        token_codec(request),
        TokenGenerator(),
        SystemClock(),
        int(settings.access_token_ttl_seconds),
        int(settings.refresh_token_ttl_seconds),
    )


async def startup(app: FastAPI) -> None:
    config = kyc_refresh_config(app.state.settings)
    if not config.enabled:
        return
    job = KycRefreshJob(
        AlpacaAccountsClient(app.state.alpaca_broker),
        kyc_uow,
        SystemClock(),
        config.interval_seconds,
    )
    job.start()
    app.state.kyc_refresh_job = job


async def shutdown(app: FastAPI) -> None:
    job = getattr(app.state, "kyc_refresh_job", None)
    if job is not None:
        await job.stop()
        app.state.kyc_refresh_job = None
    database = sys.modules.get("acciones_ud.shared.infrastructure.db")
    if database is not None:
        await database.engine.dispose()


@asynccontextmanager
async def admin_uow() -> AsyncIterator[AdminWork]:
    from acciones_ud.shared.infrastructure.db import unit_of_work

    async with unit_of_work() as session:

        class Work:
            admin = RbacRepository(session)
            audit = AuditLogRepository(session)

        yield Work()


def rbac_service(request: Request) -> RbacService:
    override = getattr(request.app.state, "rbac_service", None)
    if isinstance(override, RbacService):
        return override
    return RbacService(admin_uow, SystemClock())


def broker_activation_service(request: Request) -> BrokerActivationService:
    override = getattr(request.app.state, "broker_activation_service", None)
    if isinstance(override, BrokerActivationService):
        return override
    return BrokerActivationService(admin_uow, SystemClock())


@asynccontextmanager
async def directory_uow() -> AsyncIterator[DirectoryWork]:
    from acciones_ud.shared.infrastructure.db import unit_of_work

    async with unit_of_work() as session:

        class Work:
            directory = UserDirectoryRepository(session)

        yield Work()


def user_directory_service(request: Request) -> UserDirectoryService:
    override = getattr(request.app.state, "user_directory_service", None)
    if isinstance(override, UserDirectoryService):
        return override
    return UserDirectoryService(directory_uow, SystemClock())


def audit_log_service(request: Request) -> AuditLogService:
    override = getattr(request.app.state, "audit_log_service", None)
    if isinstance(override, AuditLogService):
        return override
    return AuditLogService(admin_uow)


@asynccontextmanager
async def account_uow() -> AsyncIterator[AccountWork]:
    from acciones_ud.shared.infrastructure.db import unit_of_work

    async with unit_of_work() as session:

        class Work:
            account = AccountRepository(session)

        yield Work()


def account_service(request: Request) -> AccountService:
    override = getattr(request.app.state, "account_service", None)
    if isinstance(override, AccountService):
        return override
    return AccountService(account_uow)


@asynccontextmanager
async def kyc_uow() -> AsyncIterator[KycWork]:
    from acciones_ud.shared.infrastructure.db import unit_of_work

    async with unit_of_work() as session:

        class Work:
            kyc = KycRepository(session, SystemClock())
            audit = AuditLogRepository(session)

        yield Work()


def kyc_service(request: Request) -> KycService:
    override = getattr(request.app.state, "kyc_service", None)
    if isinstance(override, KycService):
        return override
    return KycService(kyc_uow, AlpacaAccountsClient(request.app.state.alpaca_broker), SystemClock())


def kyc_reconcile_service(request: Request) -> KycReconcileService:
    override = getattr(request.app.state, "kyc_reconcile_service", None)
    if isinstance(override, KycReconcileService):
        return override
    return KycReconcileService(
        kyc_uow, AlpacaAccountsClient(request.app.state.alpaca_broker), SystemClock()
    )


def account_info_service(request: Request) -> AccountInfoService:
    override = getattr(request.app.state, "account_info_service", None)
    if isinstance(override, AccountInfoService):
        return override
    config = kyc_refresh_config(request.app.state.settings)
    return AccountInfoService(
        account_uow,
        kyc_uow,
        AlpacaAccountsClient(request.app.state.alpaca_broker),
        config.cache_ttl_seconds,
        SystemClock(),
    )
