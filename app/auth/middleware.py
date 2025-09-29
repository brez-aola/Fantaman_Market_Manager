"""Authentication middleware for Flask application.

Provides automatic token validation and user context injection
for all requests.
"""

import logging
from typing import Optional

from flask import Flask, request

from ..models import User, UserSession
from .jwt_manager import JWTManager

logger = logging.getLogger(__name__)


class AuthMiddleware:
    """Authentication middleware for automatic token processing."""

    def __init__(self, app: Optional[Flask] = None):
        self.jwt_manager = JWTManager()
        if app:
            self.init_app(app)

    def init_app(self, app: Flask):
        """Initialize middleware with Flask app."""
        app.before_request(self.before_request)
        app.after_request(self.after_request)

    def before_request(self):
        """Process authentication before each request."""
        # Skip authentication for certain endpoints
        if self._should_skip_auth():
            return
        # Initialize auth context (store primitives only to avoid detached ORM instances)
        from flask import current_app
        from flask import g as _g

        _g.current_user_data = None
        _g.current_user_roles = []
        _g.current_user_permissions = []
        _g.current_token = None
        _g.current_session_id = None
        _g.is_authenticated = False

        # Try to extract and validate token
        token = self._extract_token()
        if not token:
            return

        # Validate token
        try:
            payload = self.jwt_manager.verify_token(token)
            if not payload:
                return

            # Get session factory from app extensions
            Session = current_app.extensions.get("db_session_factory")
            if not Session:
                logger.error("Database session factory not found in app extensions")
                return

            session = Session()
            try:
                # Check if session is active
                user_session = (
                    session.query(UserSession)
                    .filter(
                        UserSession.session_token == token,
                        UserSession.is_active.is_(True),
                    )
                    .first()
                )

                if not user_session or user_session.is_expired():
                    return

                # Get user
                user = session.query(User).get(payload["user_id"])
                if not user or not user.is_active:
                    return

                # Set authentication context using primitives (avoid storing ORM objects)
                try:
                    from ..models import Permission, Role, RolePermission, UserRole

                    role_rows = (
                        session.query(Role.name)
                        .join(UserRole, Role.id == UserRole.role_id)
                        .filter(UserRole.user_id == user.id)
                        .all()
                    )
                    user_roles = [r[0] for r in role_rows]
                except Exception:
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
                except Exception:
                    pass

                _g.current_user_data = {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "is_active": user.is_active,
                    "created_at": (
                        user.created_at.isoformat() if user.created_at else None
                    ),
                }
                _g.current_user_roles = user_roles
                _g.current_user_permissions = list(perms)
                _g.current_token = token
                _g.current_session_id = user_session.id
                _g.is_authenticated = True

                # Update last used timestamp
                import datetime

                user_session.last_used_at = datetime.datetime.utcnow()
                session.commit()

            except Exception as e:
                session.rollback()
                logger.error(f"Authentication middleware error: {e}")
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Token validation error: {e}")

    def after_request(self, response):
        """Process response after request."""
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Add CORS headers if needed
        if request.method == "OPTIONS":
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, DELETE, OPTIONS"
            )
            response.headers["Access-Control-Allow-Headers"] = (
                "Content-Type, Authorization"
            )

        return response

    def _extract_token(self) -> Optional[str]:
        """Extract JWT token from request headers or cookies."""
        # Try Authorization header first
        auth_header = request.headers.get("Authorization")
        if auth_header:
            try:
                token_type, token = auth_header.split(" ", 1)
                if token_type.lower() == "bearer":
                    return token
            except ValueError:
                pass

        # Try cookie as fallback
        token = request.cookies.get("access_token")
        if token:
            return token

        return None

    def _should_skip_auth(self) -> bool:
        """Determine if authentication should be skipped for this request."""
        # Skip for static files
        if request.endpoint and request.endpoint.startswith("static"):
            return True

        # Skip for health check
        if request.endpoint == "api.health":
            return True

        # Skip for login/register endpoints
        auth_endpoints = [
            "auth.login",
            "auth.register",
            "auth.refresh",
            "auth.forgot_password",
            "auth.reset_password",
        ]

        if request.endpoint in auth_endpoints:
            return True

        # Skip for public API endpoints
        if request.endpoint and request.endpoint.startswith("api.public"):
            return True

        return False
