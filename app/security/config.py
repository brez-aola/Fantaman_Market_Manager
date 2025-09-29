"""Security configuration for JWT authentication and rate limiting.

Configures Flask-JWT-Extended and Flask-Limiter with Azure security best practices.
"""

import os
import secrets
from datetime import timedelta
from flask import Flask, request
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from typing import Dict, Any

from app.security.decorators import rate_limit_key_func


class SecurityConfig:
    """Security configuration constants."""

    # JWT Configuration
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', secrets.token_urlsafe(32))
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_ALGORITHM = 'HS256'
    JWT_BLACKLIST_ENABLED = True
    JWT_BLACKLIST_TOKEN_CHECKS = ['access', 'refresh']

    # Rate Limiting Configuration
    RATELIMIT_STORAGE_URL = os.getenv('REDIS_URL', 'memory://')
    RATELIMIT_STRATEGY = 'fixed-window'
    RATELIMIT_HEADERS_ENABLED = True

    # API Rate Limits (requests per minute)
    RATE_LIMITS = {
        'default': '1000 per hour',
        'auth': '10 per minute',
        'create': '100 per hour',
        'read': '500 per hour',
        'update': '200 per hour',
        'delete': '50 per hour',
        'market': '100 per hour'
    }

    # Security Headers
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://localhost:5000').split(',')
    CORS_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
    CORS_HEADERS = ['Content-Type', 'Authorization']


def init_security(app: Flask) -> tuple[JWTManager, Limiter]:
    """Initialize security components.

    Args:
        app: Flask application instance

    Returns:
        Tuple of (jwt_manager, limiter)
    """

    # Configure JWT
    app.config['JWT_SECRET_KEY'] = SecurityConfig.JWT_SECRET_KEY
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = SecurityConfig.JWT_ACCESS_TOKEN_EXPIRES
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = SecurityConfig.JWT_REFRESH_TOKEN_EXPIRES
    app.config['JWT_ALGORITHM'] = SecurityConfig.JWT_ALGORITHM
    app.config['JWT_BLACKLIST_ENABLED'] = SecurityConfig.JWT_BLACKLIST_ENABLED
    app.config['JWT_BLACKLIST_TOKEN_CHECKS'] = SecurityConfig.JWT_BLACKLIST_TOKEN_CHECKS

    # Initialize JWT manager
    jwt = JWTManager(app)

    # Initialize rate limiter
    limiter = Limiter(
        app=app,
        key_func=rate_limit_key_func,
        default_limits=[SecurityConfig.RATE_LIMITS['default']],
        storage_uri=SecurityConfig.RATELIMIT_STORAGE_URL,
        strategy=SecurityConfig.RATELIMIT_STRATEGY,
        headers_enabled=SecurityConfig.RATELIMIT_HEADERS_ENABLED
    )

    # JWT token blacklist (in production, use Redis or database)
    blacklisted_tokens = set()

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header: Dict[str, Any], jwt_payload: Dict[str, Any]) -> bool:
        """Check if JWT token is blacklisted."""
        jti = jwt_payload['jti']  # JWT ID
        return jti in blacklisted_tokens

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header: Dict[str, Any], jwt_payload: Dict[str, Any]) -> tuple:
        """Return error response for revoked tokens."""
        return {
            'error': 'Token has been revoked',
            'code': 'TOKEN_REVOKED'
        }, 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header: Dict[str, Any], jwt_payload: Dict[str, Any]) -> tuple:
        """Return error response for expired tokens."""
        return {
            'error': 'Token has expired',
            'code': 'TOKEN_EXPIRED'
        }, 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error: str) -> tuple:
        """Return error response for invalid tokens."""
        return {
            'error': 'Invalid token',
            'code': 'INVALID_TOKEN',
            'details': error
        }, 401

    @jwt.unauthorized_loader
    def missing_token_callback(error: str) -> tuple:
        """Return error response for missing tokens."""
        return {
            'error': 'Authorization token required',
            'code': 'MISSING_TOKEN'
        }, 401

    @jwt.needs_fresh_token_loader
    def token_not_fresh_callback(jwt_header: Dict[str, Any], jwt_payload: Dict[str, Any]) -> tuple:
        """Return error response for non-fresh tokens."""
        return {
            'error': 'Fresh token required',
            'code': 'FRESH_TOKEN_REQUIRED'
        }, 401

    @jwt.additional_claims_loader
    def add_claims_to_jwt(identity: str) -> Dict[str, Any]:
        """Add additional claims to JWT token."""
        # In a real application, fetch user roles from database
        # For now, return default roles
        return {
            'roles': ['user'],  # Default role
            'permissions': ['read', 'create']
        }

    # Rate limiter error handler
    @limiter.request_filter
    def rate_limit_exempt() -> bool:
        """Exempt certain requests from rate limiting."""
        # Exempt health check endpoint
        return request.endpoint == 'api.health_check'

    # Store references for token management
    app.jwt_blacklist = blacklisted_tokens

    return jwt, limiter


def get_rate_limit(operation: str) -> str:
    """Get rate limit for specific operation.

    Args:
        operation: Operation type (auth, create, read, update, delete, market)

    Returns:
        Rate limit string
    """
    return SecurityConfig.RATE_LIMITS.get(operation, SecurityConfig.RATE_LIMITS['default'])
