from uuid import uuid4

import pytest

from acciones_ud.brokers.application.directory_service import DirectoryService
from acciones_ud.brokers.domain.errors import BrokerNotFoundError, ValidationError
from tests.brokers.support import actors, context


async def test_profile_public_fields_and_validation():
    ctx = context()
    _, broker = actors(ctx)
    service = DirectoryService(ctx)
    value = await service.update_profile(broker, "Equities", 5, ("Finance",), "Description")
    assert value["specialty"] == "Equities"
    assert not {"email", "phone", "license_number", "clients"} & value.keys()
    with pytest.raises(ValidationError):
        await service.update_profile(broker, "", 5, (), "")
    ctx.directory.roles[broker].clear()
    with pytest.raises(BrokerNotFoundError):
        await service.get_profile(broker)


async def test_directory_excludes_self_paginates_and_checks_all_profile_limits():
    ctx = context()
    investor, broker = actors(ctx)
    ctx.directory.add(investor, "broker")
    for _ in range(3):
        ctx.directory.add(uuid4(), "broker")
    service = DirectoryService(ctx)
    first = await service.search(investor, "Firm", page_size=2)
    assert len(first["items"]) == 2 and first["next_cursor"]
    second = await service.search(investor, "Firm", cursor=first["next_cursor"], page_size=2)
    assert len(second["items"]) == 2 and second["next_cursor"] is None
    identifiers = [v["id"] for v in first["items"] + second["items"]]
    assert investor not in identifiers and len(set(identifiers)) == 4
    assert len(await service.suggestions(investor)) == 4
    for args in [
        ("X" * 101, 0, (), ""),
        ("X", -1, (), ""),
        ("X", 61, (), ""),
        ("X", True, (), ""),
        ("X", 0, ("C",) * 11, ""),
        ("X", 0, ("",), ""),
        ("X", 0, (), "D" * 1001),
    ]:
        with pytest.raises(ValidationError):
            await service.update_profile(broker, *args)
