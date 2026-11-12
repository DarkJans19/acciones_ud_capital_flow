from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from acciones_ud.identity.adapters.inbound.http.deps import require_permission
from acciones_ud.identity.adapters.inbound.http.schemas.admin import (
    AssignmentIn,
    BrokerActivationOut,
    CreateAssignmentIn,
    PermissionIn,
    PermissionOut,
    PremiumIn,
    PremiumOut,
    RoleAssignmentOut,
    RoleOut,
)
from acciones_ud.identity.adapters.inbound.http.schemas.auth import RegisterBaseIn, RegistrationOut
from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(prefix="/admin", tags=["identity administration"])
RbacUser = Annotated[CurrentUser, Depends(require_permission("admin:rbac"))]
AdminUser = Annotated[CurrentUser, Depends(require_permission("admin:users"))]


@router.post(
    "/users/administrators",
    status_code=201,
    response_model=RegistrationOut,
    responses=error_responses(401, 403, 409, 422, 503),
)
async def create_administrator(
    body: RegisterBaseIn,
    request: Request,
    user: Annotated[CurrentUser, Depends(require_permission("admin:users"))],
) -> dict[str, object]:
    from acciones_ud.identity.composition import registration_service

    if "administrator" not in user.roles:
        raise AppError(403, ErrorCode.FORBIDDEN, "Administrator role required.")
    return await registration_service(request).create_administrator(body.model_dump())


@router.post(
    "/users/{user_id}/broker-activation",
    response_model=BrokerActivationOut,
    responses=error_responses(401, 403, 404, 409, 422, 503),
)
async def activate_broker(user_id: UUID, request: Request, user: AdminUser) -> Record:
    from acciones_ud.identity.composition import broker_activation_service

    if "administrator" not in user.roles:
        raise AppError(403, ErrorCode.FORBIDDEN, "Administrator role required.")
    return await broker_activation_service(request).activate(user.user_id, user_id)


@router.put(
    "/users/{user_id}/premium",
    response_model=PremiumOut,
    responses=error_responses(401, 403, 404, 422, 503),
)
async def premium(user_id: UUID, body: PremiumIn, request: Request, user: AdminUser) -> Record:
    from acciones_ud.identity.composition import rbac_service

    return await rbac_service(request).premium(user_id, body.is_premium)


@router.get(
    "/users/{user_id}/roles",
    response_model=list[RoleAssignmentOut],
    responses=error_responses(401, 403, 404, 422, 503),
)
async def assignments(user_id: UUID, request: Request, user: RbacUser) -> list[Record]:
    from acciones_ud.identity.composition import rbac_service

    return await rbac_service(request).assignments(user_id)


@router.post(
    "/users/{user_id}/roles",
    status_code=201,
    response_model=RoleAssignmentOut,
    responses=error_responses(401, 403, 404, 422, 503),
)
async def create_assignment(
    user_id: UUID, body: CreateAssignmentIn, request: Request, user: RbacUser
) -> Record:
    from acciones_ud.identity.composition import rbac_service

    if body.role in {"broker", "administrator"} and "administrator" not in user.roles:
        raise AppError(403, ErrorCode.FORBIDDEN, "Administrator role required.")
    return await rbac_service(request).save(
        user_id, body.role, body.valid_from, body.valid_to, None
    )


@router.put(
    "/users/{user_id}/roles/{assignment_id}",
    response_model=RoleAssignmentOut,
    responses=error_responses(401, 403, 404, 409, 422, 503),
)
async def update_assignment(
    user_id: UUID, assignment_id: UUID, body: AssignmentIn, request: Request, user: RbacUser
) -> Record:
    from acciones_ud.identity.composition import rbac_service

    return await rbac_service(request).save(
        user_id, None, body.valid_from, body.valid_to, assignment_id
    )


@router.post(
    "/users/{user_id}/roles/{assignment_id}/revoke",
    response_model=RoleAssignmentOut,
    responses=error_responses(401, 403, 404, 409, 422, 503),
)
async def revoke_assignment(
    user_id: UUID, assignment_id: UUID, request: Request, user: RbacUser
) -> Record:
    from acciones_ud.identity.composition import rbac_service

    return await rbac_service(request).save(
        user_id, None, None, None, assignment_id, revoke=True, actor_id=user.user_id
    )


@router.get("/roles", response_model=list[RoleOut], responses=error_responses(401, 403, 503))
async def roles(request: Request, user: RbacUser) -> list[Record]:
    from acciones_ud.identity.composition import rbac_service

    return await rbac_service(request).roles()


@router.get(
    "/permissions", response_model=list[PermissionOut], responses=error_responses(401, 403, 503)
)
async def permissions(request: Request, user: RbacUser) -> list[Record]:
    from acciones_ud.identity.composition import rbac_service

    return await rbac_service(request).permissions()


@router.post(
    "/roles/{role}/permissions",
    response_model=RoleOut,
    responses=error_responses(401, 403, 404, 422, 503),
)
async def add_permission(role: str, body: PermissionIn, request: Request, user: RbacUser) -> Record:
    from acciones_ud.identity.composition import rbac_service

    return await rbac_service(request).change_permission(role, body.permission_code, False)


@router.delete(
    "/roles/{role}/permissions/{permission_code}",
    response_model=RoleOut,
    responses=error_responses(401, 403, 404, 422, 503),
)
async def remove_permission(
    role: str, permission_code: str, request: Request, user: RbacUser
) -> Record:
    from acciones_ud.identity.composition import rbac_service

    return await rbac_service(request).change_permission(role, permission_code, True)
