from decimal import Decimal
from uuid import uuid4

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.shared.domain.errors import AppError, ErrorCode
from tests.wallet.support import funding_setup


# Feature: wallet-mod-04, Property 1: Validación de importe y moneda de transferencias
@settings(max_examples=100)
@given(
    st.sampled_from(["INCOMING", "OUTGOING"]),
    st.sampled_from(
        [("0.99", "USD"), ("1.001", "USD"), ("50000.01", "USD"), ("10", "COP"), ("NaN", "USD")]
    ),
)
async def test_invalid_without_provider_calls(direction, request) -> None:
    service, _, alpaca, user, bank, _ = await funding_setup()
    with pytest.raises(AppError) as caught:
        await service.request_transfer(user, direction, bank.id, *request, "key12345")
    assert caught.value.code in {ErrorCode.VALIDATION_ERROR, ErrorCode.CURRENCY_NOT_SUPPORTED}
    assert alpaca.creations == 0


# Feature: wallet-mod-04, Property 3: Retiro limitado por el efectivo retirable
@settings(max_examples=100)
@given(st.integers(100, 5000000), st.integers(0, 5000000))
async def test_withdrawal_limit(cents, available_cents) -> None:
    service, _, alpaca, user, bank, _ = await funding_setup()
    amount, available = Decimal(cents) / 100, Decimal(available_cents) / 100
    alpaca.accounts["account"]["cash_withdrawable"] = str(available)
    if amount > available:
        with pytest.raises(AppError) as caught:
            await service.request_transfer(
                user, "OUTGOING", bank.id, str(amount), "USD", "key12345"
            )
        assert caught.value.code == ErrorCode.INSUFFICIENT_FUNDS
        assert caught.value.details == {"cash_withdrawable": str(available)}
        assert alpaca.creations == 0
    else:
        await service.request_transfer(user, "OUTGOING", bank.id, str(amount), "USD", "key12345")
        assert alpaca.creations == 1


# Feature: wallet-mod-04, Property 4: Idempotencia de depósitos y retiros
@settings(max_examples=100)
@given(
    st.sampled_from(["INCOMING", "OUTGOING"]),
    st.integers(100, 10000),
    st.lists(st.booleans(), min_size=1, max_size=12),
)
async def test_transfer_idempotency(direction, cents, changes) -> None:
    service, _, alpaca, user, bank, _ = await funding_setup()
    amount = Decimal(cents) / 100
    first = await service.request_transfer(user, direction, bank.id, str(amount), "USD", "key12345")
    for changed in changes:
        if changed:
            with pytest.raises(AppError) as caught:
                await service.request_transfer(
                    user, direction, bank.id, str(amount + 1), "USD", "key12345"
                )
            assert caught.value.code == ErrorCode.IDEMPOTENCY_CONFLICT
        else:
            assert (
                await service.request_transfer(
                    user, direction, bank.id, str(amount), "USD", "key12345"
                )
                == first
            )
    assert alpaca.creations == 1


# Feature: wallet-mod-04, Property 6: Recursos ajenos indistinguibles de inexistentes
@settings(max_examples=100)
@given(st.uuids())
async def test_ownership(other) -> None:
    service, _, _, user, bank, _ = await funding_setup()
    if other == user:
        return
    transfer = await service.request_transfer(user, "INCOMING", bank.id, "10", "USD", "key12345")
    for operation, real in [
        (service.get_transfer, transfer.id),
        (service.get_bank_relationship, bank.id),
    ]:
        errors = []
        for ident in (real, uuid4()):
            with pytest.raises(AppError) as caught:
                await operation(other, ident)
            errors.append((caught.value.status, caught.value.code, caught.value.details))
        assert errors[0] == errors[1] == (404, ErrorCode.NOT_FOUND, None)
