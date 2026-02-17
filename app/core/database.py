import os
import ssl
from typing import AsyncGenerator

from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import SQLModel

# -------------------------------------------------------------------------
# 1. ENVIRONMENT CONFIGURATION
# -------------------------------------------------------------------------
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
ENV = os.getenv("ENV", "development").lower()  # default to development if not set

if not DATABASE_URL:
    raise RuntimeError("❌ DATABASE_URL is not set")


# -------------------------------------------------------------------------
# 2. SSL CONTEXT
# -------------------------------------------------------------------------
def make_ssl_context():
    """
    Creates a standard SSL context for cloud database connections.
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# -------------------------------------------------------------------------
# 3. CONNECTION ARGUMENTS (Dynamic Based on ENV)
# -------------------------------------------------------------------------
if ENV == "production":
    logger.info("🔐 Production Mode: SSL Enabled")
    connect_args = {
        "ssl": make_ssl_context(),
        "server_settings": {
            "jit": "off",
            "timezone": "UTC",
            "application_name": "gbu_no_dues_prod"
        }
    }
else:
    logger.info("🛠 Development Mode: SSL Disabled")
    connect_args = {
        "server_settings": {
            "jit": "off",
            "timezone": "UTC",
            "application_name": "gbu_no_dues_local"
        }
    }


# -------------------------------------------------------------------------
# 4. ENGINE CONFIGURATION
# -------------------------------------------------------------------------
engine = create_async_engine(
    DATABASE_URL,
    echo=False,                # Disable SQL logging in production for performance
    future=True,
    connect_args=connect_args,
    
    # Connection Pool Settings (Optimized for Supabase Session Mode)
    pool_size=10,              # Keep 10 stable connections
    max_overflow=10,           # Allow bursts up to 20 temporarily
    pool_recycle=1800,         # Recycle every 30 mins
    pool_pre_ping=True,        # Health check before use (Heartbeat)
    pool_timeout=30,           # Wait up to 30s for a slot
    pool_use_lifo=True         # Reuse hot connections for better performance
)


# -------------------------------------------------------------------------
# 5. SESSION FACTORY
# -------------------------------------------------------------------------
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


# -------------------------------------------------------------------------
# 6. DEPENDENCY INJECTION
# -------------------------------------------------------------------------
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI Dependency to yield a database session.
    Automatically handles commit/rollback logic via context manager.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"⚠️ Database Transaction Rollback: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


# -------------------------------------------------------------------------
# 7. LIFECYCLE HELPERS (Startup/Shutdown)
# -------------------------------------------------------------------------
async def init_db():
    """Initializes database tables. Should be run once on startup."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        logger.info("✅ Database Schema Synced (Session Mode)")
    except Exception as e:
        logger.critical(f"❌ DB Init Failed: {e}")
        raise


async def test_connection():
    """Simple health check to verify latency and connectivity."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            logger.info("🚀 Database Connected (Session Mode)")
    except Exception as e:
        logger.critical(f"❌ Connection Failed: {e}")
        raise e
