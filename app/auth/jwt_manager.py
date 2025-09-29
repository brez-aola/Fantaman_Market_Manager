"""JWT Token Manager for secure authentication.

Handles JWT token generation, validation, and session management.
"""

import datetime
import secrets
from typing import Any, Dict, Optional

import jwt
from flask import current_app

from ..models import User, UserSession


class JWTManager:
    """JWT token management with refresh token support."""

    def __init__(self):
        self.algorithm = "HS256"

    @property
    def secret_key(self) -> str:
        """Get JWT secret key from app config."""
        return (
            current_app.config.get("JWT_SECRET_KEY") or current_app.config["SECRET_KEY"]
        )

    @property
    def access_token_expire_minutes(self) -> int:
        """Access token expiration time in minutes."""
        return current_app.config.get("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30)

    @property
    def refresh_token_expire_days(self) -> int:
        """Refresh token expiration time in days."""
        return current_app.config.get("JWT_REFRESH_TOKEN_EXPIRE_DAYS", 7)

    def generate_tokens(
        self,
        user: User,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate access and refresh tokens for a user."""
        now = datetime.datetime.utcnow()

        # Access token payload
        # Try to compute roles safely. If 'user' is an ORM instance and has a
        # relationship loaded, attempt to extract names; otherwise fallback to []
        roles_list = []
        try:
            # If SQLAlchemy instance, use attribute access guarded by getattr
            if hasattr(user, "roles"):
                roles_list = [
                    getattr(ur.role, "name", None)
                    for ur in getattr(user, "roles")
                    if getattr(ur, "role", None) is not None
                ]
                roles_list = [r for r in roles_list if r]
        except Exception:
            roles_list = []

        access_payload = {
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "roles": roles_list,
            "iat": now,
            "exp": now + datetime.timedelta(minutes=self.access_token_expire_minutes),
            "type": "access",
        }

        # Generate tokens
        access_token = jwt.encode(
            access_payload, self.secret_key, algorithm=self.algorithm
        )
        refresh_token = secrets.token_urlsafe(64)

        # Store session in database
        session = UserSession(
            user_id=user.id,
            session_token=access_token,
            refresh_token=refresh_token,
            expires_at=access_payload["exp"],
            refresh_expires_at=now
            + datetime.timedelta(days=self.refresh_token_expire_days),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self.access_token_expire_minutes * 60,
            "session": session,
        }

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify a JWT token and return payload if valid."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Check token type
            if payload.get("type") != "access":
                return None

            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def refresh_access_token(
        self, refresh_token: str, session_factory
    ) -> Optional[Dict[str, Any]]:
        """Generate new access token using refresh token."""
        session = session_factory()
        try:
            # Find active session with this refresh token
            user_session = (
                session.query(UserSession)
                .filter(
                    UserSession.refresh_token == refresh_token,
                    UserSession.is_active.is_(True),
                )
                .first()
            )

            if not user_session or user_session.is_refresh_expired():
                return None

            user = session.query(User).get(user_session.user_id)
            if not user or not user.is_active:
                return None

            # Generate new tokens
            tokens = self.generate_tokens(
                user, user_session.ip_address, user_session.user_agent
            )

            # Deactivate old session
            user_session.is_active = False

            # Add new session
            session.add(tokens["session"])
            session.commit()

            return tokens

        except Exception as e:
            session.rollback()
            current_app.logger.error(f"Token refresh failed: {e}")
            return None
        finally:
            session.close()

    def revoke_token(self, token: str, session_factory) -> bool:
        """Revoke a specific token by deactivating its session."""
        session = session_factory()
        try:
            user_session = (
                session.query(UserSession)
                .filter(
                    UserSession.session_token == token, UserSession.is_active.is_(True)
                )
                .first()
            )

            if user_session:
                user_session.is_active = False
                session.commit()
                return True

            return False

        except Exception as e:
            session.rollback()
            current_app.logger.error(f"Token revocation failed: {e}")
            return False
        finally:
            session.close()

    def revoke_user_sessions(self, user_id: int, session_factory) -> bool:
        """Revoke all active sessions for a user."""
        session = session_factory()
        try:
            sessions = (
                session.query(UserSession)
                .filter(UserSession.user_id == user_id, UserSession.is_active.is_(True))
                .all()
            )

            for user_session in sessions:
                user_session.is_active = False

            session.commit()
            return True

        except Exception as e:
            session.rollback()
            current_app.logger.error(f"User sessions revocation failed: {e}")
            return False
        finally:
            session.close()

    def cleanup_expired_sessions(self, session_factory) -> int:
        """Remove expired sessions from database. Returns count of cleaned sessions."""
        session = session_factory()
        try:
            now = datetime.datetime.utcnow()

            # Find expired sessions
            expired_sessions = (
                session.query(UserSession)
                .filter(UserSession.refresh_expires_at < now)
                .all()
            )

            count = len(expired_sessions)

            # Delete expired sessions
            for user_session in expired_sessions:
                session.delete(user_session)

            session.commit()
            return count

        except Exception as e:
            session.rollback()
            current_app.logger.error(f"Session cleanup failed: {e}")
            return 0
        finally:
            session.close()
