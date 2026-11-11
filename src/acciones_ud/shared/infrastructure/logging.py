import json
import logging
from collections.abc import Iterable
from contextvars import ContextVar
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from pydantic import SecretStr
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from acciones_ud.config.settings import Settings

request_id: ContextVar[str] = ContextVar("request_id", default="")


class SecretRedactionFilter(logging.Filter):
    def __init__(self, secrets: Iterable[str]) -> None:
        super().__init__()
        self.secrets = sorted({x for x in secrets if x}, key=len, reverse=True)

    def redact(self, value: str) -> str:
        for secret in self.secrets:
            value = value.replace(secret, "***")
        return value

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self.redact(record.getMessage())
        record.args = ()
        # Do not emit exception objects: they may contain arbitrary request secrets.
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "level": record.levelname,
                "message": record.getMessage(),
                "request_id": getattr(record, "request_id", request_id.get()),
            }
        )


def configure_logging(settings: Settings) -> None:
    secrets = [v.get_secret_value() for v in settings.__dict__.values() if isinstance(v, SecretStr)]
    for url in (settings.database_url, settings.migration_database_url):
        if url:
            try:
                password = urlsplit(url).password
                if password:
                    secrets.extend((password, unquote(password)))
            except ValueError:
                pass
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(SecretRedactionFilter(secrets))
    root = logging.getLogger()
    # Replace only our handler; leave host application / test handlers intact.
    for old in root.handlers[:]:
        if isinstance(old.formatter, JsonFormatter):
            root.removeHandler(old)
    root.addHandler(handler)
    root.setLevel(settings.log_level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        value = str(uuid4())
        scope.setdefault("state", {})["request_id"] = value
        token = request_id.set(value)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = [
                    *message.get("headers", []),
                    (b"x-request-id", value.encode()),
                ]
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id.reset(token)
