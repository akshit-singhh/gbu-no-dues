import redis.asyncio as redis
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request, status
from app.core.storage import upload_proof_document
from app.models.user import User, UserRole
from app.core.rbac import AllowRoles
from app.core.rate_limiter import limiter
from app.core.config import settings
from app.api.deps import get_current_user
from loguru import logger

router = APIRouter(prefix="/api/utils", tags=["Utilities"])

# ----------------------------------------------------------------
# 1. UPLOAD PROOF DOCUMENT (Protected with Rate Limit)
# ----------------------------------------------------------------
@router.post("/upload-proof")
@limiter.limit("5/minute")
async def upload_proof(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(AllowRoles(UserRole.Student))
):
    """
    Step 1 of Submission: Uploads the student's clearance PDF to private storage.
    Limited to 5 uploads per minute to prevent storage abuse.
    """
    if not current_user.student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Student profile initialization required before uploading documents."
        )

    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Only PDF documents are allowed."
        )

    try:
        file_path = await upload_proof_document(file, current_user.student_id)
        return {"path": file_path}

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Critical Upload Failure: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Failed to process file upload. Please try again later."
        )


# ----------------------------------------------------------------
# 2. SYSTEM HEALTH / REDIS STATS (Admin Only)
# ----------------------------------------------------------------
@router.get("/redis-stats")
async def get_redis_statistics(
    current_user: User = Depends(get_current_user),
):
    """
    Fetch Real-Time Redis Statistics for the Admin Dashboard.
    Provides visibility into memory consumption, connection health, and active rate limits.
    """
    if current_user.role != UserRole.Admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized.")

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


# ----------------------------------------------------------------
# 3. TRAFFIC STATISTICS (Admin Only)
# ----------------------------------------------------------------
@router.get("/traffic-stats")
async def get_traffic_statistics(
    current_user: User = Depends(get_current_user),
):
    """
    Returns aggregated hit counts for API endpoints.
    Data is collected by the Traffic Middleware in main.py.
    """
    if current_user.role != UserRole.Admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized.")

    if not settings.REDIS_URL:
        return {"status": "Disabled", "data": []}

    client = None
    try:
        client = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        
        traffic_data = []
        # Keys are stored as: TRAFFIC:{METHOD}:{PATH}
        async for key in client.scan_iter(match="TRAFFIC:*", count=500):
            count = await client.get(key)
            parts = key.split(":", 2) # Split into ["TRAFFIC", "GET", "/api/users"]
            
            if len(parts) == 3:
                traffic_data.append({
                    "method": parts[1],
                    "path": parts[2],
                    "hits": int(count) if count else 0
                })
        
        # Sort by most hits first
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


# ----------------------------------------------------------------
# 4. CLEAR SYSTEM CACHE (Admin Only)
# ----------------------------------------------------------------
@router.post("/clear-cache")
async def clear_system_cache(
    scope: str = "rate_limits", 
    current_user: User = Depends(get_current_user),
):
    """
    Allows Admins to clear Redis data. 
    scope='rate_limits': Clears active throttles.
    scope='traffic': Clears traffic stats.
    scope='all': Wipes everything.
    """
    if current_user.role != UserRole.Admin:
        raise HTTPException(status_code=403, detail="Unauthorized action.")

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