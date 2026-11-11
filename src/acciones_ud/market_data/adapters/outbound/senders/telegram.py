"""Real Telegram channel sender over the Bot API (RF-26, criterion 14.16)."""

import httpx

from acciones_ud.market_data.domain.entities import Notification, Recipient
from acciones_ud.market_data.domain.notifications import NoDestinationError

API_BASE = "https://api.telegram.org"


def _text(notification: Notification) -> str:
    lines = [f"Event: {notification.event_type}"]
    for key in sorted(notification.payload):
        lines.append(f"{key}: {notification.payload[key]}")
    return "\n".join(lines)


def build_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=API_BASE,
        timeout=httpx.Timeout(10),
        follow_redirects=False,
    )


class TelegramBotSender:
    channel = "telegram"

    def __init__(self, token: str, client: httpx.AsyncClient | None = None) -> None:
        self.token = token
        self.client = client

    async def send(self, recipient: Recipient, notification: Notification) -> None:
        if recipient.telegram_chat_id is None:
            raise NoDestinationError("recipient has no telegram chat id")
        payload = {"chat_id": recipient.telegram_chat_id, "text": _text(notification)}
        path = f"/bot{self.token}/sendMessage"
        if self.client is not None:
            response = await self.client.post(path, json=payload)
            response.raise_for_status()
            return
        async with build_client() as client:
            response = await client.post(path, json=payload)
            response.raise_for_status()
