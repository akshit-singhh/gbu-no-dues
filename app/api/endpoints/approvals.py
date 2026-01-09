# app/api/endpoints/approvals.py

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, text
from uuid import UUID
from typing import Optional

from app.api.deps import get_db_session
from app.core.rbac import AllowRoles
from app.models.user import User, UserRole
from app.models.application import Application, ApplicationStatus
from app.models.application_stage import ApplicationStage
from app.models.student import Student
from app.models.department import Department
from app.models.school import School
from app.schemas.approval import StageActionRequest, StageActionResponse
from app.services.approval_service import approve_stage, reject_stage
from app.services.email_service import send_application_rejected_email, send_application_approved_email
from app.services.pdf_service import generate_certificate_pdf

from app.core.storage import get_signed_url

router = APIRouter(
    prefix="/api/approvals",
    tags=["Approvals"]
)

# Define all roles that act as verifiers (excluding Admin/Student)
VERIFIER_ROLES = [
    UserRole.Dean, UserRole.Staff, UserRole.Library, 
    UserRole.Hostel, UserRole.Sports, UserRole.Lab, 
    UserRole.CRC, UserRole.Account
]

# ===================================================================
#  HELPER: Fetch Email Data
# ===================================================================
async def get_email_context(session: AsyncSession, application_id: str, stage: ApplicationStage):
    """
    Fetches the student details and the name of the School or Department 
    associated with the stage. Used for sending email notifications.
    """
    query = (
        select(Student)
        .join(Application, Application.student_id == Student.id)
        .where(Application.id == UUID(str(application_id)))
    )
    res = await session.execute(query)
    student = res.scalar_one_or_none()

    entity_name = "Authority"
    if stage.department_id:
        d_res = await session.execute(select(Department.name).where(Department.id == stage.department_id))
        entity_name = d_res.scalar_one_or_none() or "Department"
    elif stage.verifier_role:
        entity_name = stage.verifier_role.capitalize()

    return student, entity_name


# ===================================================================
# LIST ALL APPLICATIONS (Enriched with Smart Location Logic)
# ===================================================================
@router.get("/all")
async def list_all_applications(
    status: Optional[str] = Query(None, description="Filter by status (e.g., 'pending', 'approved')"), 
    current_user: User = Depends(
        AllowRoles(UserRole.Admin, UserRole.Student, *VERIFIER_ROLES)
    ),
    session: AsyncSession = Depends(get_db_session),
):
    # 1. Base Query: Join Student table to fetch details
    query = (
        select(Application, Student)
        .join(Student, Application.student_id == Student.id)
        .order_by(Application.created_at.desc())
    )

    # --- FILTERING LOGIC ---

    # 1. ADMIN
    if current_user.role == UserRole.Admin:
        if status:
            query = query.where(Application.status == status)

    # 2. STUDENT
    elif current_user.role == UserRole.Student:
        query = query.where(Application.student_id == current_user.student_id)
        if status:
            query = query.where(Application.status == status)

    # 3. DEAN
    elif current_user.role == UserRole.Dean:
        if not getattr(current_user, 'school_id', None):
            return JSONResponse(status_code=200, content={"message": "Dean has no school assigned.", "data": []})
        
        query = query.where(Student.school_id == current_user.school_id)
        
        if status:
            query = query.where(Application.status == status)

    # 4. STAFF
    elif current_user.role == UserRole.Staff:
        if not getattr(current_user, 'department_id', None):
            return JSONResponse(status_code=200, content={"message": "Staff has no department assigned.", "data": []})
        
        query = query.join(ApplicationStage).where(
            ApplicationStage.department_id == current_user.department_id,
            Application.current_stage_order >= ApplicationStage.sequence_order
        )
        
        if status:
            query = query.where(ApplicationStage.status == status)
            
        query = query.distinct()

    # 5. OTHER ROLES (Accounts, Library, Hostel, etc.)
    else:
        role_name = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
        
        query = query.join(ApplicationStage).where(
            ApplicationStage.verifier_role == role_name,
            Application.current_stage_order >= ApplicationStage.sequence_order
        )

        if status:
            query = query.where(ApplicationStage.status == status)

        query = query.distinct()

    # --- EXECUTE ---
    result = await session.execute(query)
    rows = result.all() 

    if not rows:
        return JSONResponse(status_code=200, content={"message": "No applications found.", "data": []})

    final_list = []

    for app, student in rows:
        
        # ---------------------------------------------------------
        # SMART LOCATION LOGIC (Who is currently holding it?)
        # ---------------------------------------------------------
        current_location_str = "Processing..."
        
        if app.status == "completed":
            current_location_str = "Completed (Certificate Issued)"
        
        else:
            # Fetch ALL stages at the current active level (e.g., Level 2)
            active_stages_res = await session.execute(
                select(ApplicationStage, Department.name)
                .outerjoin(Department, ApplicationStage.department_id == Department.id)
                .where(
                    (ApplicationStage.application_id == app.id) &
                    (ApplicationStage.sequence_order == app.current_stage_order)
                )
            )
            active_stages = active_stages_res.all()

            pending_names = []
            approved_names = []
            rejected_names = []

            for stage_obj, dept_name in active_stages:
                # Use Department Name if available, otherwise Role Name
                name = dept_name if dept_name else stage_obj.verifier_role.capitalize()
                
                if stage_obj.status == "approved":
                    approved_names.append(name)
                elif stage_obj.status == "rejected":
                    rejected_names.append(name)
                else:
                    pending_names.append(name)
            
            # Construct the Status Sentence
            parts = []
            if rejected_names:
                parts.append(f"Rejected by: {', '.join(rejected_names)}")
            
            if pending_names:
                parts.append(f"Pending at: {', '.join(pending_names)}")
            
            if approved_names and app.status != "rejected":
                # Only show approvals if not fully rejected, to keep string clean
                parts.append(f"Approved by: {', '.join(approved_names)}")

            if parts:
                current_location_str = " | ".join(parts)
            else:
                current_location_str = "Awaiting Initiation"

        # ---------------------------------------------------------
        # Standard Stage Data (For specific user view / active action)
        # ---------------------------------------------------------
        stage_query = (
            select(ApplicationStage, User.name)
            .outerjoin(User, ApplicationStage.verified_by == User.id)
            .where(ApplicationStage.application_id == app.id)
        )

        # Refine which stage info to show in active_stage object based on user role
        if current_user.role == UserRole.Staff:
            stage_query = stage_query.where(ApplicationStage.department_id == current_user.department_id)
        
        elif current_user.role not in [UserRole.Admin, UserRole.Dean, UserRole.Student]:
             role_name = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
             stage_query = stage_query.where(ApplicationStage.verifier_role == role_name)

        stage_query = stage_query.order_by(ApplicationStage.sequence_order.asc())
        
        stage_res = await session.execute(stage_query)
        row = stage_res.first() 

        active_stage_data = None
        if row:
            stage_obj, verifier_name = row
            active_stage_data = {
                "stage_id": stage_obj.id,
                "status": stage_obj.status,
                "remarks": stage_obj.comments, 
                "verified_by": stage_obj.verified_by,
                "verifier_name": verifier_name,
                "verified_at": stage_obj.verified_at,
                "sequence_order": stage_obj.sequence_order
            }

        final_list.append({
            "application_id": app.id,
            "student_id": app.student_id,
            "student_name": student.full_name,
            "roll_number": student.roll_number,
            "enrollment_number": student.enrollment_number,
            "student_email": student.email,
            "student_mobile": student.mobile_number,
            "status": app.status,
            "current_stage": app.current_stage_order, 
            "remarks": app.remarks,
            
            # RESULT: "Pending at: Library | Approved by: Hostel"
            "current_location": current_location_str,
            
            "created_at": app.created_at,
            "updated_at": app.updated_at,
            "active_stage": active_stage_data
        })

    return final_list


