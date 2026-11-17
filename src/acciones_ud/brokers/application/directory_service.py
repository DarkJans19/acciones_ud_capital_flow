from dataclasses import asdict
from uuid import UUID

from acciones_ud.brokers.application.context import BrokerContext
from acciones_ud.brokers.domain.entities import (
    BrokerIdentity,
    BrokerProfile,
    LinkStatus,
    Reputation,
)
from acciones_ud.brokers.domain.errors import BrokerNotFoundError, ValidationError
from acciones_ud.brokers.domain.link_state_machine import effective_status
from acciones_ud.brokers.domain.pagination import search_cursor
from acciones_ud.brokers.domain.reputation import average
from acciones_ud.orders.domain.model import Raw


class DirectoryService:
    def __init__(self, context: BrokerContext) -> None:
        self.ctx = context

    async def reputation_value(self, broker: BrokerIdentity) -> Reputation:
        async with self.ctx.uow() as work:
            ratings = await work.ratings.list(broker_id=broker.user_id)
            links = await work.links.list(broker_id=broker.user_id)
            proposals = await work.proposals.list(broker_id=broker.user_id)
            profile = await work.profiles.get(broker_id=broker.user_id)
        return Reputation(
            broker.user_id,
            broker.name,
            average([r.stars for r in ratings]),
            len(ratings),
            sum(p.order_id is not None for p in proposals),
            len(
                {
                    link.investor_id
                    for link in links
                    if link.status in {LinkStatus.ACTIVE, LinkStatus.ENDED}
                }
            ),
            profile.years_experience if profile else 0,
            broker.broker_since,
        )

    async def public_profile(self, broker: BrokerIdentity) -> Raw:
        async with self.ctx.uow() as work:
            profile = await work.profiles.get(broker_id=broker.user_id)
        reputation = await self.reputation_value(broker)
        return {
            "id": broker.user_id,
            "name": broker.name,
            "firm_name": broker.firm_name,
            "specialty": profile.specialty if profile else "",
            "years_experience": profile.years_experience if profile else 0,
            "certifications": profile.certifications if profile else (),
            "description": profile.description if profile else "",
            "reputation": asdict(reputation),
        }

    async def get_profile(self, broker_id: UUID) -> Raw:
        broker = await self.ctx.directory.get_broker(broker_id)
        if broker is None:
            raise BrokerNotFoundError()
        return await self.public_profile(broker)

    async def update_profile(
        self,
        broker_id: UUID,
        specialty: str,
        years_experience: int,
        certifications: tuple[str, ...],
        description: str,
    ) -> Raw:
        await self.ctx.require_role(broker_id, "broker")
        if not 1 <= len(specialty.strip()) <= 100:
            raise ValidationError("specialty")
        if type(years_experience) is not int or not 0 <= years_experience <= 60:
            raise ValidationError("years_experience")
        if len(certifications) > 10 or any(not 1 <= len(c.strip()) <= 100 for c in certifications):
            raise ValidationError("certifications")
        if len(description) > 1000:
            raise ValidationError("description")
        async with self.ctx.uow() as work:
            await work.profiles.upsert(
                BrokerProfile(
                    broker_id,
                    specialty,
                    years_experience,
                    certifications,
                    description,
                    self.ctx.clock.now(),
                )
            )
        return await self.get_profile(broker_id)

    async def suggestions(self, investor_id: UUID) -> list[Raw]:
        await self.ctx.require_role(investor_id, "investor")
        async with self.ctx.uow() as work:
            link = await work.links.open_for(investor_id)
        excluded = (
            link.broker_id
            if link
            and effective_status(link, self.ctx.clock.now(), self.ctx.config.link_ttl_days)
            in {LinkStatus.REQUESTED, LinkStatus.ACTIVE}
            else None
        )
        brokers = await self.ctx.directory.all_active(investor_id)
        values = [await self.public_profile(b) for b in brokers if b.user_id != excluded]
        values.sort(
            key=lambda v: (
                v["reputation"]["average"] is None,
                -(v["reputation"]["average"] or 0),
                -v["reputation"]["reviews_count"],
                v["name"],
                v["id"],
            )
        )
        return values[:10]

    async def search(
        self,
        investor_id: UUID,
        text: str | None = None,
        cursor: str | None = None,
        page_size: int = 20,
    ) -> Raw:
        await self.ctx.require_role(investor_id, "investor")
        if text is not None and not 2 <= len(text.strip()) <= 100:
            raise ValidationError("q")
        if not 1 <= page_size <= 100:
            raise ValidationError("page_size")
        query = text.strip() if text is not None else ""
        brokers = await self.ctx.directory.search(query, investor_id, cursor, page_size + 1)
        selected = brokers[:page_size]
        token = (
            search_cursor(selected[-1].name, selected[-1].user_id)
            if len(brokers) > page_size
            else None
        )
        return {"items": [await self.public_profile(b) for b in selected], "next_cursor": token}
