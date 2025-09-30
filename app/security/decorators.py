"""Security decorators for API endpoints.

Provides authentication, authorization, rate limiting, and validation decorators
following Azure security best practices.
"""

import logging
import time
from functools import wraps
from typing import Dict, Any, Optional, Callable
from flask import request, jsonify, g, current_app
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt
from marshmallow import Schema, ValidationError
from werkzeug.exceptions import TooManyRequests

logger = logging.getLogger(__name__)


def validate_json(schema: Schema):
    """Decorator for validating JSON request data using Marshmallow schema.

    Args:
        schema: Marshmallow schema for validation

    Returns:
        Decorated function with validated data in g.validated_data
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check if request has JSON data
            if not request.is_json:
                return jsonify({
                    "error": "Content-Type must be application/json",
                    "code": "INVALID_CONTENT_TYPE"
                }), 400

            try:
                # Get JSON data
                json_data = request.get_json()
                if json_data is None:
                    return jsonify({
                        "error": "No JSON data provided",
                        "code": "NO_JSON_DATA"
                    }), 400

                # Validate data using schema
                validated_data = schema.load(json_data)

                # Store validated data in g for use in the endpoint
                g.validated_data = validated_data

                return f(*args, **kwargs)

            except ValidationError as err:
                # Log validation errors for security monitoring
                logger.warning(
                    f"Validation error from {request.remote_addr}: {err.messages}",
                    extra={
                        "endpoint": request.endpoint,
                        "method": request.method,
                        "ip": request.remote_addr,
                        "validation_errors": err.messages
                    }
                )

                return jsonify({
                    "error": "Validation failed",
                    "code": "VALIDATION_ERROR",
                    "details": err.messages
                }), 400

            except Exception as err:
                logger.error(f"Unexpected error in validation: {err}")
                return jsonify({
                    "error": "Internal server error",
                    "code": "INTERNAL_ERROR"
                }), 500

        return decorated_function
    return decorator


def jwt_required_with_logging(optional: bool = False):
    """JWT authentication decorator with enhanced logging.

    Args:
        optional: If True, JWT is optional and won't fail if missing

    Returns:
        Decorated function with user identity in g.current_user
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # Verify JWT token
                verify_jwt_in_request(optional=optional)

                # Get user identity from JWT
                current_user = get_jwt_identity()
                g.current_user = current_user

                # Get additional claims
                claims = get_jwt()
                g.jwt_claims = claims

                # Log successful authentication
                if current_user:
                    logger.info(
                        f"Authenticated request from user {current_user}",
                        extra={
                            "user": current_user,
                            "endpoint": request.endpoint,
                            "method": request.method,
                            "ip": request.remote_addr
                        }
                    )

                return f(*args, **kwargs)

            except Exception as err:
                # Log authentication failures for security monitoring
                logger.warning(
                    f"Authentication failed from {request.remote_addr}: {err}",
                    extra={
                        "endpoint": request.endpoint,
                        "method": request.method,
                        "ip": request.remote_addr,
                        "error": str(err)
                    }
                )

                if not optional:
                    return jsonify({
                        "error": "Authentication required",
                        "code": "AUTHENTICATION_REQUIRED"
                    }), 401
                else:
                    g.current_user = None
                    g.jwt_claims = {}
                    return f(*args, **kwargs)

        return decorated_function
    return decorator


def require_roles(*roles: str):
    """Authorization decorator requiring specific roles.

    Args:
        *roles: Required roles (e.g., 'admin', 'manager', 'user')

    Returns:
        Decorated function that checks user roles
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check if user is authenticated
            if not hasattr(g, 'current_user') or not g.current_user:
                return jsonify({
                    "error": "Authentication required",
                    "code": "AUTHENTICATION_REQUIRED"
                }), 401

            # Get user roles from JWT claims
            user_roles = g.jwt_claims.get('roles', [])

            # Check if user has any of the required roles
            if not any(role in user_roles for role in roles):
                logger.warning(
                    f"Authorization failed: User {g.current_user} lacks required roles {roles}",
                    extra={
                        "user": g.current_user,
                        "required_roles": roles,
                        "user_roles": user_roles,
                        "endpoint": request.endpoint,
                        "method": request.method,
                        "ip": request.remote_addr
                    }
                )

                return jsonify({
                    "error": "Insufficient permissions",
                    "code": "INSUFFICIENT_PERMISSIONS",
                    "required_roles": list(roles)
                }), 403

            return f(*args, **kwargs)

        return decorated_function
    return decorator


def log_api_request(include_response_time: bool = True):
    """Decorator for comprehensive API request logging.

    Args:
        include_response_time: Whether to log response time

    Returns:
        Decorated function with request/response logging
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = time.time() if include_response_time else None

            # Log incoming request
            logger.info(
                f"API Request: {request.method} {request.path}",
                extra={
                    "method": request.method,
                    "path": request.path,
                    "endpoint": request.endpoint,
                    "ip": request.remote_addr,
                    "user_agent": request.headers.get('User-Agent'),
                    "content_length": request.content_length,
                    "query_params": dict(request.args),
                    "user": getattr(g, 'current_user', None)
                }
            )

            try:
                # Execute the function
                response = f(*args, **kwargs)

                # Log successful response
                if include_response_time:
                    duration = time.time() - start_time
                    logger.info(
                        f"API Response: {request.method} {request.path} - {duration:.3f}s",
                        extra={
                            "method": request.method,
                            "path": request.path,
                            "endpoint": request.endpoint,
                            "ip": request.remote_addr,
                            "response_time": duration,
                            "user": getattr(g, 'current_user', None)
                        }
                    )

                return response

            except Exception as err:
                # Log errors
                logger.error(
                    f"API Error: {request.method} {request.path} - {err}",
                    extra={
                        "method": request.method,
                        "path": request.path,
                        "endpoint": request.endpoint,
                        "ip": request.remote_addr,
                        "error": str(err),
                        "user": getattr(g, 'current_user', None)
                    },
                    exc_info=True
                )
                raise

        return decorated_function
    return decorator


def rate_limit_key_func():
    """Custom key function for rate limiting based on user or IP."""
    # Use authenticated user if available, otherwise use IP
    if hasattr(g, 'current_user') and g.current_user:
        return f"user:{g.current_user}"
    return f"ip:{request.remote_addr}"


def apply_rate_limit(limit_str: str):
    """Decorator factory that applies Flask-Limiter limits at runtime.

    This handles the case where the Limiter instance is attached to the Flask
    app after modules are imported (app.extensions['limiter']). The decorator
    defers binding the limiter until the first call and replaces the wrapped
    function with the limiter-wrapped function.

    Args:
        limit_str: rate limit string (e.g., '10 per minute')
    """
    from functools import wraps
    from flask import current_app

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            limiter = None
            try:
                limiter = current_app.extensions.get('limiter')
            except RuntimeError:
                # No app context; skip rate limiting
                limiter = None

            if limiter:
                # Bind the limiter decorator to the function and call it.
                limited = limiter.limit(limit_str)(f)
                # Replace the wrapper in closure with limited to avoid repeated binding
                return limited(*args, **kwargs)

            # Fallback: call original function if limiter not available
            return f(*args, **kwargs)

        return wrapper

    return decorator


def security_headers():
    """Decorator to add security headers to responses."""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            response = f(*args, **kwargs)

            # Ensure response is a Flask response object
            if not hasattr(response, 'headers'):
                response = current_app.make_response(response)

            # Add security headers
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            response.headers['Content-Security-Policy'] = "default-src 'self'"
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

            return response

        return decorated_function
    return decorator