# ===================================================================
# SHORTCUT: GET PENDING ONLY
# ===================================================================
@router.get("/pending")
async def list_pending_applications(
    current_user: User = Depends(
        AllowRoles(UserRole.Admin, UserRole.Student, *VERIFIER_ROLES)
    ),
    session: AsyncSession = Depends(get_db_session),
):
    return await list_all_applications(
        status="pending",
        current_user=current_user, 
        session=session
    )


# ===================================================================
# ENRICHED LIST (Legacy / SQL Optimized)
# ===================================================================
@router.get("/all/enriched")
async def list_enriched(
    current_user: User = Depends(
        AllowRoles(UserRole.Admin, *VERIFIER_ROLES)
    ),
    session: AsyncSession = Depends(get_db_session),
):
    # This endpoint is kept for complex reporting if needed, 
    # but the main /all endpoint now provides sufficient detail.
    base_query = """
        SELECT
            a.id AS application_id,
            a.status AS application_status,
            a.current_stage_order,
            a.created_at,
            a.updated_at,

            s.full_name AS student_name,
            s.roll_number,
            s.enrollment_number,
            s.mobile_number AS student_mobile,
            s.email AS student_email,
            
            sch.name AS school_name
        FROM applications a
        JOIN students s ON s.id = a.student_id
        LEFT JOIN schools sch ON sch.id = s.school_id
    """

    params = {}

    if current_user.role == UserRole.Admin:
        query = base_query + " ORDER BY a.created_at DESC"

    elif current_user.role == UserRole.Dean:
        dean_school_id = getattr(current_user, 'school_id', None)
        if not dean_school_id:
             return JSONResponse(status_code=200, content={"message": "Dean has no school.", "data": []})
        query = base_query + " WHERE s.school_id = :school_id ORDER BY a.created_at DESC"
        params = {"school_id": dean_school_id}

    elif current_user.role == UserRole.Staff:
        staff_dept_id = getattr(current_user, 'department_id', None)
        if not staff_dept_id:
             return JSONResponse(status_code=200, content={"message": "Staff has no department.", "data": []})
        
        query = base_query + """
            JOIN application_stages stg ON stg.application_id = a.id
            WHERE stg.department_id = :dept_id
            AND a.current_stage_order >= stg.sequence_order
            ORDER BY a.created_at DESC
        """
        params = {"dept_id": staff_dept_id}

    else:
        role_name = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
        
        query = base_query + """
            JOIN application_stages stg ON stg.application_id = a.id
            WHERE stg.verifier_role = :role_name
            AND a.current_stage_order >= stg.sequence_order
            ORDER BY a.created_at DESC
        """
        params = {"role_name": role_name}

    try:
        result = await session.execute(text(query), params)
        data = result.mappings().all()
    except Exception as e:
        print(f"SQL Error in list_enriched: {e}")
        return JSONResponse(status_code=500, content={"message": "Database query error", "error": str(e)})

    if not data:
        return JSONResponse(status_code=200, content={"message": "No applications found.", "data": []})

    return data


