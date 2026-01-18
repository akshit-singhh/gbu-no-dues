# app/core/database.py

import os
import ssl
from dotenv import load_dotenv
from typing import AsyncGenerator

from loguru import logger
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy import text

# ----------------------------------------------------
# Load environment
# ----------------------------------------------------
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("❌ DATABASE_URL is not set")


# ----------------------------------------------------
# SSL Context (Relaxed for Cloud Poolers)
# ----------------------------------------------------
def make_ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# ----------------------------------------------------
# AsyncPG Driver Configuration (Supabase Specific)
# ----------------------------------------------------
connect_args = {
    "ssl": make_ssl_context(),
    
    # ⚠️ CRITICAL: Disable prepared statements. 
    # Supabase Transaction Mode (port 6543/5432 pooler) does NOT support them.
    "statement_cache_size": 0,
    
    # ⚠️ CRITICAL: Increase connection handshake timeout.
    # Default is often too short for waking up dormant cloud DBs.
    "timeout": 30,          
    
    # ⚠️ CRITICAL: Increase query execution timeout.
    "command_timeout": 60,  
}

logger.info("🔄 Configuring Database Engine (Supabase Pooler Mode)")


# ----------------------------------------------------
# Engine Configuration
# ----------------------------------------------------
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set True only for local debugging
    future=True,
    connect_args=connect_args,
    
    # 1. HEALTH CHECKS ("The Heartbeat")
    # Before handing a connection to the app, run "SELECT 1".
    # If it fails, drop the connection and get a fresh one. Fixes "Closed Connection" errors.
    pool_pre_ping=True,

    # 2. STALE CONNECTION RECYCLING
    # Cloud load balancers kill idle connections silently after ~5 mins.
    # We recycle them locally every 4 mins (240s) to stay ahead of the kill.
    pool_recycle=240,

    # 3. POOL SIZE (Concurrency)
    # Keep 20 connections open. Allow bursting up to 30 temporarily.
    pool_size=20,
    max_overflow=10,
    
    # 4. POOL TIMEOUT
    # If all 30 connections are busy, wait 30s before throwing an error.
    pool_timeout=30
)


# ----------------------------------------------------
# Session Factory
# ----------------------------------------------------
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


# ----------------------------------------------------
# Dependency Injection (Used in API Routers)
# ----------------------------------------------------
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI Dependency that yields a database session.
    Ensures session is closed even if an error occurs.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"⚠️ Database Session Rollback: {str(e)}")
            await session.rollback()
            raise
        finally:
            await session.close()


# ----------------------------------------------------
# Initialization & Health Checks
# ----------------------------------------------------
async def init_db():
    """Creates tables if they don't exist (Dev Mode Only)."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        logger.info("✅ Database Tables Verified")
    except Exception as e:
        logger.error(f"❌ DB Init Failed: {e}")

async def test_connection():
    """Simple ping to verify connectivity on startup."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            logger.info("✅ Database Connection Established")
    except Exception as e:
        logger.critical(f"❌ Database Connection Failed: {e}")
        # We re-raise here so the app crashes early if DB is unreachable
        raise e