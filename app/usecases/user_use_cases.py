"""User-specific use cases for managing user operations."""

from typing import List, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.entities import UserEntity
from app.domain.value_objects import Email, Username


# DTOs for User operations
@dataclass
class UserDTO:
    """Data Transfer Object for User information."""
    id: Optional[int]
    username: str
    email: str
    is_active: bool

    @classmethod
    def from_entity(cls, user: UserEntity) -> 'UserDTO':
        """Create DTO from domain entity."""
        return cls(
            id=user.id,
            username=user.username.value,
            email=user.email.value,
            is_active=user.is_active
        )


@dataclass
class CreateUserRequest:
    """Request to create a new user."""
    username: str
    email: str
    password: str


@dataclass
class UpdateUserRequest:
    """Request to update user information."""
    user_id: int
    username: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None


@dataclass
class LoginRequest:
    """Request for user login."""
    username: str
    password: str


@dataclass
class LoginResult:
    """Result of login attempt."""
    user: Optional[UserDTO]
    success: bool
    message: str


@dataclass
class ListUsersRequest:
    """Request to list users."""
    active_only: bool = True
    limit: int = 50
    offset: int = 0


@dataclass
class ListUsersResult:
    """Result of listing users."""
    users: List[UserDTO]
    total_count: int
    has_more: bool


# Repository interface
class UserRepositoryInterface(ABC):
    """Interface for User repository operations."""

    @abstractmethod
    def get_by_id(self, user_id: int) -> Optional[UserEntity]:
        """Get user by ID."""
        pass

    @abstractmethod
    def get_by_username(self, username: Username) -> Optional[UserEntity]:
        """Get user by username."""
        pass

    @abstractmethod
    def get_by_email(self, email: Email) -> Optional[UserEntity]:
        """Get user by email."""
        pass

    @abstractmethod
    def create(self, user: UserEntity) -> UserEntity:
        """Create new user."""
        pass

    @abstractmethod
    def update(self, user: UserEntity) -> UserEntity:
        """Update existing user."""
        pass

    @abstractmethod
    def delete(self, user_id: int) -> bool:
        """Delete user by ID."""
        pass

    @abstractmethod
    def get_all(self, active_only: bool = True, limit: int = 50, offset: int = 0) -> List[UserEntity]:
        """Get all users with pagination."""
        pass

    @abstractmethod
    def authenticate(self, username: str, password: str) -> Optional[UserEntity]:
        """Authenticate user with username/password."""
        pass


# Use Cases
class CreateUserUseCase:
    """Use case for creating a new user."""

    def __init__(self, user_repository: UserRepositoryInterface):
        self.user_repository = user_repository

    def execute(self, request: CreateUserRequest) -> UserDTO:
        """Create a new user."""
        # Create domain entity
        user = UserEntity(
            username=Username(request.username),
            email=Email(request.email),
            password_hash=""  # Will be set by repository
        )

        # Validate user doesn't already exist
        existing_username = self.user_repository.get_by_username(user.username)
        if existing_username:
            raise ValueError(f"Username '{request.username}' already exists")

        existing_email = self.user_repository.get_by_email(user.email)
        if existing_email:
            raise ValueError(f"Email '{request.email}' already exists")

        # Save user (repository handles password hashing)
        created_user = self.user_repository.create(user)

        return UserDTO.from_entity(created_user)


class GetUserUseCase:
    """Use case for retrieving user information."""

    def __init__(self, user_repository: UserRepositoryInterface):
        self.user_repository = user_repository

    def execute(self, user_id: int) -> Optional[UserDTO]:
        """Get user by ID."""
        user = self.user_repository.get_by_id(user_id)
        return UserDTO.from_entity(user) if user else None


class GetUserByUsernameUseCase:
    """Use case for retrieving user by username."""

    def __init__(self, user_repository: UserRepositoryInterface):
        self.user_repository = user_repository

    def execute(self, username: str) -> Optional[UserDTO]:
        """Get user by username."""
        user = self.user_repository.get_by_username(Username(username))
        return UserDTO.from_entity(user) if user else None


class ListUsersUseCase:
    """Use case for listing users."""

    def __init__(self, user_repository: UserRepositoryInterface):
        self.user_repository = user_repository

    def execute(self, request: ListUsersRequest) -> ListUsersResult:
        """List users based on criteria."""
        users = self.user_repository.get_all(
            active_only=request.active_only,
            limit=request.limit,
            offset=request.offset
        )

        # Convert to DTOs
        user_dtos = [UserDTO.from_entity(user) for user in users]

        return ListUsersResult(
            users=user_dtos,
            total_count=len(user_dtos),
            has_more=len(user_dtos) == request.limit
        )


class UpdateUserUseCase:
    """Use case for updating user information."""

    def __init__(self, user_repository: UserRepositoryInterface):
        self.user_repository = user_repository

    def execute(self, request: UpdateUserRequest) -> UserDTO:
        """Update user information."""
        user = self.user_repository.get_by_id(request.user_id)
        if not user:
            raise ValueError(f"User with ID {request.user_id} not found")

        # Update fields if provided
        if request.username:
            # Check if username is already taken by another user
            existing = self.user_repository.get_by_username(Username(request.username))
            if existing and existing.id != user.id:
                raise ValueError(f"Username '{request.username}' already exists")
            user.username = Username(request.username)

        if request.email:
            # Check if email is already taken by another user
            existing = self.user_repository.get_by_email(Email(request.email))
            if existing and existing.id != user.id:
                raise ValueError(f"Email '{request.email}' already exists")
            user.email = Email(request.email)

        if request.is_active is not None:
            user.is_active = request.is_active

        # Save updated user
        updated_user = self.user_repository.update(user)

        return UserDTO.from_entity(updated_user)


class LoginUserUseCase:
    """Use case for user authentication."""

    def __init__(self, user_repository: UserRepositoryInterface):
        self.user_repository = user_repository

    def execute(self, request: LoginRequest) -> LoginResult:
        """Authenticate user login."""
        try:
            # Attempt authentication
            user = self.user_repository.authenticate(request.username, request.password)

            if user:
                if not user.is_active:
                    return LoginResult(
                        user=None,
                        success=False,
                        message="Account is disabled"
                    )

                return LoginResult(
                    user=UserDTO.from_entity(user),
                    success=True,
                    message="Login successful"
                )
            else:
                return LoginResult(
                    user=None,
                    success=False,
                    message="Invalid username or password"
                )

        except Exception as e:
            return LoginResult(
                user=None,
                success=False,
                message=f"Login failed: {str(e)}"
            )


class DeactivateUserUseCase:
    """Use case for deactivating a user."""

    def __init__(self, user_repository: UserRepositoryInterface):
        self.user_repository = user_repository

    def execute(self, user_id: int) -> UserDTO:
        """Deactivate user account."""
        user = self.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError(f"User with ID {user_id} not found")

        user.is_active = False
        updated_user = self.user_repository.update(user)

        return UserDTO.from_entity(updated_user)


class ActivateUserUseCase:
    """Use case for activating a user."""

    def __init__(self, user_repository: UserRepositoryInterface):
        self.user_repository = user_repository

    def execute(self, user_id: int) -> UserDTO:
        """Activate user account."""
        user = self.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError(f"User with ID {user_id} not found")

        user.is_active = True
        updated_user = self.user_repository.update(user)

        return UserDTO.from_entity(updated_user)
