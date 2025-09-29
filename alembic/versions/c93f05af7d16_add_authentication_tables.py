"""add_authentication_tables

Revision ID: c93f05af7d16
Revises: a12e098a2903
Create Date: 2025-09-25 11:01:04.646209

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c93f05af7d16'
down_revision = 'a12e098a2903'
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
    """Add authentication and authorization tables."""

    # Users table
    if not table_exists('users'):
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('username', sa.String(128), nullable=False),
            sa.Column('email', sa.String(256), nullable=False),
            sa.Column('hashed_password', sa.String(255), nullable=False),
            sa.Column('full_name', sa.String(256), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text("TRUE")),
            sa.Column('is_verified', sa.Boolean(), nullable=True, server_default=sa.text("FALSE")),
            sa.Column('failed_login_attempts', sa.Integer(), nullable=True, server_default=sa.text("0")),
            sa.Column('last_login_attempt', sa.DateTime(), nullable=True),
            sa.Column('account_locked_until', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('username'),
            sa.UniqueConstraint('email')
        )

    # Roles table
    if not table_exists('roles'):
        op.create_table(
            'roles',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(128), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text("TRUE")),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
        )

    # Permissions table
    if not table_exists('permissions'):
        op.create_table(
            'permissions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(128), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('resource', sa.String(128), nullable=False),
            sa.Column('action', sa.String(64), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name'),
            sa.Index('idx_permissions_resource_action', 'resource', 'action')
        )

    # User roles junction table
    if not table_exists('user_roles'):
        op.create_table(
            'user_roles',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('role_id', sa.Integer(), nullable=False),
            sa.Column('assigned_at', sa.DateTime(), nullable=True),
            sa.Column('assigned_by', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['assigned_by'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'role_id', name='uq_user_role')
        )

    # Role permissions junction table
    if not table_exists('role_permissions'):
        op.create_table(
            'role_permissions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('role_id', sa.Integer(), nullable=False),
            sa.Column('permission_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('role_id', 'permission_id', name='uq_role_permission')
        )

    # User sessions table
    if not table_exists('user_sessions'):
        op.create_table(
            'user_sessions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('session_token', sa.String(512), nullable=False),
            sa.Column('refresh_token', sa.String(512), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('refresh_expires_at', sa.DateTime(), nullable=False),
            sa.Column('ip_address', sa.String(45), nullable=True),
            sa.Column('user_agent', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text("TRUE")),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('last_used_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('session_token'),
            sa.UniqueConstraint('refresh_token')
        )

    # Audit logs table
    if not table_exists('audit_logs'):
        op.create_table(
            'audit_logs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('action', sa.String(128), nullable=False),
            sa.Column('resource_type', sa.String(128), nullable=True),
            sa.Column('resource_id', sa.String(128), nullable=True),
            sa.Column('details', sa.Text(), nullable=True),
            sa.Column('ip_address', sa.String(45), nullable=True),
            sa.Column('user_agent', sa.Text(), nullable=True),
            sa.Column('success', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id')
        )


def downgrade():
    """Remove authentication and authorization tables."""

    # Drop tables in reverse order due to foreign key constraints
    op.drop_table('audit_logs')
    op.drop_table('user_sessions')
    op.drop_table('role_permissions')
    op.drop_table('user_roles')
    op.drop_table('permissions')
    op.drop_table('roles')
    op.drop_table('users')
