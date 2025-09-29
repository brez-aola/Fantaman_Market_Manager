#!/usr/bin/env python3
"""Debug script for authentication decorator issues.

This script tests the JWT token validation and database access
to identify where the 500 error is occurring.
"""

import os
import sys

# Add the parent directory to Python path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.auth.jwt_manager import JWTManager


def debug_jwt_token():
    """Debug JWT token validation process."""
    print("🔍 Debugging JWT Token Validation...")

    # Sample token from our previous test
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxLCJ1c2VybmFtZSI6ImFkbWluIiwiZW1haWwiOiJhZG1pbkBmYW50YWNhbGNpby5sb2NhbCIsInJvbGVzIjpbInN1cGVyX2FkbWluIl0sImlhdCI6MTc1ODY0MjY5MCwiZXhwIjoxNzU4NjQ0NDkwLCJ0eXBlIjoiYWNjZXNzIn0.-oUuGU__AtkKdA5XDB0iE6Z2wumLJfIkrJRHzSubeJM"

    # Create Flask app context
    app = create_app()

    with app.app_context():
        try:
            # Test 1: JWT verification
            print("\n1️⃣ Testing JWT verification...")
            jwt_manager = JWTManager()
            payload = jwt_manager.verify_token(token)

            if payload:
                print("✅ JWT token is valid")
                print(f"   👤 User ID: {payload['user_id']}")
                print(f"   📧 Email: {payload['email']}")
                print(f"   🎭 Roles: {payload['roles']}")
            else:
                print("❌ JWT token is invalid or expired")
                return False

            # Test 2: Database session access
            print("\n2️⃣ Testing database session access...")
            Session = app.extensions["db_session_factory"]
            session = Session()

            try:
                from app.models import User, UserSession

                # Test user query
                user = session.query(User).get(payload["user_id"])
                if user:
                    print(f"✅ User found: {user.username}")
                    print(f"   📧 Email: {user.email}")
                    print(f"   🔋 Active: {user.is_active}")
                else:
                    print("❌ User not found in database")
                    return False

                # Test session query
                user_session = session.query(UserSession).filter(
                    UserSession.session_token == token,
                    UserSession.is_active == True
                ).first()

                if user_session:
                    print(f"✅ User session found: ID {user_session.id}")
                    print(f"   ⏱️ Expires at: {user_session.expires_at}")
                    print(f"   🔄 Is expired: {user_session.is_expired()}")
                else:
                    print("❌ User session not found or inactive")
                    return False

            except Exception as e:
                print(f"❌ Database query error: {e}")
                import traceback
                traceback.print_exc()
                return False
            finally:
                session.close()

            # Test 3: Role and permission access
            print("\n3️⃣ Testing role and permission access...")
            session = Session()
            try:
                user = session.query(User).get(payload["user_id"])

                # Print roles using a scalar query to avoid lazy-loading after session close
                from app.models import Role, UserRole
                role_rows = session.query(Role.name).join(UserRole, Role.id == UserRole.role_id).filter(UserRole.user_id == user.id).all()
                print(f"   🎭 User roles: {[r[0] for r in role_rows]}")
                print(f"   🔐 Has super_admin role: {user.has_role('super_admin')}")
                print(f"   🔐 Has user.admin permission: {user.has_permission('user.admin')}")

            except Exception as e:
                print(f"❌ Role/permission access error: {e}")
                import traceback
                traceback.print_exc()
                return False
            finally:
                session.close()

            print("\n✅ All JWT and database operations successful!")
            print("🤔 The issue might be in the decorator implementation or Flask context.")
            return True

        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Main debug function."""
    print("🐛 Authentication Decorator Debug Tool")
    print("=" * 45)

    success = debug_jwt_token()

    if success:
        print("\n💡 JWT validation works correctly outside Flask request context.")
        print("🔍 The 500 error is likely in the decorator's Flask integration.")
        print("\n🛠️ Suggested fixes:")
        print("   1. Check Flask g object access")
        print("   2. Verify session.commit() timing")
        print("   3. Review exception handling in decorator")
    else:
        print("\n❌ Found issues in JWT validation or database access")

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
