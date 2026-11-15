from uuid import UUID, uuid4

from acciones_ud.wallet.domain.model import Raw


class FakeStripe:
    def __init__(self) -> None:
        self.checkouts = 0
        self.cancellations = 0
        self.failure: Exception | None = None
        self.subscriptions: dict[str, Raw] = {}

    async def create_checkout_session(self, user_id: UUID, price_id: str) -> Raw:
        if self.failure:
            raise self.failure
        self.checkouts += 1
        return {"id": "cs_test_" + uuid4().hex, "url": "https://checkout.stripe.test/pay"}

    async def cancel_at_period_end(self, stripe_subscription_id: str) -> Raw:
        if self.failure:
            raise self.failure
        self.cancellations += 1
        return {"id": stripe_subscription_id, "cancel_at_period_end": True}

    async def get_subscription(self, stripe_subscription_id: str) -> Raw:
        if self.failure:
            raise self.failure
        return self.subscriptions[stripe_subscription_id]
