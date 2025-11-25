# app/core/rbac.py

from fastapi import Depends, HTTPException, status
from app.api.deps import get_current_user
from app.models.user import User, UserRole


def AllowRoles(*allowed_roles):
    """
    Flexible RBAC:
    - Works with both UserRole enums & raw strings
    - Case-insensitive
    - Admin always bypasses
    """

    def normalize(role) -> str:
        if isinstance(role, UserRole):
            return role.value.lower().strip()
        return str(role).lower().strip()

    normalized_allowed = {normalize(r) for r in allowed_roles}

    async def role_checker(current_user: User = Depends(get_current_user)):
        user_role_raw = current_user.role

        # Normalize user's role for comparison
        user_role = normalize(user_role_raw)

        # Admin always allowed
        if user_role == "admin":
            return current_user

        # Role not allowed?
        if user_role not in normalized_allowed:
            readable_role = (
                user_role_raw.value if isinstance(user_role_raw, UserRole)
                else str(user_role_raw)
            )  # ensures "HOD" instead of "UserRole.HOD"

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied for role '{readable_role}'"
            )

        return current_user

    return role_checker
