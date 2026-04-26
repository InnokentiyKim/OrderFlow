import uuid
from typing import Annotated

from app.common.auth_scheme import auth_header
from fastapi import Depends

from app.common.enums import UserRoleEnum
from app.core.security.exceptions import InvalidTokenError
from app.schemas.result import TokenPayload
from app.core.security.adapter import SecurityAdapter, provide_security_adapter
from app.common.exceptions import Forbidden


async def get_current_user(
    token: str = Depends(auth_header),
    security_adapter: SecurityAdapter = Depends(provide_security_adapter),
) -> TokenPayload:
    """Dependency to extract the current user's ID and role from the authentication token."""
    payload = await security_adapter.decode_jwt(token)
    user_id, role = payload.get("sub"), payload.get("role")
    if not user_id or not role:
        raise InvalidTokenError

    return TokenPayload(user_id=uuid.UUID(user_id), role=UserRoleEnum(role))


def verify_role(allowed_roles: list[str]):
    """
    Factory function that creates a dependency for specific roles.
    """

    async def role_checker(
        current_user: Annotated[TokenPayload, Depends(get_current_user)],
    ) -> TokenPayload:
        if current_user.role not in allowed_roles:
            raise Forbidden
        return current_user

    return role_checker


require_admin = verify_role([UserRoleEnum.ADMIN.value])
require_user = verify_role([UserRoleEnum.USER.value, UserRoleEnum.ADMIN.value])


CurrentUserDependency: Annotated[TokenPayload, Depends(get_current_user)]
RequireAdminDependency: Annotated[TokenPayload, Depends(require_admin)]
