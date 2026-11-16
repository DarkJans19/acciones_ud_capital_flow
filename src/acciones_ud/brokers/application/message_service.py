from dataclasses import asdict
from typing import Literal
from uuid import UUID, uuid4

from acciones_ud.brokers.application.context import BrokerContext
from acciones_ud.brokers.application.proposal_service import ProposalService
from acciones_ud.brokers.domain.entities import ProposalMessage
from acciones_ud.brokers.domain.errors import ValidationError
from acciones_ud.orders.domain.model import Raw


class MessageService:
    def __init__(self, context: BrokerContext) -> None:
        self.ctx, self.proposals = context, ProposalService(context)

    async def post(
        self, actor: UUID, role: Literal["investor", "broker"], proposal_id: UUID, body: str
    ) -> ProposalMessage:
        await self.ctx.require_role(actor, role)
        async with self.ctx.uow() as work:
            proposal = await self.proposals._owned(work, actor, role, proposal_id, active=True)
            if not 1 <= len(body.strip()) or len(body) > 1000:
                raise ValidationError("body")
            message = ProposalMessage(uuid4(), proposal_id, actor, body, self.ctx.clock.now())
            await work.messages.insert(message)
        recipient = proposal.investor_id if role == "broker" else proposal.broker_id
        await self.ctx.notify(
            recipient, "proposal_updates", proposal_id=str(proposal_id), message_id=str(message.id)
        )
        return message

    async def thread(
        self,
        actor: UUID,
        role: Literal["investor", "broker"],
        proposal_id: UUID,
        cursor: str | None = None,
        page_size: int = 20,
    ) -> Raw:
        await self.ctx.require_role(actor, role)
        async with self.ctx.uow() as work:
            await self.proposals._owned(work, actor, role, proposal_id)
            values, token = await work.messages.page(proposal_id, cursor, page_size)
        return {"items": [asdict(v) for v in values], "next_cursor": token}
