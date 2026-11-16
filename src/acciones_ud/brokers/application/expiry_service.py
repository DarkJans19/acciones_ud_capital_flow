from dataclasses import replace
from datetime import datetime

from acciones_ud.brokers.application.context import BrokerContext
from acciones_ud.brokers.application.proposal_service import ProposalService
from acciones_ud.brokers.domain import entities as e
from acciones_ud.brokers.domain import ports as p


class ExpiryService:
    def __init__(self, context: BrokerContext) -> None:
        self.ctx = context

    async def run_once(self, now: datetime | None = None) -> None:
        now = now or self.ctx.clock.now()
        await self._links(now)
        await self._proposals(now)
        await self._reconcile(now)

    async def _links(self, now: datetime) -> None:
        while True:
            changed = []
            async with self.ctx.uow() as work:
                batch = await work.links.expired_batch(now, 100)
                for link in batch:
                    updated = replace(
                        link, status=e.LinkStatus.EXPIRED, responded_at=link.expires_at
                    )
                    if await work.links.save(updated, status=e.LinkStatus.REQUESTED):
                        await self.ctx.event(
                            work,
                            "link",
                            link.id,
                            link.status,
                            updated.status,
                            "system",
                            None,
                            "ttl",
                            at=now,
                        )
                        changed.append(updated)
            for link in changed:
                await self.ctx.notify(
                    link.investor_id, "broker_link_updates", link_id=str(link.id), status="expired"
                )
            if len(batch) < 100 or not changed:
                break

    async def _proposals(self, now: datetime) -> None:
        service = ProposalService(self.ctx)
        while True:
            changed = []
            async with self.ctx.uow() as work:
                batch = await work.proposals.expired_batch(now, 100)
                for proposal in batch:
                    updated = replace(
                        proposal,
                        status=e.ProposalStatus.EXPIRED,
                        updated_at=now,
                        status_reason="ttl",
                    )
                    if await work.proposals.save(updated, status=e.ProposalStatus.SENT):
                        await self.ctx.event(
                            work,
                            "proposal",
                            proposal.id,
                            proposal.status,
                            updated.status,
                            "system",
                            None,
                            "ttl",
                            at=now,
                        )
                        changed.append(updated)
            for proposal in changed:
                await service._notify(proposal, proposal.broker_id, proposal.investor_id)
            if len(batch) < 100 or not changed:
                break

    async def _reconcile(self, now: datetime) -> None:
        async with self.ctx.uow() as work:
            candidates = await work.proposals.list(status=e.ProposalStatus.ACCEPTED)
        for proposal in candidates:
            async with self.ctx.uow() as work:
                attempts = await work.decisions.list(
                    proposal_id=proposal.id,
                    version=proposal.current_version,
                    decision="approve",
                    actor_role="broker",
                )
                version = await work.versions.get(
                    proposal_id=proposal.id, version=proposal.current_version
                )
            if (
                not attempts
                or version is None
                or proposal.accepted_version != proposal.current_version
            ):
                continue
            attempt = min(attempts, key=lambda decision: (decision.at, decision.id))
            command = p.ProposalOrderCommand(
                proposal.id,
                proposal.investor_id,
                proposal.broker_id,
                version.symbol,
                version.side,
                version.qty,
                version.type,
                version.limit_price,
            )
            order_id = await self.ctx.order_query.find_by_idempotency_key(
                proposal.investor_id, f"proposal:{proposal.id}", command
            )
            if order_id is None:
                continue
            updated = None
            async with self.ctx.uow() as work:
                await work.links.get(id=proposal.link_id, for_update=True)
                current = await work.proposals.get(id=proposal.id, for_update=True)
                if (
                    current
                    and current.status == e.ProposalStatus.ACCEPTED
                    and current.current_version == proposal.current_version
                ):
                    value = replace(
                        current, status=e.ProposalStatus.APPROVED, order_id=order_id, updated_at=now
                    )
                    if await work.proposals.save(
                        value, status=current.status, current_version=current.current_version
                    ):
                        updated = value
                        await self.ctx.event(
                            work,
                            "proposal",
                            current.id,
                            current.status,
                            value.status,
                            "broker",
                            attempt.actor_id,
                            "reconciled",
                            at=now,
                            decision_id=str(attempt.id),
                            order_id=str(order_id),
                        )
            if updated:
                await ProposalService(self.ctx)._notify(
                    updated, updated.broker_id, updated.investor_id
                )
