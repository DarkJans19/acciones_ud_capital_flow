from dataclasses import replace
from uuid import UUID, uuid4

from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from acciones_ud.wallet.application.dtos import Page, invalid, paginate
from acciones_ud.wallet.application.funding_service import not_found
from acciones_ud.wallet.domain.model import Payment, Plan, Raw, Subscription
from acciones_ud.wallet.domain.ports import StripePort, WalletWorkFactory
from acciones_ud.wallet.domain.subscriptions import plans

CURRENT = frozenset({"active", "trialing", "past_due"})


class SubscriptionService:
    def __init__(
        self,
        uow: WalletWorkFactory,
        stripe: StripePort,
        clock: Clock,
        monthly_id: str,
        annual_id: str,
    ) -> None:
        self.uow, self.stripe, self.clock = uow, stripe, clock
        self.plans = plans(monthly_id, annual_id)

    def list_plans(self) -> list[Plan]:
        return self.plans

    async def start_checkout(self, user_id: UUID, plan_code: str) -> Raw:
        plan = next((v for v in self.plans if v.code == plan_code), None)
        if plan is None:
            raise invalid("plan")
        # Serializing check + insertion prevents two current checkout attempts.
        async with self.uow() as work:
            await work.lock_user(user_id)
            values = await work.subscriptions.list(user_id=user_id)
            if any(v.status in CURRENT for v in values):
                raise AppError(
                    409, ErrorCode.SUBSCRIPTION_ALREADY_ACTIVE, "Subscription is already active."
                )
            raw = await self.stripe.create_checkout_session(user_id, plan.stripe_price_id)
            subscription = Subscription(uuid4(), user_id, plan.code, "pending_checkout", raw["id"])
            await work.subscriptions.insert(subscription)
        return {"checkout_session_id": raw["id"], "url": raw["url"]}

    async def cancel(self, user_id: UUID, reason: str) -> Subscription:
        if not 1 <= len(reason.strip()) <= 500:
            raise invalid("reason")
        async with self.uow() as work:
            await work.lock_user(user_id)
            values = await work.subscriptions.list(user_id=user_id)
            current = next((v for v in values if v.status in CURRENT), None)
            if current is None or current.stripe_subscription_id is None:
                raise AppError(
                    409, ErrorCode.SUBSCRIPTION_NOT_CANCELABLE, "Subscription cannot be canceled."
                )
            await self.stripe.cancel_at_period_end(current.stripe_subscription_id)
            updated = replace(
                current,
                cancel_at_period_end=True,
                cancel_reason=reason,
                cancel_requested_at=self.clock.now(),
            )
            await work.subscriptions.save(updated)
        return updated

    async def get_current(self, user_id: UUID) -> Raw:
        async with self.uow() as work:
            values = await work.subscriptions.list(user_id=user_id)
            current = next(
                (v for v in values if v.status in CURRENT), values[-1] if values else None
            )
            payments = await work.payments.list(user_id=user_id)
        last = max(payments, key=lambda p: p.occurred_at) if payments else None
        plan = next((p for p in self.plans if current and current.plan == p.code), None)
        return {
            "subscription": current,
            "plan": plan,
            "latest_payment": last,
            "next_charge_at": current.current_period_end
            if current and not current.cancel_at_period_end
            else None,
        }

    async def list_payments(
        self, user_id: UUID, page_size: int = 50, cursor: str | None = None
    ) -> Page[Payment]:
        async with self.uow() as work:
            values = await work.payments.list(user_id=user_id)
        return paginate(values, page_size, cursor, date_field="occurred_at")

    async def get_payment(self, user_id: UUID, payment_id: UUID) -> Payment:
        async with self.uow() as work:
            payment = await work.payments.get(id=payment_id, user_id=user_id)
        if payment is None:
            raise not_found()
        return payment
