from acciones_ud.brokers.domain.ports import (
    OrderCreated,
    OrderCreationPort,
    OrderRejected,
    ProposalOrderCommand,
)


class OrderCreation:
    def __init__(self, port: OrderCreationPort) -> None:
        self.port = port

    async def create(self, command: ProposalOrderCommand) -> OrderCreated | OrderRejected:
        return await self.port.create(command)
