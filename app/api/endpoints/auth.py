from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
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
from app.core.config import settings
from app.core.rate_limiter import limiter
from app.core.security import get_password_hash 

# Schemas
from app.schemas.auth import (
    LoginRequest, 
    RegisterRequest, 
    TokenWithUser,
    SchoolCreateRequest,
    DepartmentCreateRequest
)
from app.schemas.user import UserRead, UserUpdate, UserListResponse
from app.schemas.student import StudentRead
from app.schemas.audit import AuditLogRead
# ✅ NEW: Import Academic Schemas
from app.schemas.academic import (
    ProgrammeCreate, ProgrammeRead,
    SpecializationCreate, SpecializationRead
)

from app.core.storage import get_signed_url

# Models
from app.models.user import UserRole, User
from app.models.school import School          
from app.models.department import Department  
# ✅ NEW: Import Academic Models
from app.models.academic import Programme, Specialization
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
from app.services.turnstile import verify_turnstile

from app.api.deps import get_db_session, get_current_user, require_admin

router = APIRouter(prefix="/api/admin", tags=["Auth (Admin)"])


# ----------------------------------------------------------------
# LOGIN (Protected with Rate Limit + Turnstile)
# ----------------------------------------------------------------
@router.post("/login", response_model=TokenWithUser)
@limiter.limit("10/minute") 
async def login(
    request: Request, 
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db_session)
):
    # 1. Verify Turnstile Token
    client_ip = request.client.host if request.client else None
    
    # Check if token exists
    if not payload.turnstile_token:
        raise HTTPException(
            status_code=400, 
            detail="Security check missing."
        )

    # Validate with Cloudflare
    is_human = await verify_turnstile(payload.turnstile_token, ip=client_ip)
    
    if not is_human:
        raise HTTPException(
            status_code=400, 
            detail="Security check failed. Please refresh the page and try again."
        )

    # 2. Authenticate User
    user = await authenticate_user(session, payload.email, payload.password)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return await create_login_response(user, session)


# ===================================================================
# REGISTER USER (Robust Code-First Version)
# ===================================================================
@router.post("/register-user", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(
    data: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), 
):
    """
    Creates a new user (Admin, Dean, HOD, Staff).
    Prioritizes 'school_code' or 'department_code' for ID resolution.
    """
    # 1. Check Email Duplication
    existing = await get_user_by_email(session, data.email)
    if existing:
        raise HTTPException(400, detail="Email already exists")

    if data.role == UserRole.Admin:
         # Admins don't need school/dept links generally
         pass 

    # 2. RESOLVE CODES TO IDs
    final_school_id = data.school_id 
    final_dept_id = data.department_id 

    # Resolve School Code (e.g., 'SOICT', 'SOE')
    if data.school_code:
        clean_code = data.school_code.strip().upper()
        res = await session.execute(select(School).where(School.code == clean_code))
        school = res.scalar_one_or_none()
        if not school:
            raise HTTPException(400, f"Invalid School Code: {clean_code}")
        final_school_id = school.id

    # Resolve Department Code (e.g., 'CSE', 'LIB', 'ACC')
    if data.department_code:
        clean_code = data.department_code.strip().upper()
        res = await session.execute(select(Department).where(Department.code == clean_code))
        dept = res.scalar_one_or_none()
        if not dept:
            raise HTTPException(400, f"Invalid Department Code: {clean_code}")
        final_dept_id = dept.id

    # 3. VALIDATE ROLE RULES (Enforce Hierarchy)
    if data.role == UserRole.Dean:
        if not final_school_id:
            raise HTTPException(400, "Dean requires a valid 'school_code'.")
        final_dept_id = None  # Deans shouldn't be linked to specific academic depts

    elif data.role == UserRole.HOD:
        if not final_dept_id:
            raise HTTPException(400, "HOD requires a valid 'department_code'.")

    elif data.role == UserRole.Staff:
        if not final_school_id and not final_dept_id:
            raise HTTPException(400, "Staff must have either 'school_code' (for Office) or 'department_code' (for Admin Depts).")
        
        if final_school_id and final_dept_id:
             raise HTTPException(400, "Staff cannot operate at both School and Department levels simultaneously. Create separate accounts if needed.")

    # 4. CALL SERVICE
    new_user = await create_user(
        session=session,
        name=data.name,
        email=data.email,
        password=data.password,
        role=data.role,
        department_id=final_dept_id,
        school_id=final_school_id
    )
    
    return new_user


