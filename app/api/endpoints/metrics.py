#app/

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from sqlmodel import select
import redis.asyncio as redis
import time
import socket
import os
from loguru import logger

# Config & Deps
from app.core.config import settings
from app.api.deps import get_db_session, require_admin, get_current_user

# Models
from app.models.user import User, UserRole
from app.models.application import Application
from app.models.application_stage import ApplicationStage
from app.models.department import Department
from app.models.audit import AuditLog
from app.core.database import test_connection

# Define router
router = APIRouter(
    prefix="/api/metrics",
    tags=["System & Metrics"]
)

# Track when the module is loaded for uptime calculation
START_TIME = time.time()

# ===================================================================
# 1. GENERAL SYSTEM HEALTH (Public or Admin - depending on your needs)
# ===================================================================
@router.get("/health")
async def system_health():
    uptime_seconds = int(time.time() - START_TIME)
    
    db_status = "Disconnected"
    try:
        await test_connection()
        db_status = "Connected"
    except Exception:
        db_status = "Error"

    smtp_status = "Not Configured"
    if settings.SMTP_HOST:
        try:
            sock = socket.create_connection((settings.SMTP_HOST, settings.SMTP_PORT), timeout=2)
            sock.close()
            smtp_status = "Connected"
        except Exception:
            smtp_status = "Error"

    return {
        "status": "Online",
        "uptime_seconds": uptime_seconds,
        "database": db_status,
        "smtp_server": smtp_status,
        "environment": "Serverless (Vercel)" if os.environ.get("VERCEL") else "Development"
    }


# ===================================================================
# 2. ADMIN DASHBOARD STATS (Admin Only)
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
# 3. REDIS & TRAFFIC STATS (Admin Only)
# ===================================================================
@router.get("/redis-stats")
async def get_redis_statistics(
    current_user: User = Depends(require_admin),
):
    if not settings.REDIS_URL:
        return {"status": "Disabled", "message": "Redis is not configured."}

    client = None
    try:
        client = redis.from_url(
            settings.REDIS_URL, 
            encoding="utf-8", 
            decode_responses=True,
            socket_connect_timeout=2
        )
        
        info = await client.info()
        dbsize = await client.dbsize()
        
        active_limits = []
        async for key in client.scan_iter(match="LIMITER/*", count=100):
            active_limits.append(key)
            if len(active_limits) >= 20: 
                break

        return {
            "status": "Online",
            "metrics": {
                "redis_version": info.get("redis_version"),
                "uptime_days": info.get("uptime_in_days"),
                "clients": {
                    "connected": info.get("connected_clients"),
                    "blocked": info.get("blocked_clients")
                },
                "memory": {
                    "used": info.get("used_memory_human"),
                    "peak": info.get("used_memory_peak_human"),
                    "fragmentation": info.get("mem_fragmentation_ratio")
                },
                "db": {
                    "total_keys": dbsize,
                    "active_rate_limit_windows": len(active_limits),
                    "sampled_keys": active_limits[:5]
                }
            }
        }

    except redis.ConnectionError:
        return {"status": "Offline", "detail": "Redis server unreachable."}
    except Exception as e:
        return {"status": "Error", "detail": str(e)}
    finally:
        if client:
            await client.close()


@router.get("/traffic-stats")
async def get_traffic_statistics(
    current_user: User = Depends(require_admin),
):
    if not settings.REDIS_URL:
        return {"status": "Disabled", "data": []}

    client = None
    try:
        client = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        
        traffic_data = []
        async for key in client.scan_iter(match="TRAFFIC:*", count=500):
            count = await client.get(key)
            parts = key.split(":", 2) 
            
            if len(parts) == 3:
                traffic_data.append({
                    "method": parts[1],
                    "path": parts[2],
                    "hits": int(count) if count else 0
                })
        
        traffic_data.sort(key=lambda x: x['hits'], reverse=True)
        
        return {
            "status": "Online",
            "total_endpoints_tracked": len(traffic_data),
            "data": traffic_data
        }

    except Exception as e:
        return {"status": "Error", "detail": str(e)}
    finally:
        if client:
            await client.close()


# ===================================================================
# 4. CLEAR SYSTEM CACHE (Admin Only)
# ===================================================================
@router.post("/clear-cache")
async def clear_system_cache(
    scope: str = "rate_limits", 
    current_user: User = Depends(require_admin),
):
    """
    scope='rate_limits': Clears active throttles.
    scope='traffic': Clears traffic stats.
    scope='all': Wipes everything.
    """
    if not settings.REDIS_URL:
        raise HTTPException(status_code=400, detail="Redis not configured.")

    client = None
    try:
        client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        
        match_pattern = "LIMITER/*"
        if scope == "traffic":
            match_pattern = "TRAFFIC:*"
        elif scope == "all":
            match_pattern = "*"

        if scope == "all":
            await client.flushdb()
            msg = "Global system cache cleared."
        else:
            count = 0
            async for key in client.scan_iter(match=match_pattern):
                await client.delete(key)
                count += 1
            msg = f"Cleared {count} keys for scope: {scope}"

        return {"status": "Success", "message": msg}
            
    except Exception as e:
        logger.error(f"Cache Clear Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache.")
    finally:
        if client:
            await client.close()