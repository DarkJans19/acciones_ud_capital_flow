from fastapi import Request

from acciones_ud.shared.domain.audit_entry import RequestMeta


def request_meta(request: Request) -> RequestMeta:
    return RequestMeta(
        request.client.host[:64] if request.client else None,
        getattr(request.state, "request_id", None),
    )
