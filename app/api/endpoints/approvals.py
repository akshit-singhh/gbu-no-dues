# app/api/endpoints/approvals.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, text

from app.api.deps import get_db_session
from app.core.rbac import AllowRoles
from app.models.user import User, UserRole
from app.models.application import Application
from app.models.application_stage import ApplicationStage
from app.schemas.approval import StageActionRequest, StageActionResponse
from app.services.approval_service import approve_stage, reject_stage
from app.models.student import Student
from app.models.department import Department


router = APIRouter(
    prefix="/api/approvals",
    tags=["Approvals"]
)


# ===================================================================
# 🆕 FIXED: LIST ALL APPLICATIONS + INCLUDE ACTIVE STAGE
# ===================================================================
@router.get("/all")
async def list_all_applications(
    current_user: User = Depends(
        AllowRoles(UserRole.Admin, UserRole.HOD, UserRole.Staff, UserRole.Student)
    ),
    session: AsyncSession = Depends(get_db_session),
):
    query = select(Application).order_by(Application.created_at.desc())

    # ADMIN → sees all
    if current_user.role == UserRole.Admin:
        pass

    # STUDENT → sees only their apps
    elif current_user.role == UserRole.Student:
        query = query.where(Application.student_id == current_user.student_id)

    # STAFF / HOD → only their department
    else:
        if not current_user.department_id:
            return []
        query = query.where(
            Application.current_department_id == current_user.department_id
        )

    result = await session.execute(query)
    apps = result.scalars().all()

    final_list = []

    # 👉 Attach active stage for each application
    for app in apps:
        stage_res = await session.execute(
            select(ApplicationStage)
            .where(
                (ApplicationStage.application_id == app.id)
                & (ApplicationStage.department_id == app.current_department_id)
            )
        )
        stage = stage_res.scalar_one_or_none()

        final_list.append({
            "application_id": app.id,
            "student_id": app.student_id,
            "office_verifier_id": app.office_verifier_id,
            "status": app.status,
            "current_department_id": app.current_department_id,
            "remarks": app.remarks,
            "created_at": app.created_at,
            "updated_at": app.updated_at,

            # 🔥 Most important part for approval UI
            "active_stage": {
                "stage_id": stage.id if stage else None,
                "department_id": stage.department_id if stage else None,
                "sequence_order": stage.sequence_order if stage else None,
                "status": stage.status if stage else None,
                "priority": stage.priority if stage else None,
                "remarks": stage.remarks if stage else None,
                "reviewer_id": stage.reviewer_id if stage else None,
                "reviewed_at": stage.reviewed_at if stage else None,
            } if stage else None
        })

    return final_list


# ===================================================================
# ENRICHED LIST (names included)
# ===================================================================
@router.get("/all/enriched")
async def list_enriched(
    current_user: User = Depends(
        AllowRoles(UserRole.Admin, UserRole.HOD, UserRole.Staff, UserRole.Student)
    ),
    session: AsyncSession = Depends(get_db_session),
):
    base_query = """
        SELECT
            a.id AS application_id,
            a.status AS application_status,
            a.created_at AS created_at,
            a.updated_at AS updated_at,
            a.current_department_id,

            s.full_name AS student_name,
            s.roll_number AS roll_number,
            s.enrollment_number AS enrollment_number,
            s.mobile_number AS student_mobile,
            s.email AS student_email,

            d.name AS department_name
        FROM applications a
        LEFT JOIN students s ON s.id = a.student_id
        LEFT JOIN departments d ON d.id = a.current_department_id
    """

    if current_user.role == UserRole.Admin:
        query = base_query + " ORDER BY a.created_at DESC"
        params = {}

    elif current_user.role == UserRole.Student:
        query = base_query + " WHERE a.student_id = :student_id ORDER BY a.created_at DESC"
        params = {"student_id": current_user.student_id}

    else:
        if not current_user.department_id:
            return []
        query = base_query + " WHERE a.current_department_id = :dept ORDER BY a.created_at DESC"
        params = {"dept": current_user.department_id}

    result = await session.execute(text(query), params)
    return result.mappings().all()


# ===================================================================
# GET APPLICATION + ALL STAGES
# ===================================================================
@router.get("/{app_id}")
async def get_application_details(
    app_id: str,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(AllowRoles(UserRole.Admin, UserRole.HOD, UserRole.Staff)),
):
    result = await session.execute(select(Application).where(Application.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(404, "Application not found")

    stages = await session.execute(
        select(ApplicationStage)
        .where(ApplicationStage.application_id == app.id)
        .order_by(ApplicationStage.sequence_order.asc())
    )

    return {
        "application": app,
        "stages": stages.scalars().all(),
    }


# ===================================================================
# APPROVE STAGE
# ===================================================================
@router.post("/{stage_id}/approve", response_model=StageActionResponse)
async def approve_stage_endpoint(
    stage_id: str,
    current_user: User = Depends(AllowRoles(UserRole.Admin, UserRole.HOD, UserRole.Staff)),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        stage = await approve_stage(session, stage_id, current_user.id)
        await session.commit()
        await session.refresh(stage)
        return stage
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


# ===================================================================
# REJECT STAGE
# ===================================================================
@router.post("/{stage_id}/reject", response_model=StageActionResponse)
async def reject_stage_endpoint(
    stage_id: str,
    data: StageActionRequest,
    current_user: User = Depends(AllowRoles(UserRole.Admin, UserRole.HOD, UserRole.Staff)),
    session: AsyncSession = Depends(get_db_session),
):
    if not data.remarks:
        raise HTTPException(400, "Remarks required")

    try:
        stage = await reject_stage(session, stage_id, current_user.id, data.remarks)
        await session.commit()
        await session.refresh(stage)
        return stage
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
