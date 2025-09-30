"""Authentication and authorization decorators.

Provides decorators for protecting routes with authentication,
role-based access control, and permission-based access control.
"""

import datetime
from functools import wraps
from types import SimpleNamespace
from typing import Callable, Optional, Union

from flask import current_app, g, jsonify, request

from ..models import User
from .jwt_manager import JWTManager


def get_current_user() -> Optional[User]:
    """Get current authenticated user from Flask g object."""
    # If we have primitive user data stored in g, return a lightweight object
    data = getattr(g, "current_user_data", None)
    if data:
        user_obj = SimpleNamespace(**{k: v for k, v in data.items()})

        # attach convenience methods that use flattened lists in g
        def has_role(role_name: str) -> bool:
            roles = getattr(g, "current_user_roles", []) or []
            return role_name in roles

        def has_permission(permission_name: str) -> bool:
            perms = getattr(g, "current_user_permissions", []) or []
            return permission_name in perms

        user_obj.has_role = has_role
        user_obj.has_permission = has_permission
        return user_obj

    # Fallback: attempt to load a fresh ORM user (not preferred)
    user_id = getattr(g, "current_user_id", None)
    if not user_id:
        return None

    Session = getattr(g, "db_session_factory", None)
    if not Session:
        Session = current_app.extensions["db_session_factory"]

        # Load user and related roles/permissions while session is open.
    session = Session()
    try:
        user = session.query(User).get(user_id)
        if not user:
            return None

        # Use explicit scalar queries to fetch role and permission names
        try:
            from ..models import Permission, Role, RolePermission, UserRole

            role_rows = (
                session.query(Role.name)
                .join(UserRole, Role.id == UserRole.role_id)
                .filter(UserRole.user_id == user.id)
                .all()
            )
            user_roles = [r[0] for r in role_rows]
        except Exception:  # nosec: B110 - graceful auth degradation
            user_roles = []

        perms = set()
        try:
            perm_rows = (
                session.query(Permission.name)
                .join(RolePermission, Permission.id == RolePermission.permission_id)
                .join(Role, RolePermission.role_id == Role.id)
                .join(UserRole, UserRole.role_id == Role.id)
                .filter(UserRole.user_id == user.id)
                .all()
            )
            for p in perm_rows:
                perms.add(p[0])
        except Exception:  # nosec: B110 - graceful auth degradation
            pass

        data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }

        user_obj = SimpleNamespace(**data)

        def has_role(role_name: str) -> bool:
            return role_name in user_roles

        def has_permission(permission_name: str) -> bool:
            return permission_name in perms

        user_obj.has_role = has_role
        user_obj.has_permission = has_permission
        return user_obj
    finally:
        session.close()


