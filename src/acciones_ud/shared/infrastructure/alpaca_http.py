import httpx

from acciones_ud.shared.domain.alpaca_errors import classify


def build_client(base_url: str, key: str, secret: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=base_url,
        auth=httpx.BasicAuth(key, secret),
        timeout=httpx.Timeout(10),
        follow_redirects=False,
    )


def raise_for_alpaca(response: httpx.Response) -> None:
    if not response.is_success:
        raise classify(response.status_code)
