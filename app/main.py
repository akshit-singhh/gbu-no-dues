# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
import sys
import time
import psutil

# Import your core modules
from app.core.database import test_connection, init_db, AsyncSessionLocal
from app.core.config import settings
from app.services.auth_service import get_user_by_email, create_user
from app.models.user import UserRole

# Routers
from app.api.endpoints import (
    auth as auth_router,
    users as users_router,
    account as account_router,
    applications as applications_router,
    students as students_router,
    auth_student as auth_student_router,
    approvals as approvals_router,
    department as department_router,
    verification as verification_router,
)

# ------------------------------------------------------------
# LOGURU CONFIGURATION
# ------------------------------------------------------------
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
           "<level>{level}</level> | "
           "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
           "<level>{message}</level>",
    colorize=True,
    backtrace=True,
    diagnose=True,
)

# ------------------------------------------------------------
# FASTAPI APP INIT
# ------------------------------------------------------------
app = FastAPI(
    title="GBU No Dues Backend",
    version="1.2.0",
    description="Backend service for the GBU No Dues Management System.",
)

# Global variables for metrics
START_TIME = time.time()
DB_STATUS = "Connecting..."  # Initial state

# ------------------------------------------------------------
# STATIC FILES & FAVICON
# ------------------------------------------------------------
# Mount the static directory
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("app/static/favicon.ico")

# ------------------------------------------------------------
# UNIFIED STATUS PAGE ENDPOINT
# ------------------------------------------------------------
@app.get("/status", include_in_schema=False)
async def status_page():
    """
    Serves the Single Page Application (SPA) dashboard.
    Ensure 'status.html' is present in 'app/static/'.
    """
    return FileResponse("app/static/status.html")


# ------------------------------------------------------------
# METRICS API (Called by the HTML Dashboard)
# ------------------------------------------------------------
@app.get("/api/metrics", tags=["System"])
async def metrics():
    # 1. System Stats
    uptime_seconds = int(time.time() - START_TIME)
    cpu_usage = psutil.cpu_percent(interval=None) 
    ram_usage = psutil.virtual_memory().percent
    try:
        disk_usage = psutil.disk_usage('/').percent
    except:
        disk_usage = 0

    # 2. Database Health & Latency Check (Real-time)
    db_start = time.time()
    db_latency = 0
    current_db_status = "Disconnected"
    
    try:
        # Ping the DB
        await test_connection()
        current_db_status = "Connected"
        # Calculate latency in ms
        db_latency = round((time.time() - db_start) * 1000, 2)
    except Exception:
        current_db_status = "Error"
        db_latency = 0

    # 3. Logs
    current_time = time.strftime("%H:%M:%S")
    logs = [
        {"time": current_time, "level": "INFO", "msg": f"Health check: DB Latency {db_latency}ms"}
    ]
    if current_db_status != "Connected":
        logs.append({"time": current_time, "level": "ERROR", "msg": "Database connection failed."})

    return {
        "status": "Online",
        "version": app.version,
        "cpu": cpu_usage,
        "ram": ram_usage,
        "disk": disk_usage,
        "uptime": uptime_seconds,
        "database": current_db_status,
        "db_latency": db_latency,
        "db_pool_active": 5,
        "db_pool_max": 20,    
        "logs": logs
    }


# ------------------------------------------------------------
# CORS CONFIGURATION
# ------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://your-frontend-domain.com",
        "*", 
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "*"],
)

# ------------------------------------------------------------
# REGISTER ROUTERS
# ------------------------------------------------------------
app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(account_router.router)
app.include_router(students_router.router)
app.include_router(auth_student_router.router)
app.include_router(applications_router.router)
app.include_router(approvals_router.router)
app.include_router(department_router.router)
app.include_router(verification_router.router)

# ------------------------------------------------------------
# APPLICATION STARTUP EVENTS
# ------------------------------------------------------------
@app.on_event("startup")
async def on_startup():
    global DB_STATUS
    logger.info("🚀 Starting GBU No Dues Backend...")

    # 1) Database connection test
    try:
        await test_connection()
        DB_STATUS = "Connected"
        logger.success("Database connection established.")
    except Exception:
        DB_STATUS = "Error"
        logger.exception("Startup aborted: Database connection failed.")

    # 2) Initialize database tables
    if DB_STATUS == "Connected":
        try:
            await init_db()
            logger.success("Database tables ready.")
        except Exception as e:
            logger.warning(f"Table initialization encountered an issue: {e}")

    # 3) Seed Super Admin (Only if DB is connected)
    if DB_STATUS == "Connected":
        try:
            async with AsyncSessionLocal() as session:
                if not settings.SUPER_ADMIN_EMAIL or not settings.SUPER_ADMIN_PASSWORD:
                    logger.warning("Missing Super Admin credentials in settings.")
                else:
                    existing = await get_user_by_email(session, settings.SUPER_ADMIN_EMAIL)
                    if not existing:
                        logger.info(f"Seeding Super Admin: {settings.SUPER_ADMIN_EMAIL}")
                        await create_user(
                            session=session,
                            name=settings.SUPER_ADMIN_NAME or "Super Admin",
                            email=settings.SUPER_ADMIN_EMAIL,
                            password=settings.SUPER_ADMIN_PASSWORD,
                            role=UserRole.Admin,
                        )
                        logger.success("Super Admin created successfully.")
                    else:
                        logger.info("Super Admin already exists. Skipping.")
        except Exception:
            logger.exception("Super Admin seeding failed.")

    logger.success("Backend startup completed successfully.\n")


# ------------------------------------------------------------
# ROOT HEALTH CHECK
# ------------------------------------------------------------
@app.get("/", tags=["System"])
async def root():
    return {
        "status": "ok",
        "service": "GBU No Dues Backend",
        "version": app.version,
        "message": "Backend running successfully 🚀",
        "dashboard_url": "/status"
    }