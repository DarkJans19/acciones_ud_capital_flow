"""Real email channel sender over SMTP (RF-26, criterion 14.15)."""

from email.message import EmailMessage

import aiosmtplib

from acciones_ud.market_data.domain.entities import Notification, Recipient
from acciones_ud.market_data.domain.notifications import NoDestinationError


def _body(notification: Notification) -> str:
    lines = [f"Event: {notification.event_type}"]
    for key in sorted(notification.payload):
        lines.append(f"{key}: {notification.payload[key]}")
    return "\n".join(lines)


class SmtpEmailSender:
    channel = "email"

    def __init__(
        self,
        host: str,
        port: int,
        user: str | None,
        password: str | None,
        from_addr: str,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_addr = from_addr

    async def send(self, recipient: Recipient, notification: Notification) -> None:
        if recipient.email is None:
            raise NoDestinationError("recipient has no email address")
        message = EmailMessage()
        message["From"] = self.from_addr
        message["To"] = recipient.email
        message["Subject"] = f"Acciones UD: {notification.event_type}"
        message.set_content(_body(notification))
        await aiosmtplib.send(
            message,
            hostname=self.host,
            port=self.port,
            username=self.user or None,
            password=self.password or None,
        )
