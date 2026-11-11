from datetime import UTC, datetime
from typing import Any, cast

from acciones_ud.market_data.adapters.outbound.alpaca.fake_broker import instrument
from acciones_ud.market_data.adapters.outbound.persistence.instrument_repository import (
    UPSERT_BATCH_SIZE,
    InstrumentRepository,
)


class RecordingSession:
    def __init__(self) -> None:
        self.statements: list[object] = []

    async def execute(self, statement: object) -> None:
        self.statements.append(statement)


async def test_catalog_upsert_is_batched_below_the_parameter_limit() -> None:
    session = RecordingSession()
    repository = InstrumentRepository(cast(Any, session))
    assets = [instrument(f"S{index:05d}") for index in range(UPSERT_BATCH_SIZE * 2 + 1)]

    await repository._upsert(assets, datetime(2026, 1, 2, tzinfo=UTC))

    assert len(session.statements) == 3
    for statement in session.statements:
        parameters = statement.compile().params  # type: ignore[attr-defined]
        assert len(parameters) < 32767
