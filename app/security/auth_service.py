"""Authentication service for user management and JWT token generation.

Provides user registration, login, and token management following Azure security best practices.
"""

import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from flask import current_app
from flask_jwt_extended import create_access_token, create_refresh_token, get_jti
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User:
    """Simple User model for authentication.

    In production, this should be replaced with a proper database model.
    """

    def __init__(self, username: str, email: str, password_hash: str,
                 roles: list = None, created_at: datetime = None):
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.roles = roles or ['user']
        self.created_at = created_at or datetime.utcnow()
        self.is_active = True
        self.last_login = None

    def check_password(self, password: str) -> bool:
        """Verify password against hash."""
        return pwd_context.verify(password, self.password_hash)

    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary."""
        return {
            'username': self.username,
            'email': self.email,
            'roles': self.roles,
            'created_at': self.created_at.isoformat(),
            'is_active': self.is_active,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }


class AuthenticationService:
    """Authentication service for user management."""

    def __init__(self):
        # In-memory user storage (replace with database in production)
        self.users: Dict[str, User] = {}
        self._init_default_users()

    def _init_default_users(self):
        """Initialize default users for testing."""
        # Create default admin user
        admin_password = pwd_context.hash("admin123")
        self.users["admin"] = User(
            username="admin",
            email="admin@fantacalcio.local",
            password_hash=admin_password,
            roles=["admin", "user"]
        )

        # Create default test user
        user_password = pwd_context.hash("user123")
        self.users["testuser"] = User(
            username="testuser",
            email="testuser@fantacalcio.local",
            password_hash=user_password,
            roles=["user"]
        )

        logger.info("Initialized default users: admin, testuser")

    def register_user(self, username: str, email: str, password: str) -> Tuple[bool, str, Optional[User]]:
        """Register a new user.

        Args:
            username: Username
            email: User email
            password: Plain text password

        Returns:
            Tuple of (success, message, user)
        """
        try:
            # Check if username already exists
            if username.lower() in [u.username.lower() for u in self.users.values()]:
                return False, "Username already exists", None

            # Check if email already exists
            if email.lower() in [u.email.lower() for u in self.users.values()]:
                return False, "Email already exists", None

            # Hash password
            password_hash = pwd_context.hash(password)

            # Create user
            user = User(
                username=username,
                email=email,
                password_hash=password_hash
            )

            self.users[username] = user

            logger.info(f"User registered successfully: {username}")
            return True, "User registered successfully", user

        except Exception as e:
            logger.error(f"Error registering user {username}: {e}")
            return False, "Registration failed", None

    def authenticate_user(self, username: str, password: str) -> Tuple[bool, str, Optional[User]]:
        """Authenticate user credentials.

        Args:
            username: Username
            password: Plain text password

        Returns:
            Tuple of (success, message, user)
        """
        try:
            # Find user
            user = self.users.get(username)
            if not user:
                logger.warning(f"Authentication failed: User not found: {username}")
                return False, "Invalid credentials", None

            # Check if user is active
            if not user.is_active:
                logger.warning(f"Authentication failed: User inactive: {username}")
                return False, "Account is inactive", None

            # Verify password
            if not user.check_password(password):
                logger.warning(f"Authentication failed: Invalid password for user: {username}")
                return False, "Invalid credentials", None

            # Update last login
            user.last_login = datetime.utcnow()

            logger.info(f"User authenticated successfully: {username}")
            return True, "Authentication successful", user

        except Exception as e:
            logger.error(f"Error authenticating user {username}: {e}")
            return False, "Authentication failed", None

    def get_user(self, username: str) -> Optional[User]:
        """Get user by username.

        Args:
            username: Username

        Returns:
            User object or None
        """
        return self.users.get(username)

    def create_tokens(self, user: User) -> Dict[str, Any]:
        """Create JWT tokens for user.

        Args:
            user: User object

        Returns:
            Dictionary with access and refresh tokens
        """
        try:
            # Additional claims for JWT
            additional_claims = {
                'roles': user.roles,
                'email': user.email,
                'permissions': self._get_user_permissions(user)
            }

            # Create tokens
            access_token = create_access_token(
                identity=user.username,
                additional_claims=additional_claims
            )

            refresh_token = create_refresh_token(
                identity=user.username,
                additional_claims={'roles': user.roles}
            )

            # Get token JTIs for blacklist management
            access_jti = get_jti(access_token)
            refresh_jti = get_jti(refresh_token)

            logger.info(f"Tokens created for user: {user.username}")

            return {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'access_jti': access_jti,
                'refresh_jti': refresh_jti,
                'token_type': 'Bearer',
                'expires_in': int(current_app.config['JWT_ACCESS_TOKEN_EXPIRES'].total_seconds())
            }

        except Exception as e:
            logger.error(f"Error creating tokens for user {user.username}: {e}")
            raise

    def _get_user_permissions(self, user: User) -> list:
        """Get user permissions based on roles.

        Args:
            user: User object

        Returns:
            List of permissions
        """
        permissions = set()

        # Basic user permissions
        if 'user' in user.roles:
            permissions.update(['read', 'create_limited'])

        # Admin permissions
        if 'admin' in user.roles:
            permissions.update(['read', 'create', 'update', 'delete', 'manage_users'])

        # Manager permissions
        if 'manager' in user.roles:
            permissions.update(['read', 'create', 'update', 'manage_teams'])

        return list(permissions)

    def revoke_token(self, jti: str):
        """Add token to blacklist.

        Args:
            jti: JWT ID to blacklist
        """
        if hasattr(current_app, 'jwt_blacklist'):
            current_app.jwt_blacklist.add(jti)
            logger.info(f"Token revoked: {jti}")

    def get_user_stats(self) -> Dict[str, Any]:
        """Get user statistics.

        Returns:
            Dictionary with user statistics
        """
        active_users = sum(1 for user in self.users.values() if user.is_active)
        total_users = len(self.users)

        role_distribution = {}
        for user in self.users.values():
            for role in user.roles:
                role_distribution[role] = role_distribution.get(role, 0) + 1

        return {
            'total_users': total_users,
            'active_users': active_users,
            'inactive_users': total_users - active_users,
            'role_distribution': role_distribution
        }


# Global authentication service instance
auth_service = AuthenticationService()
