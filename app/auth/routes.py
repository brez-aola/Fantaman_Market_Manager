"""Authentication API blueprint.

Provides REST API endpoints for user authentication, registration,
and account management.
"""

import logging

from flask import Blueprint, current_app, g, jsonify, request

from .auth_service import AuthService
from .decorators import get_current_user, requires_auth, requires_role
from .jwt_manager import JWTManager

logger = logging.getLogger(__name__)

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.route("/debug-auth", methods=["GET"])
def debug_auth():
    """Debug endpoint to test authentication without decorator."""
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        return jsonify({"error": "Authorization header missing"}), 401

    try:
        token_type, token = auth_header.split(" ", 1)
        if token_type.lower() != "bearer":
            return jsonify({"error": "Invalid authorization header format"}), 401
    except ValueError:
        return jsonify({"error": "Invalid authorization header format"}), 401

    # Verify token
    jwt_manager = JWTManager()
    payload = jwt_manager.verify_token(token)

    if not payload:
        return jsonify({"error": "Invalid or expired token"}), 401

    # Check session
    Session = current_app.extensions["db_session_factory"]
    session = Session()

    try:
        from ..models import User, UserSession

        user_session = (
            session.query(UserSession)
            .filter(UserSession.session_token == token, UserSession.is_active.is_(True))
            .first()
        )

        if not user_session or user_session.is_expired():
            return jsonify({"error": "Session expired"}), 401

        user = session.query(User).get(payload["user_id"])
        if not user or not user.is_active:
            return jsonify({"error": "User account inactive"}), 401

        return jsonify(
            {
                "success": True,
                "message": "All authentication checks passed",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "is_active": user.is_active,
                },
                "session": {
                    "id": user_session.id,
                    "expires_at": user_session.expires_at.isoformat(),
                    "is_expired": user_session.is_expired(),
                },
                "payload": payload,
            }
        )

    except Exception as e:
        current_app.logger.error(f"Debug auth error: {e}")
        import traceback

        current_app.logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@bp.route("/simple-test", methods=["GET"])
def simple_test():
    """Simple test endpoint to verify decorator is working."""
    try:
        from ..models import User

        Session = current_app.extensions["db_session_factory"]
        session = Session()
        user = session.query(User).first()
        if user:
            user_data = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
            }
        else:
            user_data = None

        session.close()

        return jsonify(
            {
                "message": "Simple test passed",
                "user_count": 1 if user else 0,
                "user": user_data,
            }
        )
    except Exception as e:
        import traceback

        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@bp.route("/test-decorator", methods=["GET"])
@requires_auth
def test_decorator():
    """Test endpoint to check if decorator works."""
    try:
        return jsonify(
            {
                "message": "Decorator test passed",
                "g_user_id": getattr(g, "current_user_id", None),
                "g_user_data": getattr(g, "current_user_data", None),
                "session_id": getattr(g, "current_session_id", None),
            }
        )
    except Exception as e:
        import traceback

        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


def get_auth_service() -> AuthService:
    """Get authentication service instance."""
    session_factory = current_app.extensions["db_session_factory"]
    return AuthService(session_factory)


@bp.route("/login", methods=["POST"])
def login():
    """Authenticate user and return JWT tokens."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        username_or_email = data.get("username") or data.get("email")
        password = data.get("password")

        if not username_or_email or not password:
            return jsonify({"error": "Username/email and password required"}), 400

        # Get client info
        ip_address = request.remote_addr
        user_agent = request.headers.get("User-Agent")

        # Authenticate
        auth_service = get_auth_service()
        tokens, error = auth_service.authenticate_user(
            username_or_email, password, ip_address, user_agent
        )

        if error:
            return jsonify({"error": error}), 401

        return jsonify({"message": "Login successful", **tokens}), 200

    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/register", methods=["POST"])
def register():
    """Register a new user account."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        username = data.get("username")
        email = data.get("email")
        password = data.get("password")
        full_name = data.get("full_name")

        # Basic validation
        if not username or not email or not password:
            return jsonify({"error": "Username, email, and password required"}), 400

        if len(password) < 8:
            return jsonify({"error": "Password must be at least 8 characters"}), 400

        # Create user
        auth_service = get_auth_service()
        user, error = auth_service.create_user(
            username=username, email=email, password=password, full_name=full_name
        )

        if error:
            return jsonify({"error": error}), 400

        return (
            jsonify(
                {
                    "message": "User registered successfully",
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "full_name": user.full_name,
                    },
                }
            ),
            201,
        )

    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/refresh", methods=["POST"])
