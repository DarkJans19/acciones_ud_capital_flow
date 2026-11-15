import pytest

from acciones_ud.shared.domain.errors import AppError
from acciones_ud.shared.infrastructure.http_errors import ORDER_HTTP_STATUSES, error_body_response


@pytest.mark.parametrize("code,status", list(ORDER_HTTP_STATUSES.items()))
def test_order_error_http_contract(code, status) -> None:
    response = error_body_response(AppError(status, code, "Order operation failed."))
    assert response.status_code == status
    assert code.encode() in response.body
