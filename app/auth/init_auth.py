"""Database initialization commands for authentication system.

Provides commands to initialize roles, permissions, and create initial admin user.
"""

import logging
from typing import Dict, List

from sqlalchemy.exc import IntegrityError

from ..models import Permission, Role, RolePermission, User, UserRole

logger = logging.getLogger(__name__)


class AuthInitializer:
    """Initialize authentication system with default roles and permissions."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def initialize_permissions(self) -> bool:
        """Create default permissions."""
        session = self.session_factory()
        try:
            permissions = [
                # User management
                ("user.read", "Read user information", "user", "read"),
                ("user.write", "Create and update users", "user", "write"),
                ("user.delete", "Delete users", "user", "delete"),
                ("user.admin", "Full user administration", "user", "admin"),

                # Team management
                ("team.read", "Read team information", "team", "read"),
                ("team.write", "Create and update teams", "team", "write"),
                ("team.delete", "Delete teams", "team", "delete"),
                ("team.admin", "Full team administration", "team", "admin"),

                # Player management
                ("player.read", "Read player information", "player", "read"),
                ("player.write", "Create and update players", "player", "write"),
                ("player.delete", "Delete players", "player", "delete"),
                ("player.admin", "Full player administration", "player", "admin"),

                # Market operations
                ("market.read", "View market information", "market", "read"),
                ("market.write", "Perform market operations", "market", "write"),
                ("market.admin", "Full market administration", "market", "admin"),

                # System administration
                ("system.read", "Read system information", "system", "read"),
                ("system.write", "Modify system settings", "system", "write"),
                ("system.admin", "Full system administration", "system", "admin"),

                # Audit logs
                ("audit.read", "Read audit logs", "audit", "read"),
                ("audit.admin", "Manage audit logs", "audit", "admin"),
            ]

            created_count = 0
            for name, description, resource, action in permissions:
                existing = session.query(Permission).filter(
                    Permission.name == name
                ).first()

                if not existing:
                    permission = Permission(
                        name=name,
                        description=description,
                        resource=resource,
                        action=action
                    )
                    session.add(permission)
                    created_count += 1

            session.commit()
            logger.info(f"Created {created_count} permissions")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to initialize permissions: {e}")
            return False
        finally:
            session.close()

    def initialize_roles(self) -> bool:
        """Create default roles with permissions."""
        session = self.session_factory()
        try:
            # Define roles and their permissions
            roles_config = {
                "super_admin": {
                    "description": "Super administrator with full system access",
                    "permissions": [
                        "user.admin", "team.admin", "player.admin",
                        "market.admin", "system.admin", "audit.admin"
                    ]
                },
                "admin": {
                    "description": "Administrator with management access",
                    "permissions": [
                        "user.read", "user.write", "team.admin", "player.admin",
                        "market.admin", "audit.read", "system.read"
                    ]
                },
                "team_manager": {
                    "description": "Team manager with team and player management",
                    "permissions": [
                        "team.read", "team.write", "player.read", "player.write",
                        "market.read", "market.write"
                    ]
                },
                "read_only": {
                    "description": "Read-only access to all resources",
                    "permissions": [
                        "user.read", "team.read", "player.read", "market.read"
                    ]
                }
            }

            created_count = 0
            for role_name, config in roles_config.items():
                # Create role if it doesn't exist
                role = session.query(Role).filter(Role.name == role_name).first()
                if not role:
                    role = Role(
                        name=role_name,
                        description=config["description"]
                    )
                    session.add(role)
                    session.flush()  # Get the ID
                    created_count += 1

                # Assign permissions to role
                for perm_name in config["permissions"]:
                    permission = session.query(Permission).filter(
                        Permission.name == perm_name
                    ).first()

                    if permission:
                        # Check if role already has this permission
                        existing_assignment = session.query(RolePermission).filter(
                            RolePermission.role_id == role.id,
                            RolePermission.permission_id == permission.id
                        ).first()

                        if not existing_assignment:
                            role_permission = RolePermission(
                                role_id=role.id,
                                permission_id=permission.id
                            )
                            session.add(role_permission)

            session.commit()
            logger.info(f"Created {created_count} roles")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to initialize roles: {e}")
            return False
        finally:
            session.close()

    def create_admin_user(self, username: str = "admin",
                         email: str = "admin@fantacalcio.local",
                         password: str = "admin123") -> bool:
        """Create initial admin user."""
        session = self.session_factory()
        try:
            # Check if admin user already exists
            existing_user = session.query(User).filter(
                (User.username == username) | (User.email == email)
            ).first()

            if existing_user:
                logger.info(f"Admin user already exists: {existing_user.username}")
                return True

            # Create admin user
            admin_user = User(
                username=username,
                email=email,
                full_name="System Administrator",
                is_active=True,
                is_verified=True
            )
            admin_user.set_password(password)

            session.add(admin_user)
            session.flush()  # Get the ID

            # Assign super_admin role
            super_admin_role = session.query(Role).filter(
                Role.name == "super_admin"
            ).first()

            if super_admin_role:
                user_role = UserRole(
                    user_id=admin_user.id,
                    role_id=super_admin_role.id
                )
                session.add(user_role)

            session.commit()
            logger.info(f"Created admin user: {username}")
            return True

        except IntegrityError as e:
            session.rollback()
            logger.error(f"Admin user creation failed due to constraint: {e}")
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create admin user: {e}")
            return False
        finally:
            session.close()

    def initialize_all(self, admin_username: str = "admin",
                      admin_email: str = "admin@fantacalcio.local",
                      admin_password: str = "admin123") -> bool:
        """Initialize complete authentication system."""
        logger.info("Initializing authentication system...")

        success = True

        # Initialize permissions
        if not self.initialize_permissions():
            success = False

        # Initialize roles
        if not self.initialize_roles():
            success = False

        # Create admin user
        if not self.create_admin_user(admin_username, admin_email, admin_password):
            success = False

        if success:
            logger.info("Authentication system initialized successfully")
        else:
            logger.error("Authentication system initialization failed")

        return success
