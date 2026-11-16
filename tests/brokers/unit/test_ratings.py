from decimal import Decimal

import pytest

from acciones_ud.brokers.application.link_service import LinkService
from acciones_ud.brokers.application.rating_service import RatingService
from acciones_ud.brokers.domain.errors import ValidationError
from tests.brokers.support import actors, context


async def test_rating_replaces_latest_eligible_link_and_updates_reputation():
    ctx = context()
    investor, broker = actors(ctx)
    links, service = LinkService(ctx), RatingService(ctx)
    link = await links.request_link(investor, broker, True)
    await links.accept(broker, link.id)
    first = await service.publish(investor, broker, 2, "First")
    ctx.clock.advance(hours=1)
    updated = await service.publish(investor, broker, 5, "Updated")
    assert updated.link_id == first.link_id and updated.created_at == first.created_at
    assert updated.updated_at > first.updated_at
    assert len(ctx.uow.work.ratings.values) == 1
    reputation = await service.reputation(broker)
    assert reputation.average == Decimal("5.00") and reputation.reviews_count == 1


async def test_latest_link_selection_review_pagination_and_experience_counts():
    ctx = context()
    investor, broker = actors(ctx)
    links, ratings = LinkService(ctx), RatingService(ctx)
    assert (await ratings.reputation(broker)).average is None
    first = await links.request_link(investor, broker, True)
    await links.accept(broker, first.id)
    await ratings.publish(investor, broker, 5, "First relationship")
    await links.end_link(investor, first.id, "Ended", True)
    ctx.clock.advance(hours=1)
    second = await links.request_link(investor, broker, True)
    await links.accept(broker, second.id)
    latest = await ratings.publish(investor, broker, 1, "Second relationship")
    assert latest.link_id == second.id
    reputation = await ratings.reputation(broker)
    assert reputation.average == Decimal("3.00") and reputation.distinct_investors == 1
    first_page = await ratings.reviews(broker, page_size=1)
    assert first_page["items"][0]["stars"] == 1
    assert not {"investor_id", "link_id", "email"} & first_page["items"][0].keys()
    second_page = await ratings.reviews(broker, first_page["next_cursor"], 1)
    assert second_page["items"][0]["stars"] == 5 and second_page["next_cursor"] is None
    for stars in (True, 0, 6, 1.5):
        with pytest.raises(ValidationError):
            await ratings.publish(investor, broker, stars)
