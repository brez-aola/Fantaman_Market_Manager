"""User repository implementation.

Handles all database operations for User model including authentication
and authorization related queries.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.models import Role, RolePermission, User, UserRole

from .base import BaseRepository

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository[User]):
    """Repository for User model with authentication features."""

    def __init__(self, db_session: Session):
        """Initialize user repository.

        Args:
            db_session: SQLAlchemy database session
        """
        super().__init__(db_session, User)

    def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username.

        Args:
            username: Username to search for

        Returns:
            User instance if found, None otherwise
        """
        return self.db.query(User).filter(User.username == username).first()

    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email.

        Args:
            email: Email to search for

        Returns:
            User instance if found, None otherwise
        """
        return self.db.query(User).filter(User.email == email).first()

    def get_by_username_or_email(self, identifier: str) -> Optional[User]:
        """Get user by username or email.

        Args:
            identifier: Username or email to search for

        Returns:
            User instance if found, None otherwise
        """
        return (
            self.db.query(User)
            .filter(or_(User.username == identifier, User.email == identifier))
            .first()
        )

    def get_with_roles(self, user_id: int) -> Optional[User]:
        """Get user with roles eagerly loaded.

        Args:
            user_id: User ID

        Returns:
            User instance with roles loaded, None if not found
        """
        return (
            self.db.query(User)
            .options(joinedload(User.roles))
            .filter(User.id == user_id)
            .first()
        )

    def get_with_permissions(self, user_id: int) -> Optional[User]:
        """Get user with all permissions loaded.

        Args:
            user_id: User ID

        Returns:
            User with permissions loaded or None
        """
        try:
            user = (
                self.db.query(User)
                .options(
                    joinedload(User.roles)
                    .joinedload(UserRole.role)
                    .joinedload(Role.permissions)
                    .joinedload(RolePermission.permission)
                )
                .filter(User.id == user_id)
                .first()
            )

            if user:
                logger.info(f"Found user {user.username} with {len(user.roles)} roles")

            return user
        except Exception as e:
            logger.error(f"Error getting user with permissions: {e}")
            return None

    def get_active_users(self) -> List[User]:
        """Get all active users.

        Returns:
            List of active users
        """
        return self.db.query(User).filter(User.is_active.is_(True)).all()

    def get_users_by_role(self, role_name: str) -> List[User]:
        """Get users by role name.

        Args:
            role_name: Name of the role

        Returns:
            List of users with the specified role
        """
        return self.db.query(User).join(User.roles).filter(Role.name == role_name).all()

    def create_user(
        self,
        username: str,
        email: str,
        hashed_password: str,
        full_name: str = None,
        is_active: bool = True,
        is_verified: bool = False,
    ) -> User:
        """Create a new user.

        Args:
            username: Username
            email: Email address
            hashed_password: Hashed password
            full_name: Full name (optional)
            is_active: Whether user is active
            is_verified: Whether user is verified

        Returns:
            Created user instance
        """
        return self.create(
            username=username,
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            is_active=is_active,
            is_verified=is_verified,
            created_at=datetime.utcnow(),
        )

    def update_last_login(self, user_id: int) -> bool:
        """Update user's last login timestamp.

        Args:
            user_id: User ID

        Returns:
            True if updated, False if user not found
        """
        user = self.get_by_id(user_id)
        if not user:
            return False

        user.last_login_attempt = datetime.utcnow()
        user.failed_login_attempts = 0  # Reset failed attempts on successful login
        self.db.commit()
        return True

    def increment_failed_login(self, user_id: int) -> bool:
        """Increment failed login attempts counter.

        Args:
            user_id: User ID

        Returns:
            True if updated, False if user not found
        """
        user = self.get_by_id(user_id)
        if not user:
            return False

        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        user.last_login_attempt = datetime.utcnow()

        # Lock account if too many failed attempts (e.g., 5)
        if user.failed_login_attempts >= 5:
            user.account_locked_until = datetime.utcnow() + timedelta(minutes=30)
            logger.warning(
                f"Account locked for user {user.username} due to failed login attempts"
            )

        self.db.commit()
        return True

    def unlock_account(self, user_id: int) -> bool:
        """Unlock user account.

        Args:
            user_id: User ID

        Returns:
            True if unlocked, False if user not found
        """
        user = self.get_by_id(user_id)
        if not user:
            return False

        user.account_locked_until = None
        user.failed_login_attempts = 0
        self.db.commit()
        logger.info(f"Account unlocked for user {user.username}")
        return True

    def is_account_locked(self, user_id: int) -> bool:
        """Check if user account is locked.

        Args:
            user_id: User ID

        Returns:
            True if account is locked, False otherwise
        """
        user = self.get_by_id(user_id)
        if not user:
            return False

        if user.account_locked_until and user.account_locked_until > datetime.utcnow():
            return True

        # Auto-unlock expired locks
        if user.account_locked_until and user.account_locked_until <= datetime.utcnow():
            self.unlock_account(user_id)

        return False

    def assign_role(self, user_id: int, role_id: int, assigned_by: int = None) -> bool:
        """Assign role to user.

        Args:
            user_id: User ID
            role_id: Role ID
            assigned_by: ID of user who assigned the role

        Returns:
            True if assigned, False if user not found
        """
        from app.models import UserRole

        user = self.get_by_id(user_id)
        if not user:
            return False

        # Check if role already assigned
        existing = (
            self.db.query(UserRole)
            .filter(and_(UserRole.user_id == user_id, UserRole.role_id == role_id))
            .first()
        )

        if existing:
            return True  # Already assigned

        user_role = UserRole(
            user_id=user_id,
            role_id=role_id,
            assigned_by=assigned_by,
            assigned_at=datetime.utcnow(),
        )
        self.db.add(user_role)
        self.db.commit()
        logger.info(f"Assigned role {role_id} to user {user_id}")
        return True

    def remove_role(self, user_id: int, role_id: int) -> bool:
        """Remove role from user.

        Args:
            user_id: User ID
            role_id: Role ID

        Returns:
            True if removed, False if not found
        """
        from app.models import UserRole

        user_role = (
            self.db.query(UserRole)
            .filter(and_(UserRole.user_id == user_id, UserRole.role_id == role_id))
            .first()
        )

        if not user_role:
            return False

        self.db.delete(user_role)
        self.db.commit()
        logger.info(f"Removed role {role_id} from user {user_id}")
        return True

    def search_users(
        self, search_term: str, skip: int = 0, limit: int = 20
    ) -> List[User]:
        """Search users by username, email, or full name.

        Args:
            search_term: Search term
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of users matching search term
        """
        return (
            self.db.query(User)
            .filter(
                or_(
                    User.username.ilike(f"%{search_term}%"),
                    User.email.ilike(f"%{search_term}%"),
                    User.full_name.ilike(f"%{search_term}%"),
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )
