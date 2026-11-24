import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.identity.domain.rbac import protect_permission
from acciones_ud.shared.domain.errors import AppError, ErrorCode


# Feature: admin-mod-07, Property 18: Protección de permisos administrativos
@settings(max_examples=100)
@given(
    st.sampled_from(["investor", "broker", "administrator", "auditor", "analyst"]),
    st.one_of(
        st.sampled_from(
            [
                "admin:fees",
                "admin:audit",
                "admin:compliance:read",
                "admin:bi",
                "admin:rbac",
                "admin:users",
                "admin:compliance",
                "market:read",
            ]
        ),
        st.text(min_size=1, max_size=40),
    ),
    st.booleans(),
)
def test_closed_administrative_role_allowlist(role, permission, remove):
    read_allowed = {
        "admin:audit": {"administrator", "auditor"},
        "admin:compliance:read": {"administrator", "auditor"},
        "admin:bi": {"administrator", "analyst"},
    }
    protected = (
        not remove
        and permission.startswith("admin:")
        and role not in read_allowed.get(permission, {"administrator"})
    ) or (remove and role == "administrator" and permission == "admin:rbac")
    if protected:
        with pytest.raises(AppError) as caught:
            protect_permission(role, permission, remove)
        assert caught.value.code == ErrorCode.PROTECTED_PERMISSION
    else:
        protect_permission(role, permission, remove)
