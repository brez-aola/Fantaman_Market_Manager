"""Authentication and authorization service.

Handles user authentication, session management, and authorization logic.
"""

from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import hashlib
import secrets
import bcrypt
import logging

from app.repositories import UserRepository
from app.models import User

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication and authorization service."""

    def __init__(self, user_repo: UserRepository):
        """Initialize auth service.

        Args:
            user_repo: User repository instance
        """
        self.user_repo = user_repo

    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt.

        Args:
            password: Plain text password

        Returns:
            Hashed password
        """
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify a password against its hash.

        Args:
            password: Plain text password
            hashed_password: Hashed password to verify against

        Returns:
            True if password matches, False otherwise
        """
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False

    def authenticate_user(self, identifier: str, password: str) -> Tuple[Optional[User], str]:
        """Authenticate a user by username/email and password.

        Args:
            identifier: Username or email
            password: Plain text password

        Returns:
            Tuple of (User instance if authenticated, error message)
        """
        # Get user by username or email
        user = self.user_repo.get_by_username_or_email(identifier)
        if not user:
            return None, "Invalid username or email"

        # Check if account is locked
        if self.user_repo.is_account_locked(user.id):
            return None, "Account is temporarily locked due to failed login attempts"

        # Check if user is active
        if not user.is_active:
            return None, "Account is deactivated"

        # Verify password
        if not self.verify_password(password, user.hashed_password):
            # Increment failed login attempts
            self.user_repo.increment_failed_login(user.id)
            failed_attempts = (user.failed_login_attempts or 0) + 1

            if failed_attempts >= 5:
                return None, "Too many failed login attempts. Account has been temporarily locked."
            else:
                remaining = 5 - failed_attempts
                return None, f"Invalid password. {remaining} attempts remaining."

        # Successful authentication
        self.user_repo.update_last_login(user.id)
        logger.info(f"User {user.username} authenticated successfully")

        return user, ""

    def register_user(self, username: str, email: str, password: str,
                     full_name: str = None) -> Tuple[Optional[User], str]:
        """Register a new user.

        Args:
            username: Username
            email: Email address
            password: Plain text password
            full_name: Full name (optional)

        Returns:
            Tuple of (User instance if created, error message)
        """
        # Check if username already exists
        if self.user_repo.get_by_username(username):
            return None, "Username already exists"

        # Check if email already exists
        if self.user_repo.get_by_email(email):
            return None, "Email already exists"

        # Validate password strength
        if len(password) < 8:
            return None, "Password must be at least 8 characters long"

        # Hash password
        hashed_password = self.hash_password(password)

        try:
            # Create user
            user = self.user_repo.create_user(
                username=username,
                email=email,
                hashed_password=hashed_password,
                full_name=full_name,
                is_active=True,
                is_verified=False
            )

            logger.info(f"New user registered: {username} ({email})")
            return user, ""

        except Exception as e:
            logger.error(f"User registration failed: {e}")
            return None, "Registration failed due to database error"

    def change_password(self, user_id: int, current_password: str,
                       new_password: str) -> Tuple[bool, str]:
        """Change user password.

        Args:
            user_id: User ID
            current_password: Current password
            new_password: New password

        Returns:
            Tuple of (success boolean, error message)
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return False, "User not found"

        # Verify current password
        if not self.verify_password(current_password, user.hashed_password):
            return False, "Current password is incorrect"

        # Validate new password
        if len(new_password) < 8:
            return False, "New password must be at least 8 characters long"

        # Hash new password
        hashed_password = self.hash_password(new_password)

        # Update password
        success = self.user_repo.update(user_id, hashed_password=hashed_password)
        if success:
            logger.info(f"Password changed for user {user.username}")
            return True, ""
        else:
            return False, "Password update failed"

    def reset_password(self, email: str) -> Tuple[bool, str]:
        """Initiate password reset for user.

        Args:
            email: User email

        Returns:
            Tuple of (success boolean, message)
        """
        user = self.user_repo.get_by_email(email)
        if not user:
            # Don't reveal if email exists for security
            return True, "If the email exists, a reset link has been sent"

        # Generate temporary password
        temp_password = secrets.token_urlsafe(12)
        hashed_password = self.hash_password(temp_password)

        # Update password
        success = self.user_repo.update(user.id, hashed_password=hashed_password)
        if success:
            # In a real application, you would send this via email
            logger.info(f"Password reset for user {user.username}. Temp password: {temp_password}")
            return True, f"Password reset successful. Temporary password: {temp_password}"
        else:
            return False, "Password reset failed"

    def get_user_permissions(self, user_id: int) -> list:
        """Get all permissions for a user.

        Args:
            user_id: User ID

        Returns:
            List of permission names
        """
        user = self.user_repo.get_with_permissions(user_id)
        if not user:
            return []

        permissions = set()
        for user_role in user.roles:
            role = user_role.role
            for role_permission in role.permissions:
                permission = role_permission.permission
                permissions.add(permission.name)

        return list(permissions)

    def has_permission(self, user_id: int, permission_name: str) -> bool:
        """Check if user has a specific permission.

        Args:
            user_id: User ID
            permission_name: Permission name to check

        Returns:
            True if user has permission, False otherwise
        """
        permissions = self.get_user_permissions(user_id)
        return permission_name in permissions

    def has_role(self, user_id: int, role_name: str) -> bool:
        """Check if user has a specific role.

        Args:
            user_id: User ID
            role_name: Role name to check

        Returns:
            True if user has role, False otherwise
        """
        user = self.user_repo.get_with_roles(user_id)
        if not user:
            return False

        for user_role in user.roles:
            if user_role.role.name == role_name:
                return True

        return False

    def is_admin(self, user_id: int) -> bool:
        """Check if user is an admin.

        Args:
            user_id: User ID

        Returns:
            True if user is admin, False otherwise
        """
        return self.has_role(user_id, 'super_admin') or self.has_role(user_id, 'admin')

    def assign_role(self, user_id: int, role_name: str, assigned_by: int = None) -> bool:
        """Assign role to user by role name.

        Args:
            user_id: User ID
            role_name: Role name
            assigned_by: ID of user assigning the role

        Returns:
            True if assigned, False otherwise
        """
        # Get role by name
        from app.models import Role
        role = self.user_repo.db.query(Role).filter(Role.name == role_name).first()
        if not role:
            logger.error(f"Role '{role_name}' not found")
            return False

        success = self.user_repo.assign_role(user_id, role.id, assigned_by)
        if success:
            logger.info(f"Assigned role '{role_name}' to user {user_id}")

        return success

    def remove_role(self, user_id: int, role_name: str) -> bool:
        """Remove role from user by role name.

        Args:
            user_id: User ID
            role_name: Role name

        Returns:
            True if removed, False otherwise
        """
        # Get role by name
        from app.models import Role
        role = self.user_repo.db.query(Role).filter(Role.name == role_name).first()
        if not role:
            logger.error(f"Role '{role_name}' not found")
            return False

        success = self.user_repo.remove_role(user_id, role.id)
        if success:
            logger.info(f"Removed role '{role_name}' from user {user_id}")

        return success
