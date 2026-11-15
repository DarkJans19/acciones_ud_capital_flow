from dataclasses import replace

from acciones_ud.wallet.application.transfer_reconciler import TransferReconciler
from acciones_ud.wallet.domain.model import Activity
from tests.wallet.fakes import Notifications
from tests.wallet.support import funding_setup


async def test_transfer_and_fill_notifications_are_at_most_once() -> None:
    service, uow, alpaca, user, bank, clock = await funding_setup()
    notices = Notifications()
    reconciler = TransferReconciler(uow, alpaca, notices, clock)
    transfer = await service.request_transfer(user, "INCOMING", bank.id, "10", "USD", "key12345")
    await uow.work.transfers.save(replace(transfer, alpaca_updated_at=clock.now()))
    alpaca.transfers["account"][0]["updated_at"] = clock.now().isoformat()
    await reconciler.run_once()  # Initializes the activities cursor, without historical notices.
    clock.advance(60)
    alpaca.transfers["account"][0].update(status="COMPLETE", updated_at=clock.now().isoformat())
    alpaca.activities["account"] = [
        Activity("fill1", "FILL", clock.now(), symbol="AAPL", side="buy", qty="1", price="10")
    ]
    await reconciler.run_once()
    await reconciler.run_once()
    assert len(notices.values) == 2
    assert (await uow.work.transfers.get(id=transfer.id)).status == "COMPLETE"


async def test_transfer_returned_complete_by_creation_is_notified_once() -> None:
    service, uow, alpaca, user, bank, clock = await funding_setup()
    original = alpaca.create_transfer

    async def complete_immediately(*args):
        raw = await original(*args)
        raw["status"] = "COMPLETE"
        return raw

    alpaca.create_transfer = complete_immediately
    transfer = await service.request_transfer(user, "INCOMING", bank.id, "10", "USD", "key12345")
    assert transfer.status == "COMPLETE"
    notices = Notifications()
    reconciler = TransferReconciler(uow, alpaca, notices, clock)
    await reconciler.run_once()
    await reconciler.run_once()
    assert len(notices.values) == 1
    assert notices.values[0][1]["amount"] == "10"
