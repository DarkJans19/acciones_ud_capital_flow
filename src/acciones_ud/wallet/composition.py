"""MOD-04 composition and the funding port consumed by MOD-03."""

from decimal import Decimal

import httpx
from fastapi import FastAPI

from acciones_ud.market_data.application.notifier import Notifier
from acciones_ud.market_data.composition import build_senders, directory_uow, notification_uow
from acciones_ud.shared.domain.clock import SystemClock
from acciones_ud.wallet.adapters.inbound.http.routers import stripe_webhook, subscriptions, wallet
from acciones_ud.wallet.adapters.inbound.jobs.transfer_reconcile_job import TransferReconcileJob
from acciones_ud.wallet.adapters.outbound.alpaca.funding_client import AlpacaFundingClient
from acciones_ud.wallet.adapters.outbound.identity.account_reader import AccountStatusWriter
from acciones_ud.wallet.adapters.outbound.identity.contracted_plan_reader import (
    ContractedPlanReader,
)
from acciones_ud.wallet.adapters.outbound.notifications.balance_notifier import (
    BalanceNotifierAdapter,
)
from acciones_ud.wallet.adapters.outbound.persistence.unit_of_work import wallet_uow
from acciones_ud.wallet.adapters.outbound.stripe.stripe_client import StripeClient
from acciones_ud.wallet.application.funding_service import FundingService
from acciones_ud.wallet.application.stripe_webhook_service import StripeWebhookService
from acciones_ud.wallet.application.subscription_service import SubscriptionService
from acciones_ud.wallet.application.transfer_reconciler import TransferReconciler
from acciones_ud.wallet.application.wallet_service import WalletService


def register(app: FastAPI) -> None:
    settings, clock = app.state.settings, SystemClock()
    funding = AlpacaFundingClient(lambda: app.state.alpaca_broker)
    app.state.wallet_funding_port = funding
    app.state.wallet_clock = clock
    app.state.wallet_stripe_http = None

    def stripe_http() -> httpx.AsyncClient:
        if app.state.wallet_stripe_http is None:
            app.state.wallet_stripe_http = httpx.AsyncClient(base_url="https://api.stripe.com")
        client: httpx.AsyncClient = app.state.wallet_stripe_http
        return client

    stripe = StripeClient(
        stripe_http,
        settings.stripe_secret_key.get_secret_value() if settings.stripe_secret_key else "",
        settings.stripe_checkout_success_url,
        settings.stripe_checkout_cancel_url,
    )
    notifier = BalanceNotifierAdapter(
        directory_uow, Notifier(notification_uow, build_senders(settings), clock)
    )
    app.state.wallet_service = WalletService(wallet_uow, funding, clock, AccountStatusWriter())
    app.state.funding_service = FundingService(
        wallet_uow, funding, clock, Decimal(settings.wallet_max_transfer_amount)
    )
    app.state.subscription_service = SubscriptionService(
        wallet_uow,
        stripe,
        clock,
        settings.stripe_price_monthly_id or "",
        settings.stripe_price_annual_id or "",
    )
    app.state.stripe_webhook_service = StripeWebhookService(
        wallet_uow,
        settings.stripe_webhook_secret.get_secret_value() if settings.stripe_webhook_secret else "",
        stripe,
    )
    app.state.wallet_reconciler = TransferReconciler(wallet_uow, funding, notifier, clock)
    app.state.contracted_plan_reader = ContractedPlanReader(wallet_uow)
    for router in (wallet.router, subscriptions.router, stripe_webhook.router):
        app.include_router(router, prefix="/api/v1")


async def startup(app: FastAPI) -> None:
    settings = app.state.settings
    if settings.wallet_reconciler_enabled.lower() == "true":
        job = TransferReconcileJob(
            app.state.wallet_reconciler,
            int(settings.wallet_reconcile_interval_seconds),
            "wallet-reconcile",
        )
        app.state.wallet_job = job
        job.start()


async def shutdown(app: FastAPI) -> None:
    job = getattr(app.state, "wallet_job", None)
    if job:
        await job.stop()
    if app.state.wallet_stripe_http is not None:
        await app.state.wallet_stripe_http.aclose()
