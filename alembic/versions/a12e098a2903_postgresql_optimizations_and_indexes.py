"""PostgreSQL optimizations and indexes

Revision ID: a12e098a2903
Revises: 42684144b034
Create Date: 2025-09-25 10:35:37.427718

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a12e098a2903'
down_revision = '42684144b034'
branch_labels = None
depends_on = None


def table_exists(tablename):
    """Check if a table exists in the database."""
    conn = op.get_bind()
    if conn.dialect.name == 'postgresql':
        res = conn.execute(
            sa.text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename=:t"),
            {"t": tablename},
        ).fetchone()
    else:  # SQLite
        res = conn.execute(
            sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
            {"t": tablename},
        ).fetchone()
    return bool(res)


def upgrade():
    """Add PostgreSQL-specific optimizations and indexes."""

    # Check if we're using PostgreSQL before applying optimizations
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':

        # Add indexes for better query performance, but only if tables exist

        # Users table indexes
        if table_exists('users'):
            op.create_index('idx_users_username', 'users', ['username'])
            op.create_index('idx_users_email', 'users', ['email'])
            op.create_index('idx_users_is_active', 'users', ['is_active'])
            op.create_index('idx_users_created_at', 'users', ['created_at'])

        # Players table indexes
        if table_exists('players'):
            op.create_index('idx_players_name', 'players', ['name'])
            op.create_index('idx_players_role', 'players', ['role'])
            op.create_index('idx_players_team_id', 'players', ['team_id'])
            op.create_index('idx_players_costo', 'players', ['costo'])
            op.create_index('idx_players_squadra_reale', 'players', ['squadra_reale'])

        # Teams table indexes
        if table_exists('teams'):
            op.create_index('idx_teams_name', 'teams', ['name'])
            op.create_index('idx_teams_league_id', 'teams', ['league_id'])
            op.create_index('idx_teams_cash', 'teams', ['cash'])

        # User sessions table indexes (for authentication performance)
        if table_exists('user_sessions'):
            op.create_index('idx_user_sessions_user_id', 'user_sessions', ['user_id'])
            op.create_index('idx_user_sessions_session_token', 'user_sessions', ['session_token'])
            op.create_index('idx_user_sessions_refresh_token', 'user_sessions', ['refresh_token'])
            op.create_index('idx_user_sessions_is_active', 'user_sessions', ['is_active'])
            op.create_index('idx_user_sessions_expires_at', 'user_sessions', ['expires_at'])

        # Audit logs table indexes (for security and compliance)
        if table_exists('audit_logs'):
            op.create_index('idx_audit_logs_user_id', 'audit_logs', ['user_id'])
            op.create_index('idx_audit_logs_action', 'audit_logs', ['action'])
            op.create_index('idx_audit_logs_created_at', 'audit_logs', ['created_at'])
            op.create_index('idx_audit_logs_success', 'audit_logs', ['success'])

        # Team aliases for fast lookups
        if table_exists('team_aliases'):
            op.create_index('idx_team_aliases_team_id', 'team_aliases', ['team_id'])
            op.create_index('idx_team_aliases_alias', 'team_aliases', ['alias'])

        # Canonical mappings for import performance
        if table_exists('canonical_mappings'):
            op.create_index('idx_canonical_mappings_variant', 'canonical_mappings', ['variant'])
            op.create_index('idx_canonical_mappings_canonical', 'canonical_mappings', ['canonical'])

        # Composite indexes for common queries
        if table_exists('players') and table_exists('teams'):
            op.create_index('idx_players_team_role', 'players', ['team_id', 'role'])
        if table_exists('user_sessions'):
            op.create_index('idx_user_sessions_user_active', 'user_sessions', ['user_id', 'is_active'])
        if table_exists('audit_logs'):
            op.create_index('idx_audit_logs_user_action', 'audit_logs', ['user_id', 'action'])
def downgrade():
    """Remove PostgreSQL-specific optimizations and indexes."""

    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':

        # Drop composite indexes
        op.drop_index('idx_audit_logs_user_action')
        op.drop_index('idx_user_sessions_user_active')
        op.drop_index('idx_players_team_role')

        # Drop canonical mappings indexes
        op.drop_index('idx_canonical_mappings_canonical')
        op.drop_index('idx_canonical_mappings_variant')

        # Drop team aliases indexes
        op.drop_index('idx_team_aliases_alias')
        op.drop_index('idx_team_aliases_team_id')

        # Drop audit logs indexes
        op.drop_index('idx_audit_logs_success')
        op.drop_index('idx_audit_logs_created_at')
        op.drop_index('idx_audit_logs_action')
        op.drop_index('idx_audit_logs_user_id')

        # Drop user sessions indexes
        op.drop_index('idx_user_sessions_expires_at')
        op.drop_index('idx_user_sessions_is_active')
        op.drop_index('idx_user_sessions_refresh_token')
        op.drop_index('idx_user_sessions_session_token')
        op.drop_index('idx_user_sessions_user_id')

        # Drop teams indexes
        op.drop_index('idx_teams_cash')
        op.drop_index('idx_teams_league_id')
        op.drop_index('idx_teams_name')

        # Drop players indexes
        op.drop_index('idx_players_squadra_reale')
        op.drop_index('idx_players_costo')
        op.drop_index('idx_players_team_id')
        op.drop_index('idx_players_role')
        op.drop_index('idx_players_name')

        # Drop users indexes
        op.drop_index('idx_users_created_at')
        op.drop_index('idx_users_is_active')
        op.drop_index('idx_users_email')
        op.drop_index('idx_users_username')
