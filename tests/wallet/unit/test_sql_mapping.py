from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from acciones_ud.shared.infrastructure.entity_repository import EntityRepository
from acciones_ud.wallet.adapters.outbound.persistence.tables import subscriptions
from acciones_ud.wallet.domain.model import Subscription


async def test_database_audit_columns_are_not_passed_into_domain() -> None:
    user, ident = uuid4(), uuid4()
    row = {
        "id": ident,
        "user_id": user,
        "plan": "monthly",
        "status": "pending_checkout",
        "stripe_checkout_session_id": "cs_test",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    result = Mock()
    result.mappings.return_value.first.return_value = row
    session = AsyncMock()
    session.execute.return_value = result
    value = await EntityRepository(session, subscriptions, Subscription).get(id=ident)
    assert value.id == ident and value.plan == "monthly"
