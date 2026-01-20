# app/api/endpoints/auth.py

from fastapi import APIRouter, Depends, HTTPException, status, Query, Cookie, Response, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, text
from sqlmodel import select, or_
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import selectinload
import time 
import csv 
import io
import hashlib
from app.core.config import settings
# Rate Limiting
from app.core.rate_limiter import limiter
from app.schemas.user import UserRead, UserUpdate, UserListResponse

# Schemas
from app.schemas.auth import (
    LoginRequest, 
    RegisterRequest, 
    TokenWithUser,
    SchoolCreateRequest,
    DepartmentCreateRequest
)
from app.schemas.user import UserRead, UserUpdate
from app.schemas.student import StudentRead
from app.schemas.audit import AuditLogRead

from app.core.storage import get_signed_url
# Models
from app.models.user import UserRole, User
from app.models.school import School
from app.models.department import Department
from app.models.audit import AuditLog
from app.models.application import Application 
from app.models.application_stage import ApplicationStage 
from app.models.student import Student
from app.models.certificate import Certificate

# Services
from app.services.auth_service import (
    authenticate_user,
    create_login_response,
    create_user,
    get_user_by_email,
    list_users,
    delete_user_by_id,
    update_user
)
from app.services.student_service import list_students

# Deps
# ✅ UPDATED: Imported require_admin instead of require_super_admin
from app.api.deps import get_db_session, get_current_user, require_admin

router = APIRouter(prefix="/api/admin", tags=["Auth (Admin)"])


# ----------------------------------------------------------------
# HELPER: Verify Captcha
# ----------------------------------------------------------------
def verify_captcha_hash(user_input: str, cookie_hash: str) -> bool:
    if not user_input or not cookie_hash:
        return False
    
    # Normalize input and recreate the hash using the App Secret
    normalized = user_input.strip().upper()
    raw_str = f"{normalized}{settings.SECRET_KEY}"
    calculated_hash = hashlib.sha256(raw_str.encode()).hexdigest()
    
    return calculated_hash == cookie_hash


# ----------------------------------------------------------------
# LOGIN (Protected with Rate Limit)
# ----------------------------------------------------------------
@router.post("/login", response_model=TokenWithUser)
@limiter.limit("10/minute")  # <--- RATE LIMIT: 10 attempts per minute per IP
async def login(
    request: Request,  # <--- Required for limiter
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db_session)
):
    # 1. Verify CAPTCHA (Check BODY)
    if not payload.captcha_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="CAPTCHA hash missing."
        )
    
    if not verify_captcha_hash(payload.captcha_input, payload.captcha_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid CAPTCHA code."
        )

    # 2. Authenticate
    user = await authenticate_user(session, payload.email, payload.password)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return await create_login_response(user, session)


# ===================================================================
# 1. SCHOOL MANAGEMENT
# ===================================================================

@router.post("/schools", status_code=status.HTTP_201_CREATED)
async def create_school(
    payload: SchoolCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), # ✅ Admin only
):
    res = await session.execute(
        select(School).where(
            or_(School.name == payload.name, School.code == payload.code)
        )
    )
    if res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="School with this name or code already exists")

    new_school = School(name=payload.name, code=payload.code)
    session.add(new_school)
    await session.commit()
    await session.refresh(new_school)
    return new_school

@router.get("/schools", response_model=List[School])
async def list_schools(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), # ✅ Admin only
):
    result = await session.execute(select(School).order_by(School.name))
    return result.scalars().all()

@router.delete("/schools/{school_id}", status_code=204)
async def delete_school(
    school_id: int,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), # ✅ Admin only
):
    school = await session.get(School, school_id)
    if not school:
        raise HTTPException(404, detail="School not found")
    try:
        await session.delete(school)
        await session.commit()
    except Exception:
        await session.rollback()
        raise HTTPException(400, detail="Cannot delete school. It has linked records.")
    return None


# ===================================================================
# 2. DEPARTMENT MANAGEMENT
# ===================================================================

@router.post("/departments", status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), # ✅ Admin only
):
    res = await session.execute(select(Department).where(Department.name == payload.name))
    if res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Department with this name already exists")

    new_dept = Department(name=payload.name, phase_number=payload.phase_number)
    session.add(new_dept)
    await session.commit()
    await session.refresh(new_dept)
    return new_dept

@router.get("/departments", response_model=List[Department])
async def list_departments(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), # ✅ Admin only
):
    result = await session.execute(select(Department).order_by(Department.phase_number, Department.name))
    return result.scalars().all()

