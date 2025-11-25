# app/api/endpoints/approvals.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.schemas.approval_summary import ApprovalSummary
from app.models.student import Student
from app.models.department import Department
from app.models.user import User

from sqlalchemy import text
from sqlmodel import select

from app.api.deps import get_db_session
from app.core.rbac import AllowRoles
from app.models.user import User, UserRole
from app.models.application import Application
from app.models.application_stage import ApplicationStage

from app.schemas.approval import StageActionRequest, StageActionResponse
from app.services.approval_service import approve_stage, reject_stage

router = APIRouter(
    prefix="/api/approvals",
    tags=["Approvals"]
)


# LIST ALL APPLICATIONS
@router.get("/all")
async def list_all_applications(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(AllowRoles(UserRole.Admin, UserRole.HOD, UserRole.Office, UserRole.CellMember)),
):
    result = await session.execute(select(Application))
    return result.scalars().all()


# GET APPLICATION DETAILS + STAGES
@router.get("/{app_id}")
async def get_application_details(
    app_id: str,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(AllowRoles(UserRole.Admin, UserRole.HOD, UserRole.Office, UserRole.CellMember)),
):
    # Application
    result = await session.execute(select(Application).where(Application.id == app_id))
    app = result.scalar_one_or_none()

    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # Stages
    stages_result = await session.execute(
        select(ApplicationStage)
        .where(ApplicationStage.application_id == app.id)
        .order_by(ApplicationStage.sequence_order.asc())
    )

    return {
        "application": app,
        "stages": stages_result.scalars().all()
    }


# GET ALL APPLICATIONS (ENRICHED VIEW)
@router.get("/all/enriched")
async def list_all_applications_enriched(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(AllowRoles(
        UserRole.Admin,
        UserRole.HOD,
        UserRole.Office,
        UserRole.CellMember
    )),
):
    query = """
        SELECT
            a.id AS application_id,
            a.status AS application_status,
            a.created_at AS created_at,
            a.updated_at AS updated_at,
            a.current_department_id,

            -- Student fields
            s.full_name AS student_name,
            s.roll_number AS roll_number,
            s.enrollment_number AS enrollment_number,
            s.mobile_number AS student_mobile,
            s.email AS student_email,

            -- Department fields
            d.name AS department_name

        FROM applications a
        LEFT JOIN students s ON s.id = a.student_id
        LEFT JOIN departments d ON d.id = a.current_department_id
        ORDER BY a.created_at DESC
    """

    result = await session.execute(text(query))
    rows = result.mappings().all()

    return rows


# APPROVE A STAGE
@router.post("/{stage_id}/approve", response_model=StageActionResponse)
async def approve_stage_endpoint(
    stage_id: str,
    current_user: User = Depends(AllowRoles(UserRole.Admin, UserRole.HOD, UserRole.Office, UserRole.CellMember)),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        stage = await approve_stage(session, stage_id, str(current_user.id))
        await session.commit()
        await session.refresh(stage)
        return stage
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# REJECT A STAGE
@router.post("/{stage_id}/reject", response_model=StageActionResponse)
async def reject_stage_endpoint(
    stage_id: str,
    data: StageActionRequest,
    current_user: User = Depends(AllowRoles(UserRole.Admin, UserRole.HOD, UserRole.Office, UserRole.CellMember)),
    session: AsyncSession = Depends(get_db_session),
):
    if not data.remarks:
        raise HTTPException(status_code=400, detail="Remarks required for rejection")

    try:
        stage = await reject_stage(session, stage_id, str(current_user.id), data.remarks)
        await session.commit()
        await session.refresh(stage)
        return stage
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
