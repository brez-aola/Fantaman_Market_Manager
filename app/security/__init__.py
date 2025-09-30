"""Security module for API protection.

Provides authentication, authorization, rate limiting, and input validation.
"""

from .config import init_security, SecurityConfig, get_rate_limit
from .auth_service import AuthenticationService, auth_service
from .decorators import (
    validate_json, jwt_required_with_logging, require_roles,
    log_api_request, security_headers, rate_limit_key_func
)

__all__ = [
    'init_security',
    'SecurityConfig',
    'get_rate_limit',
    'AuthenticationService',
    'auth_service',
    'validate_json',
    'jwt_required_with_logging',
    'require_roles',
    'log_api_request',
    'security_headers',
    'rate_limit_key_func'
]
