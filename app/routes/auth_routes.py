"""Authentication API endpoints.

Provides login, registration, token refresh, and user management endpoints
with comprehensive security features.
"""

import logging
from flask import Blueprint, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from app.security.decorators import (
    validate_json, jwt_required_with_logging, require_roles,
    log_api_request, security_headers, apply_rate_limit
)
from app.security.config import get_rate_limit
from app.security.auth_service import auth_service
from app.validation.schemas import login_schema, register_schema

logger = logging.getLogger(__name__)

# Create authentication blueprint
# Note: no internal url_prefix here. The blueprint is registered in app.create_app
# with `url_prefix='/api/v1/auth'` so routes will be mounted at `/api/v1/auth/...`.
auth_bp = Blueprint('security_auth', __name__)


@auth_bp.route('/login', methods=['POST'])
@security_headers()
@log_api_request()
@apply_rate_limit(get_rate_limit('auth'))
@validate_json(login_schema)
def login():
    """User login endpoint.

    Rate limited to prevent brute force attacks.
    """
    try:
        # Get validated data
        data = g.validated_data
        username = data['username']
        password = data['password']

        # Authenticate user
        success, message, user = auth_service.authenticate_user(username, password)

        if not success:
            return jsonify({
                'error': message,
                'code': 'AUTHENTICATION_FAILED'
            }), 401

        # Create JWT tokens
        tokens = auth_service.create_tokens(user)

        return jsonify({
            'message': 'Login successful',
            'user': {
                'username': user.username,
                'email': user.email,
                'roles': user.roles
            },
            **tokens
        }), 200

    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({
            'error': 'Login failed',
            'code': 'LOGIN_ERROR'
        }), 500


@auth_bp.route('/register', methods=['POST'])
@security_headers()
@log_api_request()
@apply_rate_limit(get_rate_limit('auth'))
@validate_json(register_schema)
def register():
    """User registration endpoint.

    Rate limited to prevent spam registration.
    """
    try:
        # Get validated data
        data = g.validated_data
        username = data['username']
        email = data['email']
        password = data['password']

        # Register user
        success, message, user = auth_service.register_user(username, email, password)

        if not success:
            return jsonify({
                'error': message,
                'code': 'REGISTRATION_FAILED'
            }), 400

        # Create JWT tokens for immediate login
        tokens = auth_service.create_tokens(user)

        return jsonify({
            'message': 'Registration successful',
            'user': {
                'username': user.username,
                'email': user.email,
                'roles': user.roles
            },
            **tokens
        }), 201

    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({
            'error': 'Registration failed',
            'code': 'REGISTRATION_ERROR'
        }), 500


@auth_bp.route('/refresh', methods=['POST'])
@security_headers()
@log_api_request()
@apply_rate_limit(get_rate_limit('auth'))
@jwt_required(refresh=True)
def refresh():
    """Token refresh endpoint.

    Requires a valid refresh token.
    """
    try:
        # Get current user from refresh token
        current_user_username = get_jwt_identity()
        user = auth_service.get_user(current_user_username)

        if not user or not user.is_active:
            return jsonify({
                'error': 'User not found or inactive',
                'code': 'USER_INACTIVE'
            }), 401

        # Create new access token
        tokens = auth_service.create_tokens(user)

        return jsonify({
            'message': 'Token refreshed successfully',
            'access_token': tokens['access_token'],
            'token_type': 'Bearer',
            'expires_in': tokens['expires_in']
        }), 200

    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        return jsonify({
            'error': 'Token refresh failed',
            'code': 'REFRESH_ERROR'
        }), 500


@auth_bp.route('/logout', methods=['POST'])
@security_headers()
@log_api_request()
@apply_rate_limit(get_rate_limit('delete'))
@jwt_required()
def logout():
    """User logout endpoint.

    Blacklists the current JWT token.
    """
    try:
        # Get token JTI
        jti = get_jwt()['jti']

        # Add token to blacklist
        auth_service.revoke_token(jti)

        logger.info(f"User logged out: {get_jwt_identity()}")

        return jsonify({
            'message': 'Logout successful',
            'code': 'LOGOUT_SUCCESS'
        }), 200

    except Exception as e:
        logger.error(f"Logout error: {e}")
        return jsonify({
            'error': 'Logout failed',
            'code': 'LOGOUT_ERROR'
        }), 500


@auth_bp.route('/profile', methods=['GET'])
@security_headers()
@log_api_request()
@apply_rate_limit(get_rate_limit('read'))
@jwt_required_with_logging()
def profile():
    """Get current user profile.

    Requires authentication.
    """
    try:
        user = auth_service.get_user(g.current_user)

        if not user:
            return jsonify({
                'error': 'User not found',
                'code': 'USER_NOT_FOUND'
            }), 404

        return jsonify({
            'user': user.to_dict()
        }), 200

    except Exception as e:
        logger.error(f"Profile error: {e}")
        return jsonify({
            'error': 'Failed to get profile',
            'code': 'PROFILE_ERROR'
        }), 500


@auth_bp.route('/users', methods=['GET'])
@security_headers()
@log_api_request()
@apply_rate_limit(get_rate_limit('read'))
@jwt_required_with_logging()
@require_roles('admin')
def list_users():
    """List all users (admin only).

    Requires admin role.
    """
    try:
        users = []
        for user in auth_service.users.values():
            user_dict = user.to_dict()
            # Don't include sensitive information
            users.append(user_dict)

        stats = auth_service.get_user_stats()

        return jsonify({
            'users': users,
            'statistics': stats,
            'total': len(users)
        }), 200

    except Exception as e:
        logger.error(f"List users error: {e}")
        return jsonify({
            'error': 'Failed to list users',
            'code': 'LIST_USERS_ERROR'
        }), 500


@auth_bp.route('/validate', methods=['GET'])
@security_headers()
@log_api_request()
@apply_rate_limit(get_rate_limit('update'))
@jwt_required_with_logging()
def validate_token():
    """Validate current JWT token.

    Returns token information if valid.
    """
    try:
        claims = get_jwt()
        user = auth_service.get_user(g.current_user)

        if not user:
            return jsonify({
                'error': 'User not found',
                'code': 'USER_NOT_FOUND'
            }), 404

        return jsonify({
            'valid': True,
            'user': {
                'username': user.username,
                'roles': user.roles
            },
            'token_info': {
                'issued_at': claims.get('iat'),
                'expires_at': claims.get('exp'),
                'token_type': claims.get('type', 'access')
            }
        }), 200

    except Exception as e:
        logger.error(f"Token validation error: {e}")
        return jsonify({
            'error': 'Token validation failed',
            'code': 'VALIDATION_ERROR'
        }), 500