# ===================================================================
# SCHOOL MANAGEMENT
# ===================================================================
@router.post("/schools", status_code=status.HTTP_201_CREATED)
async def create_school(
    payload: SchoolCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), 
):
    res = await session.execute(
        select(School).where(or_(School.name == payload.name, School.code == payload.code))
    )
    if res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="School with this name or code already exists")

    new_school = School(
        name=payload.name, 
        code=payload.code.upper(),
        requires_lab_clearance=payload.requires_lab_clearance
    )
    session.add(new_school)
    await session.commit()
    await session.refresh(new_school)
    return new_school

@router.get("/schools", response_model=List[School])
async def list_schools(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), 
):
    result = await session.execute(select(School).order_by(School.name))
    return result.scalars().all()

@router.delete("/schools/{identifier}", status_code=204)
async def delete_school(
    identifier: str, 
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), 
):
    if identifier.isdigit():
        stmt = select(School).where(School.id == int(identifier))
    else:
        stmt = select(School).where(School.code == identifier.upper())
        
    result = await session.execute(stmt)
    school = result.scalar_one_or_none()

    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    dept_check = await session.execute(
        select(Department).where(Department.school_id == school.id).limit(1)
    )
    if dept_check.scalar():
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete {school.code}. You must first reassign or delete the departments belonging to this school."
        )

    try:
        await session.delete(school)
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=400, 
            detail="Deletion blocked: This school has active students or staff linked to it."
        )
    return None


# ===================================================================
# DEPARTMENT MANAGEMENT
# ===================================================================
@router.post("/departments", status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), 
):
    res = await session.execute(
        select(Department).where(or_(Department.name == payload.name, Department.code == payload.code))
    )
    if res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Department with this name or code already exists")

    final_school_id = None
    if payload.school_code:
        stmt = select(School).where(School.code == payload.school_code.strip().upper())
        school_res = await session.execute(stmt)
        school = school_res.scalar_one_or_none()
        if not school:
            raise HTTPException(status_code=400, detail=f"Invalid School Code: {payload.school_code}")
        final_school_id = school.id

    if payload.phase_number == 1 and not final_school_id:
        raise HTTPException(
            status_code=400, 
            detail="Academic Departments (Phase 1) must be linked to a School. Please select a School."
        )

    new_dept = Department(
        name=payload.name, 
        code=payload.code.upper(), 
        phase_number=payload.phase_number,
        school_id=final_school_id
    )
    session.add(new_dept)
    await session.commit()
    await session.refresh(new_dept)
    return new_dept


@router.get("/departments", response_model=List[Department])
async def list_departments(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), 
):
    result = await session.execute(
        select(Department)
        .options(selectinload(Department.school)) 
        .order_by(Department.phase_number, Department.name)
    )
    return result.scalars().all()


@router.delete("/departments/{identifier}", status_code=204)
async def delete_department(
    identifier: str,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), 
):
    if identifier.isdigit():
        stmt = select(Department).where(Department.id == int(identifier))
    else:
        stmt = select(Department).where(Department.code == identifier.upper())
        
    result = await session.execute(stmt)
    dept = result.scalar_one_or_none()

    if not dept:
        raise HTTPException(404, detail="Department not found")
        
    try:
        await session.delete(dept)
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(400, detail="Cannot delete department. It has linked student or staff records.")
    return None


# ===================================================================
# ✅ PROGRAMME MANAGEMENT (NEW)
# ===================================================================
@router.post("/programmes", response_model=ProgrammeRead, status_code=status.HTTP_201_CREATED)
async def create_programme(
    payload: ProgrammeCreate,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
):
    # 1. Resolve Department
    stmt = select(Department).where(Department.code == payload.department_code.upper().strip())
    res = await session.execute(stmt)
    department = res.scalar_one_or_none()
    
    if not department:
        raise HTTPException(400, f"Invalid Department Code: {payload.department_code}")
        
    # 2. Check Duplicates (Code must be unique globally)
    existing = await session.execute(select(Programme).where(Programme.code == payload.code.upper().strip()))
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"Programme Code '{payload.code}' already exists.")

    # 3. Create
    prog = Programme(
        name=payload.name,
        code=payload.code.upper().strip(),
        department_id=department.id
    )
    session.add(prog)
    await session.commit()
    await session.refresh(prog)
    return prog

@router.get("/programmes", response_model=List[ProgrammeRead])
async def list_programmes(
    department_code: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
):
    query = select(Programme).order_by(Programme.name)
    
    if department_code:
        query = query.join(Department).where(Department.code == department_code.upper().strip())
        
    res = await session.execute(query)
    return res.scalars().all()