def refresh_token():
    """Refresh access token using refresh token."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        refresh_token = data.get("refresh_token")
        if not refresh_token:
            return jsonify({"error": "Refresh token required"}), 400

        # Refresh tokens
        jwt_manager = JWTManager()
        session_factory = current_app.extensions["db_session_factory"]

        tokens = jwt_manager.refresh_access_token(refresh_token, session_factory)

        if not tokens:
            return jsonify({"error": "Invalid or expired refresh token"}), 401

        # Remove session object from response
        tokens.pop("session", None)

        return jsonify({"message": "Token refreshed successfully", **tokens}), 200

    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/logout", methods=["POST"])
@requires_auth
def logout():
    """Logout user by revoking current session."""
    try:
        user = get_current_user()
        token = getattr(g, "current_token", None)

        if not token:
            return jsonify({"error": "No active session"}), 400

        # Logout user
        auth_service = get_auth_service()
        success = auth_service.logout_user(token, user.id if user else None)

        if success:
            return jsonify({"message": "Logged out successfully"}), 200
        else:
            return jsonify({"error": "Logout failed"}), 500

    except Exception as e:
        logger.error(f"Logout error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/me", methods=["GET"])
@requires_auth
def get_current_user_info():
    """Get current user information."""
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Simple response to debug
        return (
            jsonify(
                {
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "is_active": user.is_active,
                        "created_at": user.created_at,  # created_at is already a string from get_current_user()
                    }
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Get user info error: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


@bp.route("/change-password", methods=["POST"])
@requires_auth
def change_password():
    """Change user password."""
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        current_password = data.get("current_password")
        new_password = data.get("new_password")

        if not current_password or not new_password:
            return jsonify({"error": "Current and new password required"}), 400

        if len(new_password) < 8:
            return jsonify({"error": "New password must be at least 8 characters"}), 400

        # Change password
        auth_service = get_auth_service()
        success, error = auth_service.change_password(
            user.id, current_password, new_password
        )

        if error:
            return jsonify({"error": error}), 400

        return jsonify({"message": "Password changed successfully"}), 200

    except Exception as e:
        logger.error(f"Change password error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/users", methods=["GET"])
@requires_role(["admin", "super_admin"])
def list_users():
    """List all users (admin only)."""
    try:
        page = int(request.args.get("page", 1))
        per_page = min(int(request.args.get("per_page", 20)), 100)  # Max 100 per page
        search = request.args.get("search", "").strip() or None

        auth_service = get_auth_service()
        user_dicts, total = auth_service.list_users(page, per_page, search)

        return (
            jsonify(
                {
                    "users": user_dicts,
                    "pagination": {
                        "page": page,
                        "per_page": per_page,
                        "total": total,
                        "pages": (total + per_page - 1) // per_page,
                    },
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"List users error: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/users/<int:user_id>/roles", methods=["POST"])
@requires_role(["admin", "super_admin"])
def assign_user_role(user_id: int):
    """Assign role to user (admin only)."""
    try:
        current_user = get_current_user()
        data = request.get_json()

        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        role_name = data.get("role")
        if not role_name:
            return jsonify({"error": "Role name required"}), 400

        auth_service = get_auth_service()
        success, error = auth_service.assign_role(user_id, role_name, current_user.id)

        if error:
            return jsonify({"error": error}), 400

        return jsonify({"message": f"Role '{role_name}' assigned successfully"}), 200

    except Exception as e:
        logger.error(f"Assign role error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/users/<int:user_id>/roles/<role_name>", methods=["DELETE"])
@requires_role(["admin", "super_admin"])
def remove_user_role(user_id: int, role_name: str):
    """Remove role from user (admin only)."""
    try:
        current_user = get_current_user()

        auth_service = get_auth_service()
        success, error = auth_service.remove_role(user_id, role_name, current_user.id)

        if error:
            return jsonify({"error": error}), 400

        return jsonify({"message": f"Role '{role_name}' removed successfully"}), 200

    except Exception as e:
        logger.error(f"Remove role error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({"error": "Endpoint not found"}), 404


@bp.errorhandler(405)
def method_not_allowed(error):
    """Handle 405 errors."""
    return jsonify({"error": "Method not allowed"}), 405


@bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500
