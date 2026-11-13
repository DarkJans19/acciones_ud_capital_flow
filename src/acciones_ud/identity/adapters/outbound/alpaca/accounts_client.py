from urllib.parse import quote

import httpx
from pydantic import AwareDatetime, BaseModel, Field, ValidationError

from acciones_ud.identity.adapters.outbound.alpaca.kyc_mapping import account_opening_document
from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.identity.domain.kyc import AlpacaAccount, AlpacaAccountSummary
from acciones_ud.identity.domain.kyc_submission import AccountOpeningRequest
from acciones_ud.identity.domain.redaction import redact
from acciones_ud.shared.domain.alpaca_errors import (
    AlpacaUnavailable,
    AlpacaValidationError,
    classify,
)
from acciones_ud.shared.infrastructure.alpaca_http import raise_for_alpaca


class AccountResponse(BaseModel):
    id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    updated_at: AwareDatetime | None = None


class ContactResponse(BaseModel):
    email_address: str | None = None


class AccountListResponse(AccountResponse):
    contact: ContactResponse | None = None


class AlpacaAccountsClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def create_account(self, request: AccountOpeningRequest | Record) -> AlpacaAccount:
        if isinstance(request, AccountOpeningRequest):
            request = account_opening_document(request)
        tax_id = str(request.get("identity", {}).get("tax_id", ""))
        return await self._request("POST", "/v1/accounts", request, tax_id=tax_id)

    async def get_account(self, account_id: str, timeout: float = 10) -> AlpacaAccount:
        return await self._request(
            "GET", "/v1/accounts/" + quote(account_id, safe=""), timeout=timeout
        )

    async def list_accounts(
        self, query: str, timeout: float = 10
    ) -> list[AlpacaAccountSummary]:
        try:
            response = await self.client.get(
                "/v1/accounts",
                params={"query": query, "entities": "contact"},
                timeout=timeout,
            )
        except httpx.RequestError as exc:
            raise classify(exc) from None
        raise_for_alpaca(response)
        try:
            documents = response.json()
            if not isinstance(documents, list):
                raise ValueError()
            accounts = [AccountListResponse.model_validate(item) for item in documents]
        except (ValidationError, ValueError, TypeError):
            raise AlpacaUnavailable() from None
        return [
            AlpacaAccountSummary(
                item.id,
                item.status,
                item.updated_at,
                item.contact.email_address if item.contact else None,
            )
            for item in accounts
        ]

    async def _request(
        self,
        method: str,
        path: str,
        body: Record | None = None,
        *,
        tax_id: str = "",
        timeout: float = 10,
    ) -> AlpacaAccount:
        try:
            response = await self.client.request(method, path, json=body, timeout=timeout)
        except httpx.RequestError as exc:
            raise classify(exc) from None
        if method == "POST" and response.status_code in {400, 409, 422}:
            message = "Alpaca rejected the submitted data."
            try:
                document = response.json()
                if isinstance(document, dict) and isinstance(document.get("message"), str):
                    message = redact(document["message"], tax_id)
            except ValueError:
                pass
            raise AlpacaValidationError(message)
        raise_for_alpaca(response)
        try:
            doc = AccountResponse.model_validate(response.json())
        except (ValidationError, ValueError):
            raise AlpacaUnavailable() from None
        return AlpacaAccount(doc.id, doc.status, doc.updated_at)