@router.delete("/departments/{dept_id}", status_code=204)
async def delete_department(
    dept_id: int,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), # ✅ Admin only
):
    dept = await session.get(Department, dept_id)
    if not dept:
        raise HTTPException(404, detail="Department not found")
    try:
        await session.delete(dept)
        await session.commit()
    except Exception:
        await session.rollback()
        raise HTTPException(400, detail="Cannot delete department. It has linked records.")
    return None


# -------------------------------------------------------------------
# REGISTER SUPER ADMIN (Renamed for Clarity, kept logic)
# -------------------------------------------------------------------
@router.post("/register-super-admin", response_model=UserRead)
async def register_admin_account(
    data: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), # ✅ Admin only
):
    if data.role != UserRole.Admin:
        raise HTTPException(400, detail="This endpoint only creates Admin accounts.")

    existing = await get_user_by_email(session, data.email)
    if existing:
        raise HTTPException(400, detail="Email already exists")

    user = await create_user(
        session=session,
        name=data.name,
        email=data.email,
        password=data.password,
        role=UserRole.Admin,
        department_id=None,
        school_id=None
    )
    return user


# -------------------------------------------------------------------
# REGISTER NORMAL USER (Dean / Staff)
# -------------------------------------------------------------------
@router.post("/register-user", response_model=UserRead)
async def register_user(
    data: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), # ✅ Admin only
):
    if data.role == UserRole.Admin:
        raise HTTPException(400, detail="Use /register-super-admin for Admin accounts.")

    existing = await get_user_by_email(session, data.email)
    if existing:
        raise HTTPException(400, detail="Email already exists")

    if data.role == UserRole.Staff:
        if not data.department_id:
            raise HTTPException(400, detail="department_id is required for Staff users")
        if data.school_id:
            raise HTTPException(400, detail="Staff cannot be assigned to a School (use Dean for that)")

    elif data.role == UserRole.Dean:
        if not data.school_id:
            raise HTTPException(400, detail="school_id is required for Dean users.")
        if data.department_id:
            raise HTTPException(400, detail="Deans cannot be assigned to a Department (use Staff for that)")

    user = await create_user(
        session=session,
        name=data.name,
        email=data.email,
        password=data.password,
        role=data.role,
        department_id=data.department_id,
        school_id=data.school_id 
    )
    return user

# -------------------------------------------------------------------
# USER MANAGEMENT
# -------------------------------------------------------------------
@router.get("/users", response_model=UserListResponse)
async def get_all_users(
    role: Optional[UserRole] = Query(None, description="Filter by role"),
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), # ✅ Admin only
):
    # Construct query with specific load options to ensure Pydantic has data
    query = select(User)
    
    # Eager load relationships to prevent MissingGreenlet errors
    query = query.options(
        selectinload(User.department),
        selectinload(User.school),
        selectinload(User.student).selectinload(Student.school)
    )

    if role:
        query = query.where(User.role == role)
    
    query = query.order_by(User.created_at.desc())
    
    result = await session.execute(query)
    users = result.scalars().all() # Fetch the list

    # Return the new object structure
    return {
        "total": len(users),
        "users": users
    }

@router.delete("/users/{user_id}", status_code=204)
async def remove_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), # ✅ Admin only
):
    try:
        await delete_user_by_id(session, str(user_id))
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    return None

@router.put("/users/{user_id}", response_model=UserRead)
async def update_user_endpoint(
    user_id: str,
    data: UserUpdate,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), # ✅ Admin only
):
    # Validation
    if data.role == UserRole.Staff and not data.department_id:
        raise HTTPException(400, detail="department_id is required for Staff users")
    if data.role == UserRole.Dean and not data.school_id:
        raise HTTPException(400, detail="school_id is required for Dean users")

    try:
        return await update_user(
            session,
            user_id=user_id,
            name=data.name,
            email=data.email,
            role=data.role,
            department_id=data.department_id,
            school_id=data.school_id 
        )
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