@router.delete("/programmes/{identifier}", status_code=204)
async def delete_programme(
    identifier: str, # ID or Code
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
):
    if identifier.isdigit():
        stmt = select(Programme).where(Programme.id == int(identifier))
    else:
        stmt = select(Programme).where(Programme.code == identifier.upper().strip())
        
    res = await session.execute(stmt)
    prog = res.scalar_one_or_none()
    
    if not prog:
        raise HTTPException(404, "Programme not found")
        
    # Safety Check: Are students linked?
    student_check = await session.execute(select(Student).where(Student.programme_id == prog.id).limit(1))
    if student_check.scalar():
         raise HTTPException(400, "Cannot delete Programme: Students are enrolled in it.")
         
    try:
        await session.delete(prog)
        await session.commit()
    except Exception:
        await session.rollback()
        raise HTTPException(400, "Deletion failed. Ensure no Specializations are linked.")
    return None


# ===================================================================
# ✅ SPECIALIZATION MANAGEMENT (NEW)
# ===================================================================
@router.post("/specializations", response_model=SpecializationRead, status_code=status.HTTP_201_CREATED)
async def create_specialization(
    payload: SpecializationCreate,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
):
    # 1. Resolve Programme
    stmt = select(Programme).where(Programme.code == payload.programme_code.upper().strip())
    res = await session.execute(stmt)
    programme = res.scalar_one_or_none()
    
    if not programme:
        raise HTTPException(400, f"Invalid Programme Code: {payload.programme_code}")
        
    # 2. Check Duplicates
    existing = await session.execute(select(Specialization).where(Specialization.code == payload.code.upper().strip()))
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"Specialization Code '{payload.code}' already exists.")

    # 3. Create
    spec = Specialization(
        name=payload.name,
        code=payload.code.upper().strip(),
        programme_id=programme.id
    )
    session.add(spec)
    await session.commit()
    await session.refresh(spec)
    return spec

@router.get("/specializations", response_model=List[SpecializationRead])
async def list_specializations(
    programme_code: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
):
    query = select(Specialization).order_by(Specialization.name)
    
    if programme_code:
        query = query.join(Programme).where(Programme.code == programme_code.upper().strip())
        
    res = await session.execute(query)
    return res.scalars().all()

@router.delete("/specializations/{identifier}", status_code=204)
async def delete_specialization(
    identifier: str, # ID or Code
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
):
    if identifier.isdigit():
        stmt = select(Specialization).where(Specialization.id == int(identifier))
    else:
        stmt = select(Specialization).where(Specialization.code == identifier.upper().strip())
        
    res = await session.execute(stmt)
    spec = res.scalar_one_or_none()
    
    if not spec:
        raise HTTPException(404, "Specialization not found")
        
    # Safety Check: Are students linked?
    student_check = await session.execute(select(Student).where(Student.specialization_id == spec.id).limit(1))
    if student_check.scalar():
         raise HTTPException(400, "Cannot delete Specialization: Students are enrolled in it.")
         
    try:
        await session.delete(spec)
        await session.commit()
    except Exception:
        await session.rollback()
        raise HTTPException(500, "Internal Server Error during deletion.")
    return None


# -------------------------------------------------------------------
# USER MANAGEMENT (List / Update / Delete)
# -------------------------------------------------------------------
@router.get("/users", response_model=UserListResponse)
async def get_all_users(
    role: Optional[UserRole] = Query(None, description="Filter by role"),
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), 
):
    query = select(User)
    query = query.options(
        selectinload(User.department),
        selectinload(User.school),
        selectinload(User.student).selectinload(Student.school)
    )

    if role:
        query = query.where(User.role == role)
    
    query = query.order_by(User.created_at.desc())
    
    result = await session.execute(query)
    users = result.scalars().all() 

    return {
        "total": len(users),
        "users": users
    }

