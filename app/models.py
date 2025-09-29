from __future__ import annotations

import datetime
from typing import List, Optional

from passlib.context import CryptContext
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeMeta, declarative_base, relationship

Base: DeclarativeMeta = declarative_base()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), unique=True, nullable=False)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=True)
    cash = Column(Integer, default=0)
    # relation to players
    players = relationship("Player", back_populates="team")
    aliases = relationship("TeamAlias", back_populates="team")
    league = relationship("League", back_populates="teams")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Team id={self.id} name={self.name} cash={self.cash}>"


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True)
    name = Column(String(256), nullable=False)
    role = Column(String(64), nullable=True)
    # new fields mirroring legacy DB
    costo = Column(Integer, nullable=True)
    anni_contratto = Column(Integer, nullable=True)
    opzione = Column(String(8), nullable=True)
    squadra_reale = Column(String(128), nullable=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    is_injured = Column(Boolean, default=False)

    team = relationship("Team", back_populates="players")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Player id={self.id} name={self.name} team_id={self.team_id}>"


class League(Base):
    __tablename__ = "leagues"

    id = Column(Integer, primary_key=True)
    slug = Column(String(64), unique=True, nullable=False)
    name = Column(String(128), nullable=False)

    teams = relationship("Team", back_populates="league")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<League id={self.id} slug={self.slug} name={self.name}>"


class TeamAlias(Base):
    __tablename__ = "team_aliases"

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    alias = Column(String(256), nullable=False, index=True)

    team = relationship("Team", back_populates="aliases")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<TeamAlias id={self.id} alias={self.alias} team_id={self.team_id}>"


class ImportAudit(Base):
    __tablename__ = "import_audit"

    id = Column(Integer, primary_key=True)
    filename = Column(String(256), nullable=True)
    user = Column(String(128), nullable=True)
    inserted = Column(Integer, default=0)
    updated = Column(Integer, default=0)
    aliases_created = Column(Integer, default=0)
    success = Column(Boolean, default=True)
    message = Column(String(1024), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<ImportAudit id={self.id} file={self.filename} user={self.user} success={self.success}>"


class CanonicalMapping(Base):
    __tablename__ = "canonical_mappings"

    id = Column(Integer, primary_key=True)
    variant = Column(String(256), nullable=False, unique=True, index=True)
    canonical = Column(String(256), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<CanonicalMapping id={self.id} variant={self.variant} canonical={self.canonical}>"


# ==========================
# AUTHENTICATION & RBAC MODELS
# ==========================

class User(Base):
    """User model with authentication and role-based access control."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(128), unique=True, nullable=False, index=True)
    email = Column(String(256), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(256), nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    failed_login_attempts = Column(Integer, default=0)
    last_login_attempt = Column(DateTime, nullable=True)
    account_locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan",
                        foreign_keys="UserRole.user_id")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<User id={self.id} username={self.username} email={self.email}>"

    def set_password(self, password: str) -> None:
        """Hash and set the user's password."""
        self.hashed_password = pwd_context.hash(password)

    def verify_password(self, password: str) -> bool:
        """Verify a password against the stored hash."""
        return pwd_context.verify(password, self.hashed_password)

    def is_account_locked(self) -> bool:
        """Check if account is currently locked due to failed login attempts."""
        if self.account_locked_until is None:
            return False
        return datetime.datetime.utcnow() < self.account_locked_until

    def lock_account(self, duration_minutes: int = 30) -> None:
        """Lock account for specified duration."""
        self.account_locked_until = datetime.datetime.utcnow() + datetime.timedelta(minutes=duration_minutes)

    def unlock_account(self) -> None:
        """Unlock account and reset failed attempts."""
        self.account_locked_until = None
        self.failed_login_attempts = 0

    def has_role(self, role_name: str) -> bool:
        """Check if user has a specific role."""
        try:
            return any(user_role.role.name == role_name for user_role in self.roles)
        except Exception:
            # If the instance is detached or relationships cannot be loaded,
            # be conservative and return False rather than raising.
            return False

    def has_permission(self, permission_name: str) -> bool:
        """Check if user has a specific permission through their roles."""
        try:
            for user_role in self.roles:
                if user_role.role.has_permission(permission_name):
                    return True
            return False
        except Exception:
            # If relationships cannot be traversed (detached instance),
            # return False to avoid propagating SQLAlchemy errors into views.
            return False


class Role(Base):
    """Role model for RBAC system."""
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    users = relationship("UserRole", back_populates="role")
    permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Role id={self.id} name={self.name}>"

    def has_permission(self, permission_name: str) -> bool:
        """Check if role has a specific permission."""
        try:
            return any(role_perm.permission.name == permission_name for role_perm in self.permissions)
        except Exception:
            # Be defensive in case this Role instance is detached.
            return False


class Permission(Base):
    """Permission model for granular access control."""
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    resource = Column(String(128), nullable=False)  # e.g., "team", "player", "market"
    action = Column(String(64), nullable=False)     # e.g., "read", "write", "delete", "admin"

    # Relationships
    roles = relationship("RolePermission", back_populates="permission")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Permission id={self.id} name={self.name} resource={self.resource} action={self.action}>"


class UserRole(Base):
    """Association table for User-Role many-to-many relationship."""
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    assigned_at = Column(DateTime, default=datetime.datetime.utcnow)
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships - specify foreign_keys to resolve ambiguity
    user = relationship("User", back_populates="roles", foreign_keys=[user_id])
    role = relationship("Role", back_populates="users")
    assigned_by_user = relationship("User", foreign_keys=[assigned_by])

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<UserRole user_id={self.user_id} role_id={self.role_id}>"


class RolePermission(Base):
    """Association table for Role-Permission many-to-many relationship."""
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    permission_id = Column(Integer, ForeignKey("permissions.id"), nullable=False)

    # Relationships
    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission", back_populates="roles")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<RolePermission role_id={self.role_id} permission_id={self.permission_id}>"


class UserSession(Base):
    """User session tracking for JWT token management."""
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_token = Column(String(512), unique=True, nullable=False, index=True)
    refresh_token = Column(String(512), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    refresh_expires_at = Column(DateTime, nullable=False)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_used_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="sessions")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<UserSession id={self.id} user_id={self.user_id} active={self.is_active}>"

    def is_expired(self) -> bool:
        """Check if session is expired."""
        return datetime.datetime.utcnow() > self.expires_at

    def is_refresh_expired(self) -> bool:
        """Check if refresh token is expired."""
        return datetime.datetime.utcnow() > self.refresh_expires_at


class AuditLog(Base):
    """Audit logging for security-sensitive operations."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(128), nullable=False)
    resource_type = Column(String(128), nullable=True)
    resource_id = Column(String(128), nullable=True)
    details = Column(Text, nullable=True)  # JSON string for structured data
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    success = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="audit_logs")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<AuditLog id={self.id} user_id={self.user_id} action={self.action} success={self.success}>"