# -------------------------------------------------------------------
# GET CURRENT ADMIN
# -------------------------------------------------------------------
@router.get("/me", response_model=UserRead)
async def me(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Re-fetches the user with eager loading to ensure
    school/department details are available for the schema.
    """
    query = (
        select(User)
        .options(
            selectinload(User.school),
            selectinload(User.department)
        )
        .where(User.id == current_user.id)
    )
    result = await session.execute(query)
    return result.scalar_one()


# ===================================================================
# STUDENT MANAGEMENT
# ===================================================================
@router.get("/students/{input_id}")
async def admin_get_student_by_id_or_roll(
    input_id: str,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), # ✅ Admin only
):
    """
    Get student details AND their latest application status.
    Returns a SIGNED URL for the proof document.
    """
    # 1. SMART SEARCH (Find Student)
    is_uuid = False
    try:
        UUID(input_id)
        is_uuid = True
    except ValueError:
        is_uuid = False

    if is_uuid:
        query = select(Student).where(Student.id == input_id)
    else:
        query = select(Student).where(
            or_(
                Student.roll_number == input_id,
                Student.enrollment_number == input_id
            )
        )
    
    # Eager load school for student details
    query = query.options(selectinload(Student.school))

    result = await session.execute(query)
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(404, f"Student not found with ID/Roll/Enrollment: {input_id}")

    # 2. FETCH LATEST APPLICATION
    app_query = (
        select(Application)
        .where(Application.student_id == student.id)
        .order_by(Application.created_at.desc())
    )
    app_res = await session.execute(app_query)
    latest_app = app_res.scalars().first()

    # 3. GENERATE SIGNED URL
    if latest_app and latest_app.proof_document_url:
        latest_app.proof_document_url = get_signed_url(latest_app.proof_document_url)

    # 4. RETURN RESPONSE
    return {
        "student": student,
        "application": latest_app if latest_app else None,
        "is_active": latest_app.status in ["pending", "in_progress"] if latest_app else False
    }

# -------------------------------------------------------------------
# VIEW AUDIT LOGS
# -------------------------------------------------------------------
@router.get("/audit-logs", response_model=List[AuditLogRead])
async def get_audit_logs(
    action: Optional[str] = Query(None),
    actor_role: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), # ✅ Admin only
):
    query = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
    if action:
        query = query.where(AuditLog.action == action)
    if actor_role:
        query = query.where(AuditLog.actor_role == actor_role)
    result = await session.execute(query)
    return result.scalars().all()


# ===================================================================
# ADMIN DASHBOARD STATS
# ===================================================================
@router.get("/dashboard-stats")
async def get_dashboard_stats(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), # ✅ Admin only
):
    # 1. General Application Counts
    status_query = select(Application.status, func.count(Application.id)).group_by(Application.status)
    status_res = await session.execute(status_query)
    status_counts = {row[0]: row[1] for row in status_res.all()}
    total_apps = sum(status_counts.values())
    
    # 2. Bottlenecks
    bottleneck_query = (
        select(Department.name, func.count(ApplicationStage.id))
        .join(ApplicationStage, ApplicationStage.department_id == Department.id)
        .where(ApplicationStage.status == "pending")
        .group_by(Department.name)
        .order_by(func.count(ApplicationStage.id).desc())
        .limit(5)
    )
    bottleneck_res = await session.execute(bottleneck_query)
    bottlenecks = [{"department": row[0], "pending_count": row[1]} for row in bottleneck_res.all()]

    # 3. Recent Activity
    logs_query = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(5)
    logs_res = await session.execute(logs_query)
    recent_logs = logs_res.scalars().all()

    return {
        "metrics": {
            "total_applications": total_apps,
            "pending": status_counts.get("pending", 0),
            "in_progress": status_counts.get("in_progress", 0),
            "completed": status_counts.get("completed", 0),
            "rejected": status_counts.get("rejected", 0)
        },
        "top_bottlenecks": bottlenecks, 
        "recent_activity": recent_logs
    }


# ===================================================================
# GLOBAL SEARCH (OPTIMIZED + RATE LIMITED)
# ===================================================================
@router.get("/search", response_model=Dict[str, Any])
@limiter.limit("60/minute")  # <--- RATE LIMIT: 60 searches per minute (1/sec)
async def admin_global_search(
    request: Request, # <--- Required for limiter
    q: str = Query(..., min_length=3),
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), # ✅ Admin only
):
    term = f"%{q.lower()}%"
    
    # 1. Search Students
    student_query = (
        select(Student)
        .options(selectinload(Student.school)) # Load school to prevent crashes
        .where(
            or_(
                func.lower(Student.full_name).like(term),
                func.lower(Student.roll_number).like(term),
                func.lower(Student.email).like(term),
                func.lower(Student.enrollment_number).like(term)
            )
        )
        .limit(10)
    )
    student_res = await session.execute(student_query)
    students = student_res.scalars().all()

    # 2. Search Applications (UUID or Display ID)
    app_results = []
    
    # Clean up input for Smart ID search
    clean_q = q.strip().upper().replace(" ", "").replace("-", "")

    try:
        # A. Try searching by UUID
        uuid_obj = UUID(q)
        app_query = (
            select(Application)
            .options(selectinload(Application.student)) # Eager load student
            .where(Application.id == uuid_obj)
        )
        app_res = await session.execute(app_query)
        app_results = app_res.scalars().all()
        
    except ValueError:
        # B. Not a UUID? Search by Display ID AND Student relations
        
        display_id_query = (
            select(Application)
            .options(selectinload(Application.student)) # Eager load student
            .where(Application.display_id.ilike(f"%{clean_q}%"))
        )
        display_res = await session.execute(display_id_query)
        app_results = display_res.scalars().all()
        
        # Include applications owned by found students
        if students:
            student_ids = [s.id for s in students]
            student_app_query = (
                select(Application)
                .options(selectinload(Application.student)) # Eager load student
                .where(Application.student_id.in_(student_ids))
                .order_by(Application.created_at.desc())
            )
            student_app_res = await session.execute(student_app_query)
            student_apps = student_app_res.scalars().all()
            
            # Merge lists avoiding duplicates
            existing_ids = {app.id for app in app_results}
            for app in student_apps:
                if app.id not in existing_ids:
                    app_results.append(app)

    return {
        "query": q,
        "students": students,
        "applications": app_results
    }


# ===================================================================
# ANALYTICS (FIXED: Normalized Names)
# ===================================================================
@router.get("/analytics/performance")
async def get_department_performance(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), # ✅ Admin only
):
    """
    Returns performance stats grouped by Department.
    Normalizes inconsistent names (e.g., 'Lab' -> 'Laboratories').
    """
    query = """
        WITH clean_data AS (
            SELECT 
                -- 1. NORMALIZE NAMES
                CASE 
                    -- Merge 'lab', 'labs' -> 'Laboratories'
                    WHEN LOWER(COALESCE(d.name, s.verifier_role)) IN ('lab', 'labs', 'laboratories', 'laboratory') 
                        THEN 'Laboratories'
                    
                    -- Merge 'account', 'accounts' -> 'Accounts'
                    WHEN LOWER(COALESCE(d.name, s.verifier_role)) IN ('account', 'accounts') 
                        THEN 'Accounts'
                    
                    -- Stylize 'crc' -> 'CRC'
                    WHEN LOWER(COALESCE(d.name, s.verifier_role)) = 'crc' 
                        THEN 'CRC'
                    
                    -- Stylize 'dean' -> 'School Dean'
                    WHEN LOWER(COALESCE(d.name, s.verifier_role)) = 'dean' 
                        THEN 'School Dean'
                        
                    -- Default: Capitalize first letter (e.g., 'hostel' -> 'Hostel')
                    ELSE INITCAP(COALESCE(d.name, s.verifier_role))
                END as dept_name,
                
                s.status,
                s.created_at,
                s.updated_at
            FROM application_stages s
            LEFT JOIN departments d ON s.department_id = d.id
        )
        SELECT 
            dept_name,
            
            -- Avg hours (only for processed items)
            COALESCE(AVG(CASE 
                WHEN status IN ('approved', 'rejected') 
                THEN EXTRACT(EPOCH FROM (updated_at - created_at))/3600 
                ELSE NULL 
            END), 0)::numeric(10,2) as avg_hours,

            -- Exact Counts
            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_count,
            COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected_count,
            COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved_count,
            
            -- Total Processed
            COUNT(CASE WHEN status IN ('approved', 'rejected') THEN 1 END) as total_processed

        FROM clean_data
        GROUP BY dept_name
        ORDER BY pending_count DESC, total_processed DESC
    """
    
    result = await session.execute(text(query))
    rows = result.mappings().all()
    return [dict(row) for row in rows]


# ===================================================================
# EXPORT REPORTS
# ===================================================================
@router.get("/reports/export-cleared")
async def export_cleared_students(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), # ✅ Admin only
):
    query = (
        select(Application, Student, School, Certificate)
        .join(Student, Application.student_id == Student.id)
        .join(School, Student.school_id == School.id)
        .outerjoin(Certificate, Certificate.application_id == Application.id)
        .where(Application.status == "completed")
        .order_by(School.name, Student.roll_number)
    )
    result = await session.execute(query)
    rows = result.all()

    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow([
        "Certificate Number", "Roll Number", "Enrollment No", "Student Name", 
        "Father's Name", "Gender", "Category", "School", "Batch", 
        "Admission Year", "Mobile", "Email", "Clearance Date", 
        "Application Ref (ID)", "System UUID" 
    ])

    for app, student, school, cert in rows:
        cert_num = cert.certificate_number if cert else "PENDING"
        writer.writerow([
            cert_num,
            student.roll_number,
            student.enrollment_number,
            student.full_name,
            student.father_name,
            student.gender,
            student.category,
            school.name,
            student.batch,
            student.admission_year,
            student.mobile_number,
            student.email,
            app.updated_at.strftime("%Y-%m-%d") if app.updated_at else "N/A",
            
            app.display_id or "N/A",
            str(app.id) 
        ])

    output.seek(0)
    
    filename = f"cleared_students_detailed_{int(time.time())}.csv"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)