import logging
from dataclasses import replace

from acciones_ud.shared.domain.clock import Clock
from acciones_ud.wallet.application.dtos import timestamp
from acciones_ud.wallet.domain.model import (
    SANDBOX_NOTICE,
    ActivityCursor,
    ActivityQuery,
    LinkedAccount,
    NotificationMarker,
    Transfer,
    TransferState,
    TransferUpdate,
)
from acciones_ud.wallet.domain.ports import (
    AlpacaFundingPort,
    BalanceNotifierPort,
    WalletWorkFactory,
)
from acciones_ud.wallet.domain.transfers import TERMINAL, decide_update

logger = logging.getLogger(__name__)


class TransferReconciler:
    def __init__(
        self,
        uow: WalletWorkFactory,
        alpaca: AlpacaFundingPort,
        notifier: BalanceNotifierPort,
        clock: Clock,
    ) -> None:
        self.uow, self.alpaca, self.notifier, self.clock = uow, alpaca, notifier, clock

    async def run_once(self) -> None:
        already_complete: list[Transfer] = []
        async with self.uow() as work:
            accounts = {a.alpaca_account_id: a for a in await work.accounts.list_active()}
            stored_transfers = await work.transfers.list()
            notified = {marker.external_id for marker in await work.markers.list(source="transfer")}
            for transfer in stored_transfers:
                if transfer.status == "COMPLETE" and transfer.alpaca_transfer_id not in notified:
                    if await work.markers.insert(
                        NotificationMarker(
                            "transfer",
                            transfer.alpaca_transfer_id,
                            transfer.user_id,
                            self.clock.now(),
                        )
                    ):
                        already_complete.append(transfer)
            transfers = [t for t in stored_transfers if t.status not in TERMINAL]
        for transfer in already_complete:
            try:
                await self.notifier.notify(
                    transfer.user_id,
                    {
                        "direction": transfer.direction,
                        "amount": str(transfer.amount),
                        "currency": transfer.currency,
                        "sandbox_notice": SANDBOX_NOTICE,
                    },
                )
            except Exception:
                logger.warning(
                    "Completed transfer notification failed",
                    extra={"user_id": str(transfer.user_id)},
                )
        for transfer in transfers:
            accounts.setdefault(
                transfer.alpaca_account_id,
                LinkedAccount(transfer.user_id, transfer.alpaca_account_id, "ACTIVE"),
            )
        for account_id, account in accounts.items():
            try:
                await self._transfers(account_id, account, transfers)
                await self._activities(account)
            except Exception:
                logger.warning(
                    "Wallet reconciliation failed for account",
                    extra={"user_id": str(account.user_id)},
                )

    async def _transfers(
        self, account_id: str, account: LinkedAccount, transfers: list[Transfer]
    ) -> None:
        raw = {str(v["id"]): v for v in await self.alpaca.list_transfers(account_id)}
        for stored in transfers:
            if stored.alpaca_account_id != account_id or stored.alpaca_transfer_id not in raw:
                continue
            live = raw[stored.alpaca_transfer_id]
            at = timestamp(live.get("updated_at"))
            if at is None:
                continue
            incoming = TransferUpdate(str(live["status"]), at, live.get("reason"))
            if (
                decide_update(TransferState(stored.status, stored.alpaca_updated_at), incoming)
                is None
            ):
                continue
            notify = False
            async with self.uow() as work:
                changed = await work.transfers.save(
                    replace(
                        stored,
                        status=incoming.status,
                        reason=incoming.reason,
                        alpaca_updated_at=at,
                        last_confirmed_at=self.clock.now(),
                    ),
                    status=stored.status,
                    alpaca_updated_at=stored.alpaca_updated_at,
                )
                if changed and incoming.status == "COMPLETE":
                    notify = await work.markers.insert(
                        NotificationMarker(
                            "transfer", stored.alpaca_transfer_id, stored.user_id, self.clock.now()
                        )
                    )
            if notify:
                await self.notifier.notify(
                    stored.user_id,
                    {
                        "direction": stored.direction,
                        "amount": str(stored.amount),
                        "currency": stored.currency,
                        "sandbox_notice": SANDBOX_NOTICE,
                    },
                )

    async def _activities(self, account: LinkedAccount) -> None:
        now = self.clock.now()
        async with self.uow() as work:
            cursor = await work.cursors.get(alpaca_account_id=account.alpaca_account_id)
            if cursor is None:
                await work.cursors.insert(ActivityCursor(account.alpaca_account_id, None, now))
                return
        token = cursor.last_activity_id
        while True:
            page = await self.alpaca.list_activities(
                ActivityQuery(account.alpaca_account_id, cursor.updated_at, now, (), 100, token)
            )
            for activity in page.items:
                notify = False
                async with self.uow() as work:
                    if activity.type == "FILL":
                        notify = await work.markers.insert(
                            NotificationMarker("activity", activity.id, account.user_id, now)
                        )
                    await work.cursors.save(
                        ActivityCursor(account.alpaca_account_id, activity.id, activity.date)
                    )
                if notify:
                    await self.notifier.notify(
                        account.user_id,
                        {
                            "side": activity.side,
                            "symbol": activity.symbol,
                            "qty": activity.qty,
                            "price": activity.price,
                            "currency": activity.currency,
                        },
                    )
            if page.next_cursor is None or page.next_cursor == token:
                break
            token = page.next_cursor
