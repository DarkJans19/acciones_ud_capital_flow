from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from acciones_ud.market_data.adapters.outbound.persistence.recipient_directory import (
    RecipientDirectory,
)


async def test_recipient_filters_in_sql_and_respects_channels() -> None:
    user_id = uuid4()
    result = Mock()
    result.all.return_value = [
        SimpleNamespace(
            user_id=user_id,
            event_type="balance_changes",
            channel="in_app",
            enabled=True,
            email="test@example.com",
            telegram_chat_id=None,
        )
    ]
    session = AsyncMock()
    session.execute.return_value = result
    recipient = await RecipientDirectory(session).recipient(user_id, "balance_changes")
    assert recipient and recipient.channels == frozenset({"in_app"})
    statement, parameters = session.execute.call_args.args
    assert "p.user_id = :user_id" in str(statement)
    assert parameters["user_id"] == user_id
    result.all.return_value[0].enabled = False
    assert await RecipientDirectory(session).recipient(user_id, "balance_changes") is None
