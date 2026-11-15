from dataclasses import replace
from datetime import timedelta

import pytest

from acciones_ud.shared.domain.alpaca_errors import AlpacaValidationError
from acciones_ud.shared.domain.errors import AppError
from acciones_ud.wallet.application.dtos import period
from acciones_ud.wallet.domain.model import BankRelationshipInput
from tests.wallet.support import funding_setup


async def test_bank_validation_and_rejected_transfer_release_key() -> None:
    service, uow, alpaca, user, bank, clock = await funding_setup()
    with pytest.raises(AppError) as caught:
        await service.create_bank_relationship(
            user, BankRelationshipInput("", "INVALID", "sensitive-account", "sensitive-route")
        )
    assert caught.value.details == {
        "fields": [
            "account_owner_name",
            "bank_account_type",
            "bank_account_number",
            "bank_routing_number",
        ]
    }
    alpaca.failure = AlpacaValidationError("Rejected by provider")
    with pytest.raises(AppError) as caught:
        await service.request_transfer(user, "INCOMING", bank.id, "10", "USD", "key12345")
    assert caught.value.code == "TRANSFER_REJECTED"
    assert caught.value.details == {"reason": "Rejected by provider"}
    assert not uow.work.keys.values and not uow.work.transfers.values
    start, end = period(clock.now(), None, None)
    assert end - start == timedelta(days=30)
    for before, after in [(end, start), (end - timedelta(days=367), end)]:
        with pytest.raises(AppError):
            period(clock.now(), before, after)


async def test_unapproved_bank_and_inactive_account() -> None:
    service, uow, alpaca, user, bank, _ = await funding_setup()
    await uow.work.banks.save(replace(bank, status="PENDING"))
    with pytest.raises(AppError) as caught:
        await service.request_transfer(user, "INCOMING", bank.id, "10", "USD", "key12345")
    assert caught.value.code == "BANK_RELATIONSHIP_NOT_USABLE"
    assert alpaca.creations == 0
    uow.link(user, status="SUBMITTED")
    with pytest.raises(AppError) as caught:
        await service.create_bank_relationship(
            user, BankRelationshipInput("Sandbox", "CHECKING", "12345678", "123456789")
        )
    assert caught.value.code == "WALLET_ACCOUNT_NOT_ACTIVE"
