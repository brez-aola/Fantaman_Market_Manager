"""Authentication service for user management and security operations.

Handles user registration, login, password management, and security features
like account lockout and audit logging.
"""

import datetime
import json
import logging
from typing import Dict, List, Optional, Tuple

from flask import request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import AuditLog, Permission, Role, RolePermission, User, UserRole, UserSession
from sqlalchemy.orm import joinedload
from .jwt_manager import JWTManager

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication and user management service."""

    def __init__(self, session_factory, jwt_manager: Optional[JWTManager] = None):
        self.session_factory = session_factory
        self.jwt_manager = jwt_manager or JWTManager()

    def create_user(self, username: str, email: str, password: str,
                   full_name: Optional[str] = None,
                   is_active: bool = True,
                   created_by: Optional[int] = None) -> Tuple[Optional[User], Optional[str]]:
        """Create a new user. Returns (user, error_msg)."""
        session = self.session_factory()
        try:
            # Check if username or email already exists
            existing = session.query(User).filter(
                (User.username == username) | (User.email == email)
            ).first()

            if existing:
                if existing.username == username:
                    return None, "Username already exists"
                return None, "Email already exists"

            # Create user
            user = User(
                username=username,
                email=email,
                full_name=full_name,
                is_active=is_active
            )
            user.set_password(password)

            session.add(user)
            session.commit()

            # Log user creation
            self._log_audit(
                session,
                created_by,
                "user_created",
                "user",
                str(user.id),
                {"username": username, "email": email}
            )

            return user, None

        except IntegrityError as e:
            session.rollback()
            logger.error(f"User creation failed with integrity error: {e}")
            return None, "User creation failed due to data constraints"
        except Exception as e:
            session.rollback()
            logger.error(f"User creation failed: {e}")
            return None, f"User creation failed: {str(e)}"
        finally:
            session.close()

    def authenticate_user(self, username_or_email: str, password: str,
                         ip_address: Optional[str] = None,
                         user_agent: Optional[str] = None) -> Tuple[Optional[Dict], Optional[str]]:
        """Authenticate user and return tokens. Returns (tokens_dict, error_msg)."""
        session = self.session_factory()
        try:
            # Find user by username or email
            user = session.query(User).filter(
                (User.username == username_or_email) | (User.email == username_or_email)
            ).first()

            if not user:
                self._log_audit(
                    session,
                    None,
                    "login_failed",
                    "user",
                    None,
                    {"reason": "user_not_found", "identifier": username_or_email},
                    success=False,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                return None, "Invalid credentials"

            # Check if account is locked
            if user.is_account_locked():
                self._log_audit(
                    session,
                    user.id,
                    "login_failed",
                    "user",
                    str(user.id),
                    {"reason": "account_locked"},
                    success=False,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                return None, "Account is temporarily locked due to too many failed attempts"

            # Check if user is active
            if not user.is_active:
                self._log_audit(
                    session,
                    user.id,
                    "login_failed",
                    "user",
                    str(user.id),
                    {"reason": "account_inactive"},
                    success=False,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                return None, "Account is inactive"

            # Verify password
            if not user.verify_password(password):
                # Increment failed attempts
                user.failed_login_attempts += 1
                user.last_login_attempt = datetime.datetime.utcnow()

                # Lock account after 5 failed attempts
                if user.failed_login_attempts >= 5:
                    user.lock_account(30)  # 30 minutes

                session.commit()

                self._log_audit(
                    session,
                    user.id,
                    "login_failed",
                    "user",
                    str(user.id),
                    {"reason": "invalid_password", "attempts": user.failed_login_attempts},
                    success=False,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                return None, "Invalid credentials"

            # Reset failed attempts on successful login
            user.failed_login_attempts = 0
            user.last_login_attempt = datetime.datetime.utcnow()
            user.account_locked_until = None

            # Generate tokens
            tokens = self.jwt_manager.generate_tokens(user, ip_address, user_agent)

            # Save session
            session.add(tokens["session"])
            session.commit()

            # Log successful login
            self._log_audit(
                session,
                user.id,
                "login_success",
                "user",
                str(user.id),
                {"session_id": tokens["session"].id},
                ip_address=ip_address,
                user_agent=user_agent
            )

            # Remove session object from return (it's already persisted)
            tokens.pop("session")

            return tokens, None

        except Exception as e:
            session.rollback()
            logger.error(f"Authentication failed: {e}")
            return None, "Authentication failed"
        finally:
            session.close()

    def logout_user(self, token: str, user_id: Optional[int] = None) -> bool:
        """Logout user by revoking their token."""
        session = self.session_factory()
        try:
            success = self.jwt_manager.revoke_token(token, self.session_factory)

            if success and user_id:
                self._log_audit(
                    session,
                    user_id,
                    "logout",
                    "user",
                    str(user_id),
                    {"token_revoked": True}
                )

            return success

        except Exception as e:
            logger.error(f"Logout failed: {e}")
            return False
        finally:
            session.close()

    def change_password(self, user_id: int, current_password: str,
                       new_password: str) -> Tuple[bool, Optional[str]]:
        """Change user password. Returns (success, error_msg)."""
        session = self.session_factory()
        try:
            user = session.query(User).get(user_id)
            if not user:
                return False, "User not found"

            # Verify current password
            if not user.verify_password(current_password):
                self._log_audit(
                    session,
                    user_id,
                    "password_change_failed",
                    "user",
                    str(user_id),
                    {"reason": "invalid_current_password"},
                    success=False
                )
                return False, "Current password is incorrect"

            # Set new password
            user.set_password(new_password)
            user.updated_at = datetime.datetime.utcnow()

            session.commit()

            # Revoke all user sessions to force re-login
            self.jwt_manager.revoke_user_sessions(user_id, self.session_factory)

            self._log_audit(
                session,
                user_id,
                "password_changed",
                "user",
                str(user_id),
                {"sessions_revoked": True}
            )

            return True, None

        except Exception as e:
            session.rollback()
            logger.error(f"Password change failed: {e}")
            return False, "Password change failed"
        finally:
            session.close()

    def assign_role(self, user_id: int, role_name: str,
                   assigned_by: Optional[int] = None) -> Tuple[bool, Optional[str]]:
        """Assign a role to a user. Returns (success, error_msg)."""
        session = self.session_factory()
        try:
            user = session.query(User).get(user_id)
            if not user:
                return False, "User not found"

            role = session.query(Role).filter(Role.name == role_name).first()
            if not role:
                return False, f"Role '{role_name}' not found"

            # Check if user already has this role
            existing = session.query(UserRole).filter(
                UserRole.user_id == user_id,
                UserRole.role_id == role.id
            ).first()

            if existing:
                return False, f"User already has role '{role_name}'"

            # Assign role
            user_role = UserRole(
                user_id=user_id,
                role_id=role.id,
                assigned_by=assigned_by
            )

            session.add(user_role)
            session.commit()

            self._log_audit(
                session,
                assigned_by,
                "role_assigned",
                "user",
                str(user_id),
                {"role": role_name, "assigned_to": user.username}
            )

            return True, None

        except Exception as e:
            session.rollback()
            logger.error(f"Role assignment failed: {e}")
            return False, "Role assignment failed"
        finally:
            session.close()

    def remove_role(self, user_id: int, role_name: str,
                   removed_by: Optional[int] = None) -> Tuple[bool, Optional[str]]:
        """Remove a role from a user. Returns (success, error_msg)."""
        session = self.session_factory()
        try:
            user = session.query(User).get(user_id)
            if not user:
                return False, "User not found"

            role = session.query(Role).filter(Role.name == role_name).first()
            if not role:
                return False, f"Role '{role_name}' not found"

            # Find user role assignment
            user_role = session.query(UserRole).filter(
                UserRole.user_id == user_id,
                UserRole.role_id == role.id
            ).first()

            if not user_role:
                return False, f"User does not have role '{role_name}'"

            session.delete(user_role)
            session.commit()

            self._log_audit(
                session,
                removed_by,
                "role_removed",
                "user",
                str(user_id),
                {"role": role_name, "removed_from": user.username}
            )

            return True, None

        except Exception as e:
            session.rollback()
            logger.error(f"Role removal failed: {e}")
            return False, "Role removal failed"
        finally:
            session.close()

    def list_users(self, page: int = 1, per_page: int = 20,
                  search: Optional[str] = None) -> Tuple[List[User], int]:
        """List users with pagination and search. Returns (users, total_count)."""
        session = self.session_factory()
        try:
            query = session.query(User)

            if search:
                search_pattern = f"%{search}%"
                query = query.filter(
                    (User.username.ilike(search_pattern)) |
                    (User.email.ilike(search_pattern)) |
                    (User.full_name.ilike(search_pattern))
                )

            total = query.count()

            # Query scalar user fields to avoid returning ORM instances
            user_rows = session.query(
                User.id,
                User.username,
                User.email,
                User.full_name,
                User.is_active,
                User.is_verified,
                User.created_at
            ).offset((page - 1) * per_page).limit(per_page).all()

            # user_rows are tuples/KeyedTuples; use index access to avoid attribute lookups
            user_ids = [r[0] for r in user_rows]

            # Fetch roles for these users in one query
            roles_map = {uid: [] for uid in user_ids}
            if user_ids:
                role_rows = session.query(UserRole.user_id, Role.name).join(Role, UserRole.role_id == Role.id).filter(
                    UserRole.user_id.in_(user_ids)
                ).all()

                for ur in role_rows:
                    # ur is a tuple (user_id, role_name)
                    uid = ur[0]
                    rname = ur[1]
                    roles_map.setdefault(uid, []).append(rname)

            user_dicts = []
            for r in user_rows:
                user_dicts.append({
                    "id": r[0],
                    "username": r[1],
                    "email": r[2],
                    "full_name": r[3],
                    "is_active": r[4],
                    "is_verified": r[5],
                    "created_at": r[6].isoformat() if r[6] else None,
                    "roles": roles_map.get(r[0], [])
                })

            return user_dicts, total

        except Exception as e:
            import traceback
            logger.error(f"User listing failed: {e}")
            logger.error(traceback.format_exc())
            return [], 0
        finally:
            logger.debug("Closing session")
            session.close()

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        session = self.session_factory()
        try:
            user = session.query(User).get(user_id)
            if not user:
                return None
            # Prefer scalar query to build roles list to avoid lazy loading issues
            roles = []
            try:
                role_rows = session.query(Role.name).join(UserRole, Role.id == UserRole.role_id).filter(UserRole.user_id == user.id).all()
                roles = [r[0] for r in role_rows]
            except Exception:
                roles = []

            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "roles": roles
            }
        except Exception as e:
            logger.error(f"Get user failed: {e}")
            return None
        finally:
            session.close()

    def _log_audit(self, session: Session, user_id: Optional[int], action: str,
                   resource_type: Optional[str] = None, resource_id: Optional[str] = None,
                   details: Optional[Dict] = None, success: bool = True,
                   ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Log an audit event."""
        try:
            # Get IP and user agent from request if not provided
            if ip_address is None and request:
                ip_address = request.remote_addr
            if user_agent is None and request:
                user_agent = request.headers.get("User-Agent")

            audit_log = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=json.dumps(details) if details else None,
                ip_address=ip_address,
                user_agent=user_agent,
                success=success
            )

            session.add(audit_log)
            # Note: Don't commit here, let the caller handle the transaction

        except Exception as e:
            logger.error(f"Audit logging failed: {e}")
            # Don't let audit failures break the main operation
