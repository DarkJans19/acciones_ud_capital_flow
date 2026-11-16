import pytest

from acciones_ud.shared.domain.errors import AppError
from acciones_ud.shared.infrastructure.http_errors import BROKERS_HTTP_STATUSES, error_body_response


@pytest.mark.parametrize("code,status", list(BROKERS_HTTP_STATUSES.items()))
def test_broker_error_http_contract(code, status):
    response = error_body_response(AppError(500, code, "Broker operation failed."))
    assert response.status_code == status
    assert code.encode() in response.body
