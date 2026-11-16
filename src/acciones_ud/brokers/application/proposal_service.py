from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict, replace
from datetime import timedelta
from typing import Literal, cast
from uuid import UUID, uuid4

from acciones_ud.brokers.application.commands import ProposalContent
from acciones_ud.brokers.application.context import BrokerContext
from acciones_ud.brokers.domain import entities as e
from acciones_ud.brokers.domain import ports as p
from acciones_ud.brokers.domain.access import require_active_link
from acciones_ud.brokers.domain.errors import (
    AccountNotLinkedError,
    AssetNotTradableError,
    ConfirmationRequiredError,
    ExtraAuthorizationInvalidError,
    InvalidProposalStateError,
    NotFoundError,
    TradingAuthorizationRequiredError,
    ValidationError,
)
from acciones_ud.brokers.domain.estimates import estimated_cost, reference_price, requires_totp
from acciones_ud.brokers.domain.periods import to_utc_range
from acciones_ud.brokers.domain.proposal_state_machine import (
    check_version,
    effective_status,
    transition,
)
from acciones_ud.orders.domain.model import Raw


class ProposalService:
    def __init__(self, context: BrokerContext) -> None:
        self.ctx = context

    def _effective(self, proposal: e.Proposal) -> e.Proposal:
        return replace(
            proposal,
            status=effective_status(
                proposal, self.ctx.clock.now(), self.ctx.config.proposal_ttl_hours
            ),
        )

    async def _participants(self, proposal: e.Proposal) -> Raw:
        return {
            "broker": {
                "id": proposal.broker_id,
                "name": await self.ctx.directory.display_name(proposal.broker_id) or "",
            },
            "investor": {
                "id": proposal.investor_id,
                "name": await self.ctx.directory.display_name(proposal.investor_id) or "",
            },
        }

    async def detail(self, actor: UUID, role: Literal["investor", "broker"], ident: UUID) -> Raw:
        await self.ctx.require_role(actor, role)
        async with self.ctx.uow() as work:
            proposal = await self._owned(work, actor, role, ident)
            versions = await work.versions.list(proposal_id=ident)
            decisions = await work.decisions.list(proposal_id=ident)
        return {
            **asdict(self._effective(proposal)),
            **await self._participants(proposal),
            "versions": [asdict(v) for v in sorted(versions, key=lambda v: v.version)],
            "decisions": [asdict(d) for d in sorted(decisions, key=lambda d: (d.at, d.id))],
        }

    async def _history(
        self,
        actor: UUID,
        role: Literal["investor", "broker"],
        status: e.ProposalStatus | None,
        period: e.Period | None,
        cursor: str | None,
        page_size: int,
    ) -> Raw:
        await self.ctx.require_role(actor, role)
        start, end = to_utc_range(period) if period else (None, None)
        if status is not None:
            try:
                status = e.ProposalStatus(status)
            except ValueError:
                raise ValidationError("status") from None
        async with self.ctx.uow() as work:
            proposals, token = await work.proposals.page(
                actor, role, status, start, end, self.ctx.clock.now(), cursor, page_size
            )
            versions = [
                await work.versions.get(proposal_id=proposal.id, version=proposal.current_version)
                for proposal in proposals
            ]
        items = []
        for proposal, version in zip(proposals, versions, strict=True):
            assert version is not None
            items.append(
                {
                    **asdict(self._effective(proposal)),
                    **await self._participants(proposal),
                    "symbol": version.symbol,
                    "side": version.side,
                    "qty": version.qty,
                    "type": version.type,
                    "estimated_cost": version.estimated_cost,
                }
            )
        return {"items": items, "next_cursor": token}

    async def history_investor(
        self,
        investor_id: UUID,
        status: e.ProposalStatus | None = None,
        period: e.Period | None = None,
        cursor: str | None = None,
        page_size: int = 20,
    ) -> Raw:
        return await self._history(investor_id, "investor", status, period, cursor, page_size)

    async def history_broker(
        self,
        broker_id: UUID,
        status: e.ProposalStatus | None = None,
        period: e.Period | None = None,
        cursor: str | None = None,
        page_size: int = 20,
    ) -> Raw:
        return await self._history(broker_id, "broker", status, period, cursor, page_size)

    async def _owned(
        self,
        work: p.BrokerWork,
        actor: UUID,
        role: Literal["investor", "broker"],
        ident: UUID,
        *,
        active: bool = False,
    ) -> e.Proposal:
        proposal = await work.proposals.get(id=ident)
        if proposal is None or getattr(proposal, f"{role}_id") != actor:
            raise NotFoundError("proposal")
        link = await work.links.get(id=proposal.link_id, for_update=True)
        if role == "broker" or active:
            require_active_link(
                link, await self.ctx.directory.has_role(proposal.broker_id, "broker"), "proposal"
            )
        locked = await work.proposals.get(id=ident, for_update=True)
        if locked is None:
            raise NotFoundError("proposal")
        return locked

    async def _expire(self, work: p.BrokerWork, proposal: e.Proposal) -> e.Proposal:
        status = effective_status(
            proposal, self.ctx.clock.now(), self.ctx.config.proposal_ttl_hours
        )
        if status != proposal.status:
            updated = replace(
                proposal, status=status, updated_at=self.ctx.clock.now(), status_reason="ttl"
            )
            await work.proposals.save(updated, status=proposal.status)
            await self.ctx.event(
                work, "proposal", proposal.id, proposal.status, status, "system", None, "ttl"
            )
            return updated
        return proposal

    async def _notify(self, proposal: e.Proposal, *recipients: UUID) -> None:
        for recipient in recipients:
            await self.ctx.notify(
                recipient, "proposal_updates", proposal_id=str(proposal.id), status=proposal.status
            )

    async def _snapshot(
        self, actor: UUID, role: Literal["investor", "broker"], ident: UUID
    ) -> e.Proposal:
        async with self.ctx.uow() as work:
            old = await self._owned(work, actor, role, ident)
            proposal = await self._expire(work, old)
        if proposal.status != old.status:
            await self._notify(proposal, proposal.broker_id, proposal.investor_id)
        return proposal

    @asynccontextmanager
    async def _action(
        self,
        actor: UUID,
        role: Literal["investor", "broker"],
        ident: UUID,
        action: e.ProposalAction,
        seen_version: int,
    ) -> AsyncIterator[tuple[p.BrokerWork, e.Proposal]]:
        expired = None
        async with self.ctx.uow() as work:
            old = await self._owned(work, actor, role, ident)
            proposal = await self._expire(work, old)
            if old.status != proposal.status:
                expired = proposal
            else:
                transition(proposal.status, action)
                check_version(proposal.current_version, seen_version)
                yield work, proposal
        if expired:
            await self._notify(expired, expired.broker_id, expired.investor_id)
            raise InvalidProposalStateError(expired.status)

    async def _version(
        self, ident: UUID, version: int, content: ProposalContent
    ) -> e.ProposalVersion:
        content = content.validated()
        if not await self.ctx.quotes.tradable(content.symbol):
            raise AssetNotTradableError()
        last = (
            await self.ctx.quotes.last_price(content.symbol) if content.type == "market" else None
        )
        price = reference_price(content.type, content.limit_price, last)
        cost = estimated_cost(content.qty, price, self.ctx.config.commission_rate)
        if not cost.is_finite() or cost >= 10**18:
            raise ValidationError("estimated_cost", "numeric_range")
        return e.ProposalVersion(
            ident,
            version,
            content.symbol,
            cast(Literal["buy", "sell"], content.side),
            content.qty,
            cast(Literal["market", "limit"], content.type),
            content.limit_price,
            price,
            cost,
            self.ctx.clock.now(),
        )

    async def create(
        self, broker_id: UUID, investor_id: UUID, content: ProposalContent
    ) -> e.Proposal:
        await self.ctx.require_role(broker_id, "broker")
        async with self.ctx.uow() as work:
            link = await work.links.get(
                broker_id=broker_id, investor_id=investor_id, status=e.LinkStatus.ACTIVE
            )
        require_active_link(link, await self.ctx.directory.has_role(broker_id, "broker"), "client")
        if not await self.ctx.accounts.has_linked_account(investor_id):
            raise AccountNotLinkedError()
        ident = uuid4()
        version = await self._version(ident, 1, content)
        now = self.ctx.clock.now()
        assert link is not None
        proposal = e.Proposal(
            ident,
            link.id,
            broker_id,
            investor_id,
            e.ProposalStatus.SENT,
            1,
            now,
            now,
            version.created_at,
            version.created_at + timedelta(hours=self.ctx.config.proposal_ttl_hours),
        )
        async with self.ctx.uow() as work:
            current = await work.links.get(id=link.id, for_update=True)
            require_active_link(
                current, await self.ctx.directory.has_role(broker_id, "broker"), "client"
            )
            await work.proposals.insert(proposal)
            await work.versions.insert(version)
            await self.ctx.event(work, "proposal", ident, None, "sent", "broker", broker_id)
        await self._notify(proposal, investor_id)
        return proposal

    async def modify(
        self, broker_id: UUID, ident: UUID, seen_version: int, content: ProposalContent
    ) -> e.Proposal:
        await self.ctx.require_role(broker_id, "broker")
        current = await self._snapshot(broker_id, "broker", ident)
        transition(current.status, e.ProposalAction.MODIFY)
        check_version(current.current_version, seen_version)
        version = await self._version(ident, current.current_version + 1, content)
        async with self._action(
            broker_id, "broker", ident, e.ProposalAction.MODIFY, seen_version
        ) as (work, old):
            updated = replace(
                old,
                status=e.ProposalStatus.SENT,
                current_version=version.version,
                accepted_version=None,
                last_version_at=version.created_at,
                updated_at=self.ctx.clock.now(),
                expires_at=version.created_at + timedelta(hours=self.ctx.config.proposal_ttl_hours),
            )
            await work.versions.insert(version)
            await work.proposals.save(
                updated, status=old.status, current_version=old.current_version
            )
            await self.ctx.event(
                work,
                "proposal",
                ident,
                old.status,
                updated.status,
                "broker",
                broker_id,
                "modified",
                version=version.version,
            )
        await self._notify(updated, updated.investor_id)
        return updated

    async def broker_decide(
        self,
        broker_id: UUID,
        ident: UUID,
        seen_version: int,
        decision: Literal["approve", "decline"],
        evidence_message_ids: tuple[UUID, ...] = (),
        evidence_text: str = "",
    ) -> e.Proposal:
        await self.ctx.require_role(broker_id, "broker")
        current = await self._snapshot(broker_id, "broker", ident)
        if decision == "approve" and current.status == e.ProposalStatus.APPROVED:
            return current
        if decision not in {"approve", "decline"}:
            raise ValidationError("decision")
        action = e.ProposalAction(decision)
        # The first transaction stores immutable attempted evidence for D3 recovery.
        async with self._action(broker_id, "broker", ident, action, seen_version) as (work, old):
            if len(evidence_text) > 1000:
                raise ValidationError("evidence_text")
            for message_id in evidence_message_ids:
                message = await work.messages.get(id=message_id, proposal_id=ident)
                if message is None:
                    raise ValidationError("evidence_message_ids", "outside_thread")
            if (
                decision == "approve"
                and await work.authorizations.get(link_id=old.link_id, revoked_at=None) is None
            ):
                raise TradingAuthorizationRequiredError()
            version = await work.versions.get(proposal_id=ident, version=seen_version)
            assert version is not None
            record = e.ProposalDecision(
                uuid4(),
                ident,
                seen_version,
                broker_id,
                "broker",
                decision,
                self.ctx.clock.now(),
                evidence_message_ids=evidence_message_ids,
                evidence_text=evidence_text,
            )
            previous = await work.decisions.list(
                proposal_id=ident, version=seen_version, decision=decision, actor_id=broker_id
            )
            if previous:
                record = min(previous, key=lambda v: (v.at, v.id))
            else:
                await work.decisions.insert(record)
            if decision == "decline":
                updated = replace(
                    old, status=e.ProposalStatus.DECLINED_BY_BROKER, updated_at=self.ctx.clock.now()
                )
                await work.proposals.save(
                    updated, status=old.status, current_version=old.current_version
                )
                await self.ctx.event(
                    work,
                    "proposal",
                    ident,
                    old.status,
                    updated.status,
                    "broker",
                    broker_id,
                    "decline",
                    decision_id=str(record.id),
                )
            elif not previous:
                await self.ctx.event(
                    work,
                    "proposal",
                    ident,
                    old.status,
                    old.status,
                    "broker",
                    broker_id,
                    "approval_attempted",
                    attempted="approve",
                    version=seen_version,
                    decision_id=str(record.id),
                )
        if decision == "decline":
            await self._notify(updated, updated.investor_id)
            return updated
        command = p.ProposalOrderCommand(
            ident,
            old.investor_id,
            broker_id,
            version.symbol,
            version.side,
            version.qty,
            version.type,
            version.limit_price,
        )
        # No brokers transaction or row lock is held while orders commits or calls Alpaca.
        result = await self.ctx.order_creation.create(command)
        conflict = None
        async with self.ctx.uow() as work:
            await work.links.get(id=old.link_id, for_update=True)
            latest = await work.proposals.get(id=ident, for_update=True)
            if latest is None:
                raise NotFoundError("proposal")
            if latest.status == e.ProposalStatus.APPROVED:
                if isinstance(result, p.OrderCreated) and latest.order_id == result.order_id:
                    return latest
                raise InvalidProposalStateError(latest.status)
            if latest.status != e.ProposalStatus.ACCEPTED or latest.current_version != seen_version:
                details: dict[str, object] = {"attempted": "approve", "version": seen_version}
                if isinstance(result, p.OrderCreated):
                    details.update(orphan_order=True, order_id=str(result.order_id))
                else:
                    details["failure_code"] = result.code
                await self.ctx.event(
                    work,
                    "proposal",
                    ident,
                    latest.status,
                    latest.status,
                    "broker",
                    broker_id,
                    "conversion_raced",
                    attempted="approve",
                    version=seen_version,
                    orphan_order=details.get("orphan_order", False),
                    order_id=details.get("order_id"),
                    failure_code=details.get("failure_code"),
                )
                conflict = latest.status
            else:
                created = isinstance(result, p.OrderCreated)
                target = (
                    e.ProposalStatus.APPROVED if created else e.ProposalStatus.CONVERSION_FAILED
                )
                updated = replace(
                    latest,
                    status=target,
                    updated_at=self.ctx.clock.now(),
                    order_id=result.order_id if isinstance(result, p.OrderCreated) else None,
                    failure_code=result.code if isinstance(result, p.OrderRejected) else None,
                )
                await work.proposals.save(
                    updated, status=latest.status, current_version=seen_version
                )
                await self.ctx.event(
                    work,
                    "proposal",
                    ident,
                    latest.status,
                    target,
                    "broker",
                    broker_id,
                    "approve" if created else updated.failure_code,
                    attempted="approve",
                    decision_id=str(record.id),
                    order_id=str(updated.order_id) if updated.order_id else None,
                )
        if conflict is not None:
            raise InvalidProposalStateError(conflict)
        await self._notify(updated, updated.broker_id, updated.investor_id)
        return updated

    async def investor_decide(
        self,
        investor_id: UUID,
        ident: UUID,
        seen_version: int,
        decision: Literal["accept", "reject"],
        comment: str = "",
        totp_code: str | None = None,
    ) -> e.Proposal:
        await self.ctx.require_role(investor_id, "investor")
        async with self.ctx.uow() as work:
            await self._owned(work, investor_id, "investor", ident)
        if not await self.ctx.accounts.has_linked_account(investor_id):
            raise AccountNotLinkedError()
        if decision not in {"accept", "reject"}:
            raise ValidationError("decision")
        action = e.ProposalAction(decision)
        current = await self._snapshot(investor_id, "investor", ident)
        transition(current.status, action)
        check_version(current.current_version, seen_version)
        if len(comment) > 500:
            raise ValidationError("comment")
        if decision == "accept":
            async with self.ctx.uow() as work:
                version = await work.versions.get(proposal_id=ident, version=seen_version)
            assert version is not None
            threshold = await self.ctx.controls.high_order_threshold_usd(investor_id)
            if requires_totp(version.estimated_cost, threshold):
                if not totp_code or not await self.ctx.totp.verify(investor_id, totp_code):
                    raise ExtraAuthorizationInvalidError()
        async with self._action(investor_id, "investor", ident, action, seen_version) as (
            work,
            old,
        ):
            now = self.ctx.clock.now()
            updated = replace(
                old,
                status=transition(old.status, action),
                updated_at=now,
                accepted_version=seen_version if decision == "accept" else None,
            )
            record = e.ProposalDecision(
                uuid4(), ident, seen_version, investor_id, "investor", decision, now, comment
            )
            await work.decisions.insert(record)
            await work.proposals.save(
                updated, status=old.status, current_version=old.current_version
            )
            await self.ctx.event(
                work,
                "proposal",
                ident,
                old.status,
                updated.status,
                "investor",
                investor_id,
                decision,
                version=seen_version,
                decision_id=str(record.id),
            )
        await self._notify(updated, updated.broker_id)
        return updated

    async def withdraw(
        self, broker_id: UUID, ident: UUID, seen_version: int, reason: str, confirmed: bool
    ) -> e.Proposal:
        await self.ctx.require_role(broker_id, "broker")
        async with self._action(
            broker_id, "broker", ident, e.ProposalAction.WITHDRAW, seen_version
        ) as (work, old):
            if confirmed is not True:
                raise ConfirmationRequiredError()
            if not 1 <= len(reason.strip()) <= 500:
                raise ValidationError("reason")
            updated = replace(
                old,
                status=e.ProposalStatus.WITHDRAWN,
                status_reason=reason,
                updated_at=self.ctx.clock.now(),
            )
            await work.proposals.save(
                updated, status=old.status, current_version=old.current_version
            )
            await self.ctx.event(
                work, "proposal", ident, old.status, updated.status, "broker", broker_id, reason
            )
        await self._notify(updated, updated.investor_id)
        return updated
