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
#  Removed NullPool (It causes connection churn)
from sqlalchemy import text

# ----------------------------------------------------
# Load environment
# ----------------------------------------------------
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("❌ DATABASE_URL is not set")


# ----------------------------------------------------
# SSL for Supabase Pooler
# ----------------------------------------------------
def make_ssl():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# ----------------------------------------------------
# AsyncPG SAFE Config (Supabase PgBouncer)
# ----------------------------------------------------
connect_args = {
    "ssl": make_ssl(),
    "statement_cache_size": 0,  # CRITICAL: Disable prepared statements for PgBouncer
    "command_timeout": 60,      # Give queries more time before giving up
}

logger.info("🔄 Configuring Database (Pooler Mode with Resilience)")


# ----------------------------------------------------
# Engine (ROBUST POOLING CONFIGURATION)
# ----------------------------------------------------
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args=connect_args,
    
    #  1. CONNECTION HEALTH CHECK
    # Before running a query, SQLAlchemy sends a quick "SELECT 1".
    # If the connection is dead, it discards it and gets a new one automatically.
    # This prevents "ConnectionDoesNotExistError" from crashing your endpoint.
    pool_pre_ping=True,

    #  2. AGGRESSIVE RECYCLING
    # Supabase/Cloud DBs kill idle connections after ~5 mins. 
    # We retire them locally after 5 mins (300s) so we never try to use a stale one.
    pool_recycle=300,

    #  3. PERSISTENT POOL (Fixes WinError 10054)
    # Instead of closing the TCP connection after every request (NullPool),
    # we keep 20 connections open. This stops the "handshake reset" errors.
    pool_size=20,
    max_overflow=40,  # Allow spikes up to 60 total connections
    
    #  4. TIMEOUTS
    # Wait up to 30s to get a connection from the pool before failing
    pool_timeout=30
)


# ----------------------------------------------------
# Sessions
# ----------------------------------------------------
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"⚠️ Database Session Error: {str(e)}")
            await session.rollback()
            raise
        finally:
            await session.close()


# ----------------------------------------------------
# Create tables (DEV / TEST ONLY)
# ----------------------------------------------------
async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
    except Exception as e:
        logger.error(f"❌ Failed to init DB: {e}")
        # Don't raise here, let the app start even if DB init fails (for resilience)


# ----------------------------------------------------
# Test Connection (Silent, Safe for Metrics)
# ----------------------------------------------------
async def test_connection():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            logger.debug("DB connection OK (Pooler)")
    except Exception as e:
        logger.error(f"❌ DB Health Check Failed: {e}")
        # We catch the error so the health check endpoint returns status: Error 
        # instead of crashing the whole server.
        raise e