def requires_auth(f: Callable) -> Callable:
    """Decorator that requires valid JWT authentication."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Check for Authorization header
            auth_header = request.headers.get("Authorization")

            if not auth_header:
                return jsonify({"error": "Authorization header missing"}), 401

            # Extract token from "Bearer <token>" format
            try:
                token_type, token = auth_header.split(" ", 1)
                if token_type.lower() != "bearer":
                    return (
                        jsonify({"error": "Invalid authorization header format"}),
                        401,
                    )
            except ValueError:
                return jsonify({"error": "Invalid authorization header format"}), 401

            # Verify token
            jwt_manager = JWTManager()
            payload = jwt_manager.verify_token(token)

            if not payload:
                return jsonify({"error": "Invalid or expired token"}), 401

            # Check if session is still active
            Session = current_app.extensions["db_session_factory"]
            session = Session()

            try:
                from ..models import UserSession

                user_session = (
                    session.query(UserSession)
                    .filter(
                        UserSession.session_token == token,
                        UserSession.is_active,
                    )
                    .first()
                )

                if not user_session or user_session.is_expired():
                    session.close()
                    return jsonify({"error": "Session expired"}), 401

                # Get user
                user = session.query(User).get(payload["user_id"])
                if not user or not user.is_active:
                    session.close()
                    return jsonify({"error": "User account inactive"}), 401

                # Force loading of all user attributes before storing
                user_id = user.id
                username = user.username
                email = user.email
                is_active = user.is_active
                created_at = user.created_at
                # Collect roles and permissions as primitive lists while session is open
                try:
                    from ..models import Permission, Role, RolePermission, UserRole

                    role_rows = (
                        session.query(Role.name)
                        .join(UserRole, Role.id == UserRole.role_id)
                        .filter(UserRole.user_id == user.id)
                        .all()
                    )
                    user_roles = [r[0] for r in role_rows]
                except Exception:  # nosec: B110 - graceful auth degradation
                    user_roles = []

                perms = set()
                try:
                    perm_rows = (
                        session.query(Permission.name)
                        .join(
                            RolePermission,
                            Permission.id == RolePermission.permission_id,
                        )
                        .join(Role, RolePermission.role_id == Role.id)
                        .join(UserRole, UserRole.role_id == Role.id)
                        .filter(UserRole.user_id == user.id)
                        .all()
                    )
                    for p in perm_rows:
                        perms.add(p[0])
                except Exception:  # nosec: B110 - graceful auth degradation
                    pass

                # Store user ID, session info and flattened roles/permissions in g
                g.current_user_id = user_id
                g.current_user_data = {
                    "id": user_id,
                    "username": username,
                    "email": email,
                    "is_active": is_active,
                    "created_at": created_at.isoformat() if created_at else None,
                }
                g.current_user_roles = user_roles
                g.current_user_permissions = list(perms)
                g.current_token = token
                g.current_session_id = user_session.id

                # Store the session factory for use by get_current_user
                g.db_session_factory = Session

                # Update last used timestamp (in separate transaction to avoid blocking main logic)
                try:
                    user_session.last_used_at = datetime.datetime.utcnow()
                    session.commit()
                except Exception as commit_error:
                    # Log but don't fail authentication for timestamp update issues
                    current_app.logger.warning(
                        f"Failed to update session timestamp: {commit_error}"
                    )
                    session.rollback()

            except Exception as db_error:
                session.rollback()
                current_app.logger.error(
                    f"Database error in authentication: {db_error}"
                )
                import traceback

                current_app.logger.error(traceback.format_exc())
                return jsonify({"error": "Authentication database error"}), 500
            finally:
                session.close()

            # Call the decorated function
            return f(*args, **kwargs)

        except Exception as e:
            # If any unexpected error occurs, log and return a generic auth error.
            current_app.logger.error(f"Unexpected authentication error: {e}")
            import traceback

            current_app.logger.error(traceback.format_exc())
            return jsonify({"error": "Authentication system error"}), 500

    return decorated_function


def requires_role(role: Union[str, list]) -> Callable:
    """Decorator that requires user to have specific role(s)."""

    def decorator(f: Callable) -> Callable:

        @wraps(f)
        @requires_auth
        def decorated_function(*args, **kwargs):
            # Prefer flattened roles set stored in g during authentication
            user_roles = getattr(g, "current_user_roles", None)
            if user_roles is None:
                # If roles were not populated during authentication, deny access
                # instead of attempting to re-load ORM objects which may be detached.
                return jsonify({"error": "Authentication required"}), 401

            # Handle single role or list of roles
            required_roles = [role] if isinstance(role, str) else role

            # Check if user has any of the required roles
            if not any(req_role in user_roles for req_role in required_roles):
                return (
                    jsonify(
                        {
                            "error": f"Insufficient privileges. Required roles: {required_roles}"
                        }
                    ),
                    403,
                )

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def requires_permission(permission: str) -> Callable:
    """Decorator that requires user to have specific permission."""

    def decorator(f: Callable) -> Callable:

        @wraps(f)
        @requires_auth
        def decorated_function(*args, **kwargs):
            # Prefer flattened permissions stored in g
            user_perms = getattr(g, "current_user_permissions", None)
            if user_perms is None:
                # Don't attempt to lazily load permissions from ORM fallback; require auth to set them.
                return jsonify({"error": "Authentication required"}), 401

            # Check if user has the required permission
            if permission not in user_perms:
                return (
                    jsonify(
                        {
                            "error": f"Insufficient privileges. Required permission: {permission}"
                        }
                    ),
                    403,
                )

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def requires_own_resource_or_role(role: str, resource_id_param: str = "id") -> Callable:
    """Decorator that allows access if user owns the resource OR has specific role."""

    def decorator(f: Callable) -> Callable:

        @wraps(f)
        @requires_auth
        def decorated_function(*args, **kwargs):
            # Use flattened roles from g instead of get_current_user() to avoid ORM calls
            user_roles = getattr(g, "current_user_roles", None)
            user_data = getattr(g, "current_user_data", None)

            if user_roles is None or user_data is None:
                return jsonify({"error": "Authentication required"}), 401

            # Check if user has the bypass role
            if role in user_roles:
                return f(*args, **kwargs)

            # Check if user owns the resource
            resource_id = kwargs.get(resource_id_param) or request.view_args.get(
                resource_id_param
            )

            if resource_id and str(user_data["id"]) == str(resource_id):
                return f(*args, **kwargs)

            return (
                jsonify(
                    {"error": f"Access denied. Must own resource or have {role} role"}
                ),
                403,
            )

        return decorated_function

    return decorator


def optional_auth(f: Callable) -> Callable:
    """Decorator that provides authentication info if available but doesn't require it."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Try to authenticate but don't fail if not present
        auth_header = request.headers.get("Authorization")

        if auth_header:
            try:
                token_type, token = auth_header.split(" ", 1)
                if token_type.lower() == "bearer":
                    jwt_manager = JWTManager()
                    payload = jwt_manager.verify_token(token)

                    if payload:
                        Session = current_app.extensions["db_session_factory"]
                        session = Session()
                        try:
                            from ..models import UserSession

                            user_session = (
                                session.query(UserSession)
                                .filter(
                                    UserSession.session_token == token,
                                    UserSession.is_active,
                                )
                                .first()
                            )

                            if user_session and not user_session.is_expired():
                                user = session.query(User).get(payload["user_id"])
                                if user and user.is_active:
                                    # Convert to primitives using scalar queries
                                    try:
                                        from ..models import (
                                            Permission,
                                            Role,
                                            RolePermission,
                                            UserRole,
                                        )

                                        role_rows = (
                                            session.query(Role.name)
                                            .join(UserRole, Role.id == UserRole.role_id)
                                            .filter(UserRole.user_id == user.id)
                                            .all()
                                        )
                                        user_roles = [r[0] for r in role_rows]
                                    except (
                                        Exception
                                    ):  # nosec: B110 - graceful auth degradation
                                        user_roles = []

                                    perms = set()
                                    try:
                                        perm_rows = (
                                            session.query(Permission.name)
                                            .join(
                                                RolePermission,
                                                Permission.id
                                                == RolePermission.permission_id,
                                            )
                                            .join(
                                                Role, RolePermission.role_id == Role.id
                                            )
                                            .join(UserRole, UserRole.role_id == Role.id)
                                            .filter(UserRole.user_id == user.id)
                                            .all()
                                        )
                                        for p in perm_rows:
                                            perms.add(p[0])
                                    except (
                                        Exception
                                    ):  # nosec: B110 - graceful auth degradation
                                        pass

                                    g.current_user_data = {
                                        "id": user.id,
                                        "username": user.username,
                                        "email": user.email,
                                        "is_active": user.is_active,
                                        "created_at": (
                                            user.created_at.isoformat()
                                            if user.created_at
                                            else None
                                        ),
                                    }
                                    g.current_user_roles = user_roles
                                    g.current_user_permissions = list(perms)
                                    g.current_token = token
                                    g.current_session_id = user_session.id

                        except Exception:  # nosec: B110 - graceful auth degradation
                            pass  # Ignore errors in optional auth
                        finally:
                            session.close()

            except Exception:  # nosec: B110 - graceful auth degradation
                pass  # Ignore errors in optional auth

        return f(*args, **kwargs)

    return decorated_function
