from typing import Literal

from starlette.responses import Response

from acciones_ud.config.settings import Settings, get_settings

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"


def set_auth_cookies(
    response: Response,
    access: str,
    refresh: str,
    settings: Settings | None = None,
) -> None:
    config = settings or get_settings()
    same_site: Literal["lax", "strict"] = "strict" if config.cookie_samesite == "strict" else "lax"
    for name, value, path, ttl in (
        (ACCESS_COOKIE, access, "/", config.access_token_ttl_seconds),
        (REFRESH_COOKIE, refresh, "/api/v1/auth", config.refresh_token_ttl_seconds),
    ):
        response.set_cookie(
            name,
            value,
            path=path,
            max_age=int(ttl or "0"),
            secure=True,
            httponly=True,
            samesite=same_site,
            domain=config.cookie_domain,
        )


def clear_auth_cookies(response: Response, settings: Settings | None = None) -> None:
    config = settings or get_settings()
    same_site: Literal["lax", "strict"] = "strict" if config.cookie_samesite == "strict" else "lax"
    for name, path in ((ACCESS_COOKIE, "/"), (REFRESH_COOKIE, "/api/v1/auth")):
        response.delete_cookie(
            name,
            path=path,
            domain=config.cookie_domain,
            secure=True,
            httponly=True,
            samesite=same_site,
        )
