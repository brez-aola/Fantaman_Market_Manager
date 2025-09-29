"""Authentication and authorization module.

This module provides JWT-based authentication, session management,
and role-based access control (RBAC) functionality.
"""

from .auth_service import AuthService
from .decorators import requires_auth, requires_permission, requires_role
from .jwt_manager import JWTManager
from .middleware import AuthMiddleware

__all__ = [
    "AuthService",
    "JWTManager",
    "AuthMiddleware",
    "requires_auth",
    "requires_role",
    "requires_permission",
]