@router.delete("/users/{user_id}", status_code=204)
async def remove_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), 
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
    _: User = Depends(require_admin), 
):
    if data.role == UserRole.Dean and not data.school_id and not data.school_code:
        raise HTTPException(400, detail="school_id/code is required for Dean users")
    
    if data.role == UserRole.HOD and not data.department_id and not data.department_code:
        raise HTTPException(400, detail="department_id/code is required for HOD users")

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
    _: User = Depends(require_admin), 
):
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
    
    # ✅ Update to load Programme/Specialization
    query = query.options(
        selectinload(Student.school),
        selectinload(Student.programme),
        selectinload(Student.specialization)
    )

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
    _: User = Depends(require_admin), 
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
    _: User = Depends(require_admin), 
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
# GLOBAL SEARCH
# ===================================================================
@router.get("/search", response_model=Dict[str, Any])
@limiter.limit("60/minute") 
async def admin_global_search(
    request: Request, 
    q: str = Query(..., min_length=3),
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), 
):
    term = f"%{q.lower()}%"
    
    # 1. Search Students
    student_query = (
        select(Student)
        .options(selectinload(Student.school)) 
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
    
    clean_q = q.strip().upper().replace(" ", "").replace("-", "")

    try:
        # A. Try searching by UUID
        uuid_obj = UUID(q)
        app_query = (
            select(Application)
            .options(selectinload(Application.student)) 
            .where(Application.id == uuid_obj)
        )
        app_res = await session.execute(app_query)
        app_results = app_res.scalars().all()
        
    except ValueError:
        # B. Not a UUID? Search by Display ID AND Student relations
        
        display_id_query = (
            select(Application)
            .options(selectinload(Application.student)) 
            .where(Application.display_id.ilike(f"%{clean_q}%"))
        )
        display_res = await session.execute(display_id_query)
        app_results = display_res.scalars().all()
        
        # Include applications owned by found students
        if students:
            student_ids = [s.id for s in students]
            student_app_query = (
                select(Application)
                .options(selectinload(Application.student)) 
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
# ANALYTICS
# ===================================================================
@router.get("/analytics/performance")
async def get_department_performance(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), 
):
    """
    Returns performance stats grouped by Department.
    """
    query = """
        WITH clean_data AS (
            SELECT 
                CASE 
                    WHEN LOWER(COALESCE(d.name, s.verifier_role)) IN ('lab', 'labs', 'laboratories', 'laboratory') THEN 'Laboratories'
                    WHEN LOWER(COALESCE(d.name, s.verifier_role)) IN ('account', 'accounts') THEN 'Accounts'
                    WHEN LOWER(COALESCE(d.name, s.verifier_role)) = 'crc' THEN 'CRC'
                    WHEN LOWER(COALESCE(d.name, s.verifier_role)) = 'dean' THEN 'School Dean'
                    WHEN LOWER(COALESCE(d.name, s.verifier_role)) = 'hod' THEN 'Head of Department'
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
            COALESCE(AVG(CASE 
                WHEN status IN ('approved', 'rejected') 
                THEN EXTRACT(EPOCH FROM (updated_at - created_at))/3600 
                ELSE NULL 
            END), 0)::numeric(10,2) as avg_hours,
            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_count,
            COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected_count,
            COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved_count,
            COUNT(CASE WHEN status IN ('approved', 'rejected') THEN 1 END) as total_processed
        FROM clean_data
        GROUP BY dept_name
        ORDER BY pending_count DESC, total_processed DESC
    """
    
    result = await session.execute(text(query))
    rows = result.mappings().all()
    return [dict(row) for row in rows]


# ===================================================================
# EXPORT REPORTS (Updated: Includes Dept Code)
# ===================================================================
@router.get("/reports/export-cleared")
async def export_cleared_students(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin), 
):
    # 1. Update Query to join Department
    query = (
        select(Application, Student, School, Certificate, Department)
        .join(Student, Application.student_id == Student.id)
        .join(School, Student.school_id == School.id)
        .outerjoin(Department, Student.department_id == Department.id)
        .outerjoin(Certificate, Certificate.application_id == Application.id)
        .where(Application.status == "completed")
        .order_by(School.name, Student.roll_number)
    )
    result = await session.execute(query)
    rows = result.all()

    output = io.StringIO()
    writer = csv.writer(output)
    
    # 2. Update Headers (Added 'Dept Code')
    writer.writerow([
        "Certificate Number", "Roll Number", "Enrollment No", "Student Name", 
        "Father's Name", "Gender", "Category", 
        "School Code", "School Name",          # Split School info
        "Dept Code", "Department Name",        # ADDED Dept Code
        "Admission Year", "Mobile", "Email", "Clearance Date", 
        "Application Ref (ID)", "System UUID" 
    ])

    # 3. Write Rows
    for app, student, school, cert, department in rows:
        cert_num = cert.certificate_number if cert else "PENDING"
        
        # Safe Access for Department
        dept_name = department.name if department else "N/A"
        dept_code = department.code if department else "N/A" # Fetch Code

        # Safe Access for School Code (assuming School model has a 'code' column)
        school_code = getattr(school, "code", "N/A") 

        writer.writerow([
            cert_num,
            student.roll_number,
            student.enrollment_number,
            student.full_name,
            student.father_name,
            student.gender,
            student.category,
            school_code,    # School Code
            school.name,    # School Name
            dept_code,      # Dept Code (e.g., "CSE")
            dept_name,      # Dept Name (e.g., "Computer Science...")
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