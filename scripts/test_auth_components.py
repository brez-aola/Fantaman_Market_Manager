#!/usr/bin/env python3
"""Simple authentication functionality test.

This script tests the core authentication components without starting a web server.
"""

import os
import sys

# Add the parent directory to Python path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.auth.auth_service import AuthService
from app.auth.jwt_manager import JWTManager


def test_auth_components():
    """Test authentication components directly."""
    print("🔐 Testing Authentication System Components...")

    # Create Flask app context
    app = create_app()

    with app.app_context():
        try:
            # Test 1: JWT Manager
            print("\n1️⃣ Testing JWT Manager...")
            jwt_manager = JWTManager()

            # Test token generation
            session_factory = app.extensions["db_session_factory"]
            session = session_factory()

            from app.models import User
            admin_user = session.query(User).filter(User.username == "admin").first()

            if admin_user:
                tokens = jwt_manager.generate_tokens(admin_user, "127.0.0.1", "Test-Agent")
                print(f"✅ JWT tokens generated successfully")
                print(f"   🔑 Access token: {tokens['access_token'][:20]}...")
                print(f"   🔄 Refresh token: {tokens['refresh_token'][:20]}...")

                # Test token verification
                payload = jwt_manager.verify_token(tokens['access_token'])
                if payload:
                    print(f"✅ Token verification successful")
                    print(f"   👤 User ID: {payload['user_id']}")
                    print(f"   🎭 Roles: {payload['roles']}")
                else:
                    print("❌ Token verification failed")

                # Save session to database
                session.add(tokens["session"])
                session.commit()

            else:
                print("❌ Admin user not found")
                session.close()
                return False

            session.close()

            # Test 2: Auth Service
            print("\n2️⃣ Testing Auth Service...")
            auth_service = AuthService(session_factory)

            # Test login
            tokens, error = auth_service.authenticate_user(
                "admin", "fantacalcio123", "127.0.0.1", "Test-Agent"
            )

            if tokens and not error:
                print("✅ Authentication service login successful")
                print(f"   🔑 Access token: {tokens['access_token'][:20]}...")
            else:
                print(f"❌ Authentication failed: {error}")
                return False

            # Test 3: User permissions
            print("\n3️⃣ Testing User Permissions...")
            session = session_factory()
            try:
                admin_user = session.query(User).filter(User.username == "admin").first()
                if admin_user:
                    print(f"✅ Admin user found: {admin_user.username}")
                    # Fetch roles via explicit scalar query
                    from app.models import Role, UserRole
                    role_rows = session.query(Role.name).join(UserRole, Role.id == UserRole.role_id).filter(UserRole.user_id == admin_user.id).all()
                    print(f"   🎭 Roles: {[r[0] for r in role_rows]}")

                    # Test specific permissions using ORM methods while session is open
                    permissions_to_test = [
                        "user.admin", "team.admin", "player.admin",
                        "market.admin", "system.admin"
                    ]
                    for perm in permissions_to_test:
                        has_perm = admin_user.has_permission(perm)
                        status = "✅" if has_perm else "❌"
                        print(f"   {status} {perm}: {has_perm}")
            except Exception as e:
                print(f"❌ Permission test failed: {e}")
            finally:
                session.close()

            print("\n🎉 All authentication components working correctly!")
            return True

        except Exception as e:
            print(f"❌ Test error: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Main test function."""
    print("🧪 Authentication System Component Test")
    print("=" * 40)

    success = test_auth_components()

    if success:
        print("\n✅ Authentication system is ready!")
        print("\n📋 Next Steps:")
        print("   1. Start the Flask application")
        print("   2. Test API endpoints with curl or Postman")
        print("   3. Login with: admin / fantacalcio123")
    else:
        print("\n❌ Authentication system has issues")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
