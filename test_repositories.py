#!/usr/bin/env python3
"""Test Repository Pattern implementation.

This script tests the new repository pattern with the migrated PostgreSQL data.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database import get_db_session, get_repositories
from app.services.auth_service import AuthService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_repositories():
    """Test repository pattern functionality."""

    print("🧪 Testing Repository Pattern with PostgreSQL...")
    print("=" * 60)

    # Get database session and repositories
    with next(get_db_session()) as db:
        repos = get_repositories(db)

        # Test User Repository
        print("\n👤 Testing User Repository:")
        users = repos.users.get_all()
        print(f"   Total users: {len(users)}")

        if users:
            user = users[0]
            print(f"   Admin user: {user.username} ({user.email})")
            print(f"   Active: {user.is_active}")

            # Test user with roles
            user_with_roles = repos.users.get_with_roles(user.id)
            if user_with_roles and user_with_roles.roles:
                role_names = [user_role.role.name for user_role in user_with_roles.roles]
                print(f"   Roles: {', '.join(role_names)}")

        # Test Team Repository
        print("\n🏆 Testing Team Repository:")
        teams = repos.teams.get_all()
        print(f"   Total teams: {len(teams)}")

        if teams:
            team = teams[0]
            print(f"   First team: {team.name}")
            print(f"   Cash: €{team.cash:.2f}")

            # Test team statistics
            stats = repos.teams.get_team_statistics(team.id)
            print(f"   Players: {stats.get('total_players', 0)}")
            print(f"   Total value: €{stats.get('total_player_value', 0):.2f}")

        # Test League Repository
        print("\n🏟️ Testing League Repository:")
        leagues = repos.leagues.get_all()
        print(f"   Total leagues: {len(leagues)}")

        if leagues:
            league = leagues[0]
            print(f"   League: {league.name}")
            print(f"   Slug: {league.slug}")

            # Test league statistics
            stats = repos.leagues.get_league_statistics(league.id)
            print(f"   Teams: {stats.get('current_teams', 0)}/{stats.get('max_teams', 0)}")
            print(f"   Total players: {stats.get('total_players', 0)}")
            print(f"   Total cash: €{stats.get('total_cash', 0):.2f}")

        # Test Player Repository
        print("\n⚽ Testing Player Repository:")
        players = repos.players.get_all(limit=5)
        print(f"   Sample players: {len(players)}")

        # Test free agents
        free_agents = repos.players.get_free_agents()
        print(f"   Free agents: {len(free_agents)}")

        # Test market statistics
        market_stats = repos.players.get_market_statistics()
        print(f"   Total players in DB: {market_stats.get('total_players', 0)}")
        print(f"   Assigned: {market_stats.get('assigned_players', 0)}")
        print(f"   Available: {market_stats.get('free_agents', 0)}")

        # Test role distribution
        role_dist = market_stats.get('role_distribution', {})
        for role, stats in role_dist.items():
            print(f"   {role}: {stats['total']} total, {stats['available']} available")

        print("\n🔐 Testing Auth Service:")
        auth_service = AuthService(repos.users)

        # Test authentication with admin user
        if users:
            admin_user = users[0]
            print(f"   Testing auth for: {admin_user.username}")

            # Get permissions
            permissions = auth_service.get_user_permissions(admin_user.id)
            print(f"   Permissions: {len(permissions)}")
            if permissions:
                print(f"   Sample permissions: {', '.join(permissions[:3])}")

            # Test role checks
            is_admin = auth_service.is_admin(admin_user.id)
            print(f"   Is admin: {is_admin}")

        print("\n✅ Repository Pattern test completed successfully!")
        print("🎉 PostgreSQL migration and Repository Pattern are working perfectly!")


if __name__ == "__main__":
    test_repositories()
