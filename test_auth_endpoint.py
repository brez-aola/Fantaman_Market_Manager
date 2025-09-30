"""
Simple test endpoint to debug authentication issues.
"""

from flask import Blueprint, jsonify, request, current_app, g
from app.auth.jwt_manager import JWTManager

# Create a test blueprint
test_bp = Blueprint("test_auth", __name__, url_prefix="/test")


@test_bp.route("/simple-auth", methods=["GET"])
def simple_auth_test():
    """Simple authentication test without decorators."""
    try:
        # Step 1: Check Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"error": "No Authorization header"}), 401

        # Step 2: Extract token
        try:
            token_type, token = auth_header.split(" ", 1)
            if token_type.lower() != "bearer":
                return jsonify({"error": "Invalid token type"}), 401
        except ValueError:
            return jsonify({"error": "Invalid Authorization format"}), 401

        # Step 3: Verify JWT
        jwt_manager = JWTManager()
        payload = jwt_manager.verify_token(token)

        if not payload:
            return jsonify({"error": "Invalid token"}), 401

        # Step 4: Query database
        Session = current_app.extensions["db_session_factory"]
        session = Session()

        try:
            from app.models import User, UserSession

            # Get user
            user = session.query(User).get(payload["user_id"])
            if not user:
                return jsonify({"error": "User not found"}), 401

            # Get session
            user_session = session.query(UserSession).filter(
                UserSession.session_token == token,
                UserSession.is_active == True
            ).first()

            if not user_session:
                return jsonify({"error": "Session not found"}), 401

            if user_session.is_expired():
                return jsonify({"error": "Session expired"}), 401

            # Success response
            return jsonify({
                "message": "Authentication successful",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email
                },
                "session": {
                    "id": user_session.id,
                    "expires_at": user_session.expires_at.isoformat()
                }
            }), 200

        except Exception as db_error:
            return jsonify({
                "error": "Database error",
                "details": str(db_error)
            }), 500
        finally:
            session.close()

    except Exception as e:
        return jsonify({
            "error": "Unexpected error",
            "details": str(e)
        }), 500


# Add route to main app
def register_test_blueprint(app):
    """Register test blueprint with the app."""
    app.register_blueprint(test_bp)
