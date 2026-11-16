from collections.abc import Mapping, Sequence
from dataclasses import replace
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from uuid import UUID

from acciones_ud.brokers.domain.entities import Rating


def average(stars: Sequence[int]) -> Decimal | None:
    if not stars:
        return None
    with localcontext() as ctx:
        ctx.prec = 40
        return (Decimal(sum(stars)) / len(stars)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_EVEN
        )


def upsert(ratings: Mapping[UUID, Rating], value: Rating) -> Mapping[UUID, Rating]:
    existing = ratings.get(value.link_id)
    if existing:
        value = replace(value, created_at=existing.created_at)
    return {**ratings, value.link_id: value}
