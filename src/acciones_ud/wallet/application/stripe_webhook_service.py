import json
import logging
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from acciones_ud.shared.domain.errors import AppError, ErrorCode
from acciones_ud.wallet.application.dtos import timestamp
from acciones_ud.wallet.domain.errors import InvalidSignatureError
from acciones_ud.wallet.domain.model import Payment, Raw, StripeEvent, Subscription
from acciones_ud.wallet.domain.ports import StripePort, WalletWork, WalletWorkFactory
from acciones_ud.wallet.domain.stripe_signature import verify
from acciones_ud.wallet.domain.subscriptions import premium_effect

logger = logging.getLogger(__name__)


class StripeWebhookService:
    def __init__(self, uow: WalletWorkFactory, secret: str, stripe: StripePort) -> None:
        self.uow, self.secret, self.stripe = uow, secret, stripe

    async def handle(
        self, raw_body: bytes, signature_header: str | None, now: datetime
    ) -> dict[str, bool]:
        verify(raw_body, signature_header, self.secret, now)
        try:
            event = json.loads(raw_body)
            event_id, kind, data = str(event["id"]), str(event["type"]), event["data"]["object"]
            created = timestamp(event["created"])
            if not isinstance(data, dict) or created is None:
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise InvalidSignatureError() from None
        try:
            async with self.uow() as work:
                if not await work.events.insert(StripeEvent(event_id, kind, "applied", now)):
                    return {"received": True}
                subscription = await self._match(work, kind, data)
                if subscription is None:
                    await work.events.save(StripeEvent(event_id, kind, "unassociated", now))
                    return {"received": True}
                await work.lock_user(subscription.user_id)
                # Re-read after locking: two distinct events must compare against committed state.
                subscription = await work.subscriptions.get(id=subscription.id)
                assert subscription is not None
                if kind.startswith("invoice."):
                    await self._invoice(work, subscription, kind, data, created)
                elif kind == "checkout.session.completed" or kind.startswith(
                    "customer.subscription."
                ):
                    if subscription.stripe_event_created_at and created < (
                        subscription.stripe_event_created_at
                    ):
                        await work.events.save(StripeEvent(event_id, kind, "stale", now))
                    else:
                        if kind == "checkout.session.completed":
                            external_id = data.get("subscription")
                            if isinstance(external_id, dict):
                                data = external_id
                            elif external_id:
                                data = await self.stripe.get_subscription(str(external_id))
                            else:
                                await work.events.save(
                                    StripeEvent(event_id, kind, "unassociated", now)
                                )
                                return {"received": True}
                        status = (
                            "canceled"
                            if kind == "customer.subscription.deleted"
                            else data["status"]
                        )
                        updated = replace(
                            subscription,
                            stripe_subscription_id=str(data["id"]),
                            stripe_customer_id=data.get("customer")
                            or subscription.stripe_customer_id,
                            status=status,
                            current_period_start=timestamp(data.get("current_period_start")),
                            current_period_end=timestamp(data.get("current_period_end")),
                            cancel_at_period_end=bool(data.get("cancel_at_period_end", False)),
                            stripe_event_created_at=created,
                        )
                        await work.subscriptions.save(updated)
                        if status != subscription.status:
                            effect = premium_effect(status)
                            if effect is not None:
                                await work.premium.set_premium(subscription.user_id, effect)
        except AppError as exc:
            if exc.code == ErrorCode.DATABASE_UNAVAILABLE:
                logger.error(
                    "Stripe event not applied", extra={"event_id": event_id, "applied": False}
                )
            raise
        return {"received": True}

    async def _match(self, work: WalletWork, kind: str, data: Raw) -> Subscription | None:
        if kind == "checkout.session.completed":
            return await work.subscriptions.get(stripe_checkout_session_id=str(data["id"]))
        external = data.get("subscription") if kind.startswith("invoice.") else data.get("id")
        if isinstance(external, dict):
            external = external.get("id")
        if external:
            result = await work.subscriptions.get(stripe_subscription_id=str(external))
            if result:
                return result
        customer = data.get("customer")
        if customer:
            result = await work.subscriptions.get(stripe_customer_id=str(customer))
            if result:
                return result
        # Initial subscription event may arrive before Checkout's completed event.
        # Only associate its trusted metadata to a checkout already stored for that investor.
        metadata = data.get("metadata") or {}
        try:
            user_id = UUID(metadata["user_id"])
        except (ValueError, KeyError, TypeError):
            return None
        candidates = await work.subscriptions.list(user_id=user_id, status="pending_checkout")
        return candidates[0] if len(candidates) == 1 else None

    async def _invoice(
        self, work: WalletWork, subscription: Subscription, kind: str, data: Raw, created: datetime
    ) -> None:
        if kind not in {"invoice.paid", "invoice.payment_failed"}:
            return
        lines = data.get("lines", {}).get("data", [])
        interval = lines[0].get("period", {}) if lines else {}
        amount = Decimal(
            str(data.get("amount_paid" if kind == "invoice.paid" else "amount_due", 0))
        )
        existing = await work.payments.get(stripe_invoice_id=str(data["id"]))
        if existing and (
            created < existing.occurred_at
            or (existing.result == "paid" and kind == "invoice.payment_failed")
        ):
            return
        payment = Payment(
            existing.id if existing else uuid4(),
            subscription.user_id,
            subscription.id,
            str(data["id"]),
            subscription.plan,
            amount / 100,
            str(data.get("currency") or "USD").upper(),
            timestamp(interval.get("start")),
            timestamp(interval.get("end")),
            "paid" if kind == "invoice.paid" else "failed",
            created,
        )
        if existing:
            await work.payments.save(payment)
        else:
            await work.payments.insert(payment)
