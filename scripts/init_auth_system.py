#!/usr/bin/env python3
"""Test script for authentication system initialization.

This script creates all database tables and initializes the authentication system
with default roles, permissions, and admin user.
"""

import os
import sys

# Add the parent directory to Python path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app


def main():
    """Initialize the authentication system."""
    print("🔐 Initializing Authentication System...")

    # Create Flask app
    app = create_app()

    with app.app_context():
        try:
            # Create all database tables
            print("📊 Creating database tables...")
            app.init_db()
            print("✅ Database tables created successfully")

            # Initialize authentication system
            print("🔑 Initializing authentication system...")
            success = app.init_auth(
                admin_username="admin",
                admin_email="admin@fantacalcio.local",
                admin_password="fantacalcio123"
            )

            if success:
                print("✅ Authentication system initialized successfully!")
                print("\n📋 System Summary:")
                print("   👤 Admin User: admin")
                print("   📧 Admin Email: admin@fantacalcio.local")
                print("   🔑 Admin Password: fantacalcio123")
                print("\n🎭 Available Roles:")
                print("   • super_admin - Full system access")
                print("   • admin - Management access")
                print("   • team_manager - Team and player management")
                print("   • read_only - Read-only access")
                print("\n🚀 You can now start the application!")
            else:
                print("❌ Authentication system initialization failed")
                return 1

        except Exception as e:
            print(f"❌ Error during initialization: {e}")
            import traceback
            traceback.print_exc()
            return 1

    return 0


if __name__ == "__main__":
    exit(main())
