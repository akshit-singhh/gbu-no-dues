# app/api/deps.py

from typing import AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.core.database import get_session
from app.services.auth_service import get_user_by_id
from app.models.user import User, UserRole


# ------------------------------------------------------------
# HTTP Bearer Authentication
# ------------------------------------------------------------
bearer_scheme = HTTPBearer(auto_error=True)


# ------------------------------------------------------------
# DB Session
# ------------------------------------------------------------
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


# ------------------------------------------------------------
# Get current logged-in user from JWT
# ------------------------------------------------------------
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:

    token = credentials.credentials

    try:
        # Decode token (Will raise PyJWT errors if invalid/expired)
        payload = decode_token(token)
        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload: missing subject",
                headers={"WWW-Authenticate": "Bearer"},
            )

    except jwt.ExpiredSignatureError:
        # --- CATCH EXPIRED TOKEN ---
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        # --- CATCH INVALID TOKEN ---
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        # --- CATCH EVERYTHING ELSE ---
        print(f"Auth Error: {str(e)}") # Debug log
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user by ID
    user = await get_user_by_id(session, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


# ------------------------------------------------------------
# Role-based access control
# ------------------------------------------------------------
def role_required(*allowed_roles: UserRole):
    def normalize_role(role):
        if isinstance(role, UserRole):
            return role.value.strip().lower()
        return str(role).strip().lower()

    normalized_allowed = set(normalize_role(r) for r in allowed_roles)

    async def checker(current_user: User = Depends(get_current_user)):
        user_role_normalized = normalize_role(current_user.role)

        if user_role_normalized not in normalized_allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied for role '{current_user.role.value if isinstance(current_user.role, UserRole) else current_user.role}'"
            )

        return current_user

    return checker


# ------------------------------------------------------------
# Exposed dependencies for routers
# ------------------------------------------------------------

require_super_admin = role_required(UserRole.Admin)
require_dean = role_required(UserRole.Dean)
require_staff = role_required(UserRole.Staff)
require_student = role_required(UserRole.Student)