from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Request

from acciones_ud.admin.adapters.inbound.http import schemas as s
from acciones_ud.admin.adapters.inbound.http.audit_router import GUARANTEE
from acciones_ud.admin.adapters.inbound.http.commissions_router import From, Size, To
from acciones_ud.admin.adapters.inbound.http.deps import (
    AuditRoute,
    ComplianceAdmin,
    ComplianceReader,
)
from acciones_ud.admin.domain.periods import Period
from acciones_ud.admin.domain.reports import canonical_value
from acciones_ud.shared.infrastructure.http_errors import error_responses
from acciones_ud.shared.infrastructure.request_meta import request_meta

router = APIRouter(
    prefix="/admin/compliance",
    tags=["admin-compliance"],
    route_class=AuditRoute,
    responses=error_responses(401, 403, 404, 409, 422, 503),
)


@router.post("/restrictions", response_model=s.RestrictionOut, status_code=201)
async def restrict(body: s.RestrictIn, request: Request, user: ComplianceAdmin) -> object:
    return canonical_value(
        await request.app.state.admin_restrictions.restrict(
            body.user_id,
            body.reason,
            body.evidence_text,
            [r.model_dump() for r in body.evidence_refs],
            user.user_id,
            body.totp_code,
            request_meta(request),
        )
    )


@router.post("/restrictions/{restriction_id}/lift", response_model=s.RestrictionOut)
async def lift(
    restriction_id: UUID, body: s.AdminEvidenceIn, request: Request, user: ComplianceAdmin
) -> object:
    return canonical_value(
        await request.app.state.admin_restrictions.lift(
            restriction_id,
            body.reason,
            body.evidence_text,
            [r.model_dump() for r in body.evidence_refs],
            user.user_id,
            body.totp_code,
            request_meta(request),
        )
    )


@router.get("/restrictions", response_model=s.AdminPageOut[s.RestrictionOut])
async def restrictions(
    request: Request,
    user: ComplianceReader,
    user_id: UUID | None = None,
    status: str | None = None,
    cursor: str | None = None,
    page_size: Size = 20,
) -> object:
    return canonical_value(
        await request.app.state.admin_restrictions.page(user_id, status, cursor, page_size)
    )


@router.get("/atypical-operations", response_model=s.AtypicalPage)
async def atypical(
    request: Request,
    user: ComplianceReader,
    from_: From,
    to: To,
    user_id: UUID | None = None,
    min_amount: Decimal | None = None,
    cursor: str | None = None,
    page_size: Size = 20,
) -> object:
    return canonical_value(
        await request.app.state.admin_compliance.atypical(
            Period(from_, to), user_id, min_amount, cursor, page_size
        )
    )


@router.post(
    "/users/{user_id}/audit-reports", response_model=s.ComplianceReportOut, status_code=201
)
async def generate(
    user_id: UUID, body: s.ComplianceReportIn, request: Request, user: ComplianceAdmin
) -> object:
    return canonical_value(
        await request.app.state.admin_compliance.generate_report(
            user_id, Period(body.from_, body.to), user.user_id, request_meta(request)
        )
    )


@router.get(
    "/audit-reports/{report_id}", response_model=s.ComplianceReportOut, description=GUARANTEE
)
async def get_report(report_id: UUID, request: Request, user: ComplianceReader) -> object:
    return canonical_value(await request.app.state.admin_compliance.get_report(report_id))


@router.get("/users/{user_id}/audit-reports", response_model=s.AdminPageOut[s.ComplianceReportOut])
async def reports(
    user_id: UUID,
    request: Request,
    user: ComplianceReader,
    cursor: str | None = None,
    page_size: Size = 20,
) -> object:
    return canonical_value(
        await request.app.state.admin_compliance.reports_for_user(user_id, cursor, page_size)
    )