# ===================================================================
# GET APPLICATION DETAILS (With Signed URL Logic)
# ===================================================================
@router.get("/{app_id}")
async def get_application_details(
    app_id: str,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(AllowRoles(UserRole.Admin, UserRole.Student, *VERIFIER_ROLES)),
):
    try:
        app_uuid = UUID(app_id)
    except ValueError:
        raise HTTPException(400, "Invalid Application ID format")

    # Fetch Application
    result = await session.execute(select(Application).where(Application.id == app_uuid))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(404, "Application not found")

    # 🔐 GENERATE SIGNED URL FOR VERIFIER
    # If a proof path exists, generate a temporary viewing link valid for 1 hour.
    if app.proof_document_url:
        signed_link = get_signed_url(app.proof_document_url)
        # We temporarily overwrite the attribute for this response only
        app.proof_document_url = signed_link

    # Fetch Stages AND Verifier Name
    stages_query = (
        select(ApplicationStage, User.name)
        .outerjoin(User, ApplicationStage.verified_by == User.id)
        .where(ApplicationStage.application_id == app.id)
        .order_by(ApplicationStage.sequence_order.asc())
    )
    
    stages_res = await session.execute(stages_query)
    rows = stages_res.all()

    stages_data = []
    for stage, verifier_name in rows:
        stage_dict = stage.model_dump()
        stage_dict["verifier_name"] = verifier_name
        stages_data.append(stage_dict)

    return {
        "application": app,
        "stages": stages_data,
    }


# ===================================================================
# APPROVE STAGE (Updated with Certificate Gen)
# ===================================================================
@router.post("/{stage_id}/approve", response_model=StageActionResponse)
async def approve_stage_endpoint(
    stage_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(AllowRoles(UserRole.Admin, *VERIFIER_ROLES)),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        # 1. Perform Approval Logic
        stage = await approve_stage(session, stage_id, current_user.id)
        await session.commit()
        await session.refresh(stage)

        # 2. Check Completion Status
        app_res = await session.execute(select(Application).where(Application.id == stage.application_id))
        application = app_res.scalar_one()

        # CHECK IF COMPLETED (Last Stage Approved)
        if str(application.status) == ApplicationStatus.COMPLETED.value:
            
            # 3. GENERATE CERTIFICATE AUTOMATICALLY
            try:
                await generate_certificate_pdf(session, application.id, current_user.id)
                print(f"✅ Certificate generated for Application {application.id}")
            except Exception as e:
                # Log error but don't fail the approval response
                print(f"⚠️ Certificate generation failed: {e}")

            # 4. Fetch Student for Email
            student_res = await session.execute(select(Student).where(Student.id == application.student_id))
            student = student_res.scalar_one()

            # 5. Send "Application Approved" Email
            email_data = {
                "name": student.full_name,
                "email": student.email,
                "roll_number": student.roll_number,
                "enrollment_number": student.enrollment_number,
                "application_id": str(application.id)
            }
            background_tasks.add_task(send_application_approved_email, email_data)

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
    background_tasks: BackgroundTasks,
    current_user: User = Depends(AllowRoles(UserRole.Admin, *VERIFIER_ROLES)),
    session: AsyncSession = Depends(get_db_session),
):
    if not data.remarks:
        raise HTTPException(400, "Remarks required")

    try:
        # 1. Perform Rejection
        stage = await reject_stage(session, stage_id, current_user.id, data.remarks)
        await session.commit()
        await session.refresh(stage)

        # 2. Fetch Context (Student + Rejecting Entity Name)
        student, entity_name = await get_email_context(session, str(stage.application_id), stage)
        
        if student:
            # 3. Send "Application Rejected" Email
            email_payload = {
                "name": student.full_name,
                "email": student.email,
                "department_name": entity_name or "Department",
                "remarks": data.remarks
            }
            background_tasks.add_task(send_application_rejected_email, email_payload)

        return stage

    except ValueError as e:
        raise HTTPException(400, detail=str(e))