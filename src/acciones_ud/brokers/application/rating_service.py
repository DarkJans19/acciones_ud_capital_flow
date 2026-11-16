from uuid import UUID

from acciones_ud.brokers.application.context import BrokerContext
from acciones_ud.brokers.application.directory_service import DirectoryService
from acciones_ud.brokers.domain.entities import LinkStatus, Rating, Reputation
from acciones_ud.brokers.domain.errors import (
    BrokerNotFoundError,
    RatingNotAllowedError,
    ValidationError,
)
from acciones_ud.orders.domain.model import Raw


class RatingService:
    def __init__(self, context: BrokerContext) -> None:
        self.ctx = context

    async def publish(
        self, investor_id: UUID, broker_id: UUID, stars: int, comment: str = ""
    ) -> Rating:
        await self.ctx.require_role(investor_id, "investor")
        if type(stars) is not int or not 1 <= stars <= 5:
            raise ValidationError("stars")
        if len(comment) > 1000:
            raise ValidationError("comment")
        async with self.ctx.uow() as work:
            await work.lock_investor(investor_id)
            eligible = [
                v
                for v in await work.links.list(investor_id=investor_id, broker_id=broker_id)
                if v.status in {LinkStatus.ACTIVE, LinkStatus.ENDED}
            ]
            if not eligible:
                raise RatingNotAllowedError()
            link = max(eligible, key=lambda v: (v.requested_at, v.id))
            now = self.ctx.clock.now()
            return await work.ratings.upsert(
                Rating(link.id, investor_id, broker_id, stars, comment, now, now)
            )

    async def reputation(self, broker_id: UUID) -> Reputation:
        broker = await self.ctx.directory.get_broker(broker_id)
        if broker is None:
            raise BrokerNotFoundError()
        return await DirectoryService(self.ctx).reputation_value(broker)

    async def reviews(self, broker_id: UUID, cursor: str | None = None, page_size: int = 20) -> Raw:
        if await self.ctx.directory.get_broker(broker_id) is None:
            raise BrokerNotFoundError()
        async with self.ctx.uow() as work:
            values, token = await work.ratings.page(broker_id, cursor, page_size)
        # Review pages expose no investor identifiers or contact details.
        return {
            "items": [
                {
                    "stars": value.stars,
                    "comment": value.comment,
                    "created_at": value.created_at,
                    "updated_at": value.updated_at,
                }
                for value in values
            ],
            "next_cursor": token,
        }
