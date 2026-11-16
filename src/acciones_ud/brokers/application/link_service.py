from dataclasses import asdict, replace
from datetime import timedelta
from typing import Literal
from uuid import UUID, uuid4

from acciones_ud.brokers.application.context import BrokerContext
from acciones_ud.brokers.application.directory_service import DirectoryService
from acciones_ud.brokers.domain import entities as e
from acciones_ud.brokers.domain import ports as p
from acciones_ud.brokers.domain.errors import (
    BrokerNotFoundError,
    ConfirmationRequiredError,
    ConsentRequiredError,
    InvalidLinkStateError,
    LinkAlreadyExistsError,
    NotFoundError,
    ValidationError,
)
from acciones_ud.brokers.domain.link_state_machine import effective_status, is_open, transition
from acciones_ud.brokers.domain.periods import to_utc_range
from acciones_ud.orders.domain.model import Raw


class LinkService:
    def __init__(self, context: BrokerContext) -> None:
        self.ctx = context

    async def _owned(
        self, work: p.BrokerWork, actor: UUID, role: Literal["broker", "investor"], ident: UUID
    ) -> e.Link:
        link = await work.links.get(id=ident, for_update=True)
        if link is None or getattr(link, f"{role}_id") != actor:
            raise NotFoundError("link")
        return link

    async def _expire(self, work: p.BrokerWork, link: e.Link) -> e.Link:
        status = effective_status(link, self.ctx.clock.now(), self.ctx.config.link_ttl_days)
        if status != link.status:
            updated = replace(link, status=status, responded_at=link.expires_at)
            if await work.links.save(updated, status=e.LinkStatus.REQUESTED):
                await self.ctx.event(
                    work, "link", link.id, link.status, status, "system", None, "ttl"
                )
            return updated
        return link

    async def _notify_expired(self, link: e.Link) -> None:
        await self.ctx.notify(
            link.investor_id, "broker_link_updates", link_id=str(link.id), status="expired"
        )

    async def request_link(
        self, investor_id: UUID, broker_id: UUID, consent_accepted: bool
    ) -> e.Link:
        await self.ctx.require_role(investor_id, "investor")
        if consent_accepted is not True:
            raise ConsentRequiredError()
        if investor_id == broker_id:
            raise ValidationError("broker_id", "self_link")
        if await self.ctx.directory.get_broker(broker_id) is None:
            raise BrokerNotFoundError()
        now = self.ctx.clock.now()
        expired = None
        async with self.ctx.uow() as work:
            await work.lock_investor(investor_id)
            previous = await work.links.open_for(investor_id, for_update=True)
            if previous:
                previous = await self._expire(work, previous)
                if is_open(previous.status):
                    raise LinkAlreadyExistsError()
                expired = previous
            link = e.Link(
                uuid4(),
                investor_id,
                broker_id,
                e.LinkStatus.REQUESTED,
                now,
                now + timedelta(days=self.ctx.config.link_ttl_days),
                self.ctx.config.link_consent_version,
                now,
            )
            await work.links.insert(link)
            await self.ctx.event(work, "link", link.id, None, link.status, "investor", investor_id)
        if expired:
            await self._notify_expired(expired)
        await self.ctx.notify(
            broker_id, "broker_link_updates", link_id=str(link.id), status=link.status
        )
        return link

    async def _respond(
        self,
        actor: UUID,
        role: Literal["investor", "broker"],
        ident: UUID,
        action: e.LinkAction,
        reason: str | None = None,
    ) -> e.Link:
        await self.ctx.require_role(actor, role)
        if action == e.LinkAction.DECLINE and (
            reason is None or not 1 <= len(reason.strip()) <= 500
        ):
            raise ValidationError("reason")
        expired = False
        async with self.ctx.uow() as work:
            original = await self._owned(work, actor, role, ident)
            link = await self._expire(work, original)
            expired = link.status != original.status
            if not expired:
                status = transition(link.status, action)
                now = self.ctx.clock.now()
                link = replace(
                    link,
                    status=status,
                    responded_at=now,
                    started_at=now if status == e.LinkStatus.ACTIVE else None,
                    decline_reason=reason if status == e.LinkStatus.DECLINED else None,
                )
                await work.links.save(link, status=original.status)
                await self.ctx.event(
                    work, "link", ident, original.status, status, role, actor, reason
                )
        if expired:
            await self._notify_expired(link)
            raise InvalidLinkStateError(link.status)
        recipient = link.investor_id if role == "broker" else link.broker_id
        await self.ctx.notify(
            recipient, "broker_link_updates", link_id=str(ident), status=link.status
        )
        return link

    async def accept(self, broker_id: UUID, link_id: UUID) -> e.Link:
        return await self._respond(broker_id, "broker", link_id, e.LinkAction.ACCEPT)

    async def decline(self, broker_id: UUID, link_id: UUID, reason: str) -> e.Link:
        return await self._respond(broker_id, "broker", link_id, e.LinkAction.DECLINE, reason)

    async def cancel(self, investor_id: UUID, link_id: UUID) -> e.Link:
        return await self._respond(investor_id, "investor", link_id, e.LinkAction.CANCEL)

    async def view(self, link: e.Link) -> Raw:
        broker = await self.ctx.directory.get_broker(link.broker_id)
        result = asdict(
            replace(
                link,
                status=effective_status(link, self.ctx.clock.now(), self.ctx.config.link_ttl_days),
            )
        )
        result["broker"] = {
            "id": link.broker_id,
            "name": broker.name
            if broker
            else await self.ctx.directory.display_name(link.broker_id) or "",
            "firm_name": broker.firm_name if broker else "",
        }
        return result

    async def pending_requests(self, broker_id: UUID) -> list[Raw]:
        await self.ctx.require_role(broker_id, "broker")
        async with self.ctx.uow() as work:
            values = await work.links.list(broker_id=broker_id, status=e.LinkStatus.REQUESTED)
        result = []
        for link in sorted(values, key=lambda v: (v.requested_at, v.id), reverse=True):
            if (
                effective_status(link, self.ctx.clock.now(), self.ctx.config.link_ttl_days)
                == e.LinkStatus.REQUESTED
            ):
                result.append(
                    {
                        "id": link.id,
                        "investor_id": link.investor_id,
                        "investor_name": await self.ctx.directory.display_name(link.investor_id)
                        or "",
                        "requested_at": link.requested_at,
                    }
                )
        return result

    async def current(self, investor_id: UUID) -> Raw:
        await self.ctx.require_role(investor_id, "investor")
        async with self.ctx.uow() as work:
            link = await work.links.open_for(investor_id)
            if link and not is_open(
                effective_status(link, self.ctx.clock.now(), self.ctx.config.link_ttl_days)
            ):
                link = None
            authorization = (
                await work.authorizations.get(link_id=link.id, revoked_at=None) if link else None
            )
        pending = link is None and await self.ctx.requests.broker_requested(investor_id)
        return {
            "link": await self.view(link) if link else None,
            "trading_authorization": asdict(authorization) if authorization else None,
            "pending_broker_selection": pending,
            "suggestions": await DirectoryService(self.ctx).suggestions(investor_id)
            if pending
            else [],
        }

    async def history(
        self,
        investor_id: UUID,
        status: e.LinkStatus | None = None,
        period: e.Period | None = None,
        cursor: str | None = None,
        page_size: int = 20,
    ) -> Raw:
        await self.ctx.require_role(investor_id, "investor")
        start, end = to_utc_range(period) if period else (None, None)
        if status is not None:
            try:
                status = e.LinkStatus(status)
            except ValueError:
                raise ValidationError("status") from None
        async with self.ctx.uow() as work:
            links, token = await work.links.page(
                investor_id, status, start, end, self.ctx.clock.now(), cursor, page_size
            )
        return {"items": [await self.view(link) for link in links], "next_cursor": token}

    async def _active_for_authorization(
        self, work: p.BrokerWork, investor: UUID, ident: UUID
    ) -> e.Link:
        link = await self._owned(work, investor, "investor", ident)
        if link.status != e.LinkStatus.ACTIVE or not await self.ctx.directory.has_role(
            link.broker_id, "broker"
        ):
            raise InvalidLinkStateError(link.status)
        return link

    async def grant_trading(
        self, investor_id: UUID, link_id: UUID, consent_accepted: bool
    ) -> e.TradingAuthorization:
        await self.ctx.require_role(investor_id, "investor")
        async with self.ctx.uow() as work:
            link = await self._active_for_authorization(work, investor_id, link_id)
            if consent_accepted is not True:
                raise ConsentRequiredError()
            existing = await work.authorizations.get(
                link_id=link_id, revoked_at=None, for_update=True
            )
            if existing:
                return existing
            authorization = e.TradingAuthorization(
                uuid4(), link_id, self.ctx.config.trading_consent_version, self.ctx.clock.now()
            )
            await work.authorizations.insert(authorization)
            await self.ctx.event(
                work,
                "trading_authorization",
                authorization.id,
                None,
                "active",
                "investor",
                investor_id,
            )
        await self.ctx.notify(
            link.broker_id, "broker_link_updates", link_id=str(link_id), authorization="granted"
        )
        return authorization

    async def revoke_trading(self, investor_id: UUID, link_id: UUID) -> e.TradingAuthorization:
        await self.ctx.require_role(investor_id, "investor")
        async with self.ctx.uow() as work:
            link = await self._owned(work, investor_id, "investor", link_id)
            authorization = await work.authorizations.get(
                link_id=link_id, revoked_at=None, for_update=True
            )
            if authorization is None:
                raise InvalidLinkStateError(link.status, "no_active_authorization")
            updated = replace(
                authorization, revoked_at=self.ctx.clock.now(), revoke_reason="investor"
            )
            if not await work.authorizations.save(updated, revoked_at=None):
                raise InvalidLinkStateError(link.status, "authorization_changed")
            await self.ctx.event(
                work,
                "trading_authorization",
                updated.id,
                "active",
                "revoked",
                "investor",
                investor_id,
                "investor",
            )
        await self.ctx.notify(
            link.broker_id, "broker_link_updates", link_id=str(link_id), authorization="revoked"
        )
        return updated

    async def set_order_review(self, investor_id: UUID, link_id: UUID, enabled: bool) -> e.Link:
        await self.ctx.require_role(investor_id, "investor")
        if type(enabled) is not bool:
            raise ValidationError("enabled")
        async with self.ctx.uow() as work:
            link = await self._active_for_authorization(work, investor_id, link_id)
            if link.order_review_enabled == enabled:
                return link
            updated = replace(link, order_review_enabled=enabled)
            await work.links.save(updated, status=e.LinkStatus.ACTIVE)
            await self.ctx.event(
                work,
                "link",
                link_id,
                link.status,
                link.status,
                "investor",
                investor_id,
                "order_review_changed",
                previous_enabled=link.order_review_enabled,
                enabled=enabled,
            )
        return updated

    async def end_link(
        self, investor_id: UUID, link_id: UUID, reason: str, confirmed: bool
    ) -> e.Link:
        await self.ctx.require_role(investor_id, "investor")
        if confirmed is not True:
            raise ConfirmationRequiredError()
        if not 1 <= len(reason.strip()) <= 500:
            raise ValidationError("reason")
        withdrawn = []
        async with self.ctx.uow() as work:
            link = await self._owned(work, investor_id, "investor", link_id)
            status = transition(link.status, e.LinkAction.END)
            now = self.ctx.clock.now()
            updated = replace(link, status=status, ended_at=now, end_reason=reason)
            authorization = await work.authorizations.get(
                link_id=link_id, revoked_at=None, for_update=True
            )
            if authorization:
                revoked = replace(authorization, revoked_at=now, revoke_reason="link_ended")
                if not await work.authorizations.save(revoked, revoked_at=None):
                    raise InvalidLinkStateError(link.status, "authorization_changed")
                await self.ctx.event(
                    work,
                    "trading_authorization",
                    revoked.id,
                    "active",
                    "revoked",
                    "investor",
                    investor_id,
                    "link_ended",
                )
            await work.links.save(updated, status=link.status)
            await self.ctx.event(
                work, "link", link.id, link.status, status, "investor", investor_id, reason
            )
            for proposal in await work.proposals.list(link_id=link_id):
                if proposal.status in {e.ProposalStatus.SENT, e.ProposalStatus.ACCEPTED}:
                    value = replace(
                        proposal,
                        status=e.ProposalStatus.WITHDRAWN,
                        status_reason="link_ended",
                        updated_at=now,
                    )
                    if await work.proposals.save(
                        value, status=proposal.status, current_version=proposal.current_version
                    ):
                        withdrawn.append(value)
                        await self.ctx.event(
                            work,
                            "proposal",
                            value.id,
                            proposal.status,
                            value.status,
                            "investor",
                            investor_id,
                            "link_ended",
                        )
        await self.ctx.notify(
            link.broker_id, "broker_link_updates", link_id=str(link_id), status="ended"
        )
        if authorization:
            await self.ctx.notify(
                link.broker_id, "broker_link_updates", link_id=str(link_id), authorization="revoked"
            )
        for proposal in withdrawn:
            for recipient in (proposal.broker_id, proposal.investor_id):
                await self.ctx.notify(
                    recipient,
                    "proposal_updates",
                    proposal_id=str(proposal.id),
                    status="withdrawn",
                    reason="link_ended",
                )
        return updated
