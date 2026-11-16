from datetime import timedelta
from uuid import uuid4

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.brokers.application.rating_service import RatingService
from acciones_ud.brokers.domain.entities import Link
from acciones_ud.brokers.domain.entities import LinkStatus as S
from acciones_ud.brokers.domain.errors import RatingNotAllowedError
from tests.brokers.support import actors, context


# Feature: brokers-mod-06, Property 11: Una Rating por Link con reemplazo
@settings(max_examples=100)
@given(
    st.lists(st.lists(st.sampled_from(list(S)), max_size=5), min_size=2, max_size=2),
    st.lists(st.tuples(st.integers(0, 1), st.integers(1, 5), st.text(max_size=25)), max_size=25),
)
async def test_ratings_select_latest_eligible_link_and_replace(history, publications):
    ctx = context()
    first, broker = actors(ctx)
    owners = [first, uuid4()]
    ctx.directory.add(owners[1], "investor")
    histories = [[], []]
    for owner_index, statuses in enumerate(history):
        open_seen = False
        for index, status in enumerate(statuses):
            if status in {S.REQUESTED, S.ACTIVE}:
                status = S.ENDED if open_seen else status
                open_seen = True
            instant = ctx.clock.now() + timedelta(hours=index)
            link = Link(
                uuid4(),
                owners[owner_index],
                broker,
                status,
                instant,
                instant + timedelta(days=7),
                "v1",
                instant,
            )
            await ctx.uow.work.links.insert(link)
            histories[owner_index].append(link)
    service, expected = RatingService(ctx), {}
    for owner_index, stars, comment in publications:
        ctx.clock.advance(seconds=1)
        eligible = [v for v in histories[owner_index] if v.status in {S.ACTIVE, S.ENDED}]
        before = dict(ctx.uow.work.ratings.values)
        if not eligible:
            with pytest.raises(RatingNotAllowedError):
                await service.publish(owners[owner_index], broker, stars, comment)
            assert ctx.uow.work.ratings.values == before
        else:
            latest = max(eligible, key=lambda v: v.requested_at)
            rating = await service.publish(owners[owner_index], broker, stars, comment)
            assert rating.link_id == latest.id
            expected[latest.id] = stars, comment
        assert len(ctx.uow.work.ratings.values) == len(expected)
        for rating in ctx.uow.work.ratings.values.values():
            assert (rating.stars, rating.comment) == expected[rating.link_id]
        assert (await service.reputation(broker)).reviews_count == len(expected)
