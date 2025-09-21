"""Add leagues and team_aliases tables and add league_id to teams

Revision ID: 0004_add_leagues_and_aliases
Revises: 0003_add_player_fields
Create Date: 2025-09-20 12:40:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0004_add_leagues_and_aliases'
down_revision = '0003_add_player_fields'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Create leagues table if it doesn't exist
    if 'leagues' not in inspector.get_table_names():
        op.create_table(
            'leagues',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('slug', sa.String(length=64), nullable=False, unique=True),
            sa.Column('name', sa.String(length=128), nullable=False),
        )

    # Add league_id to teams (nullable initially) using batch for SQLite if column missing
    team_cols = [c['name'] for c in inspector.get_columns('teams')]
    if 'league_id' not in team_cols:
        with op.batch_alter_table('teams', schema=None) as batch_op:
            batch_op.add_column(sa.Column('league_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key('fk_teams_league', 'leagues', ['league_id'], ['id'])

    # Create team_aliases table if missing
    if 'team_aliases' not in inspector.get_table_names():
        op.create_table(
            'team_aliases',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=False),
            sa.Column('alias', sa.String(length=256), nullable=False),
        )


def downgrade():
    op.drop_table('team_aliases')
    op.drop_constraint('fk_teams_league', 'teams', type_='foreignkey')
    op.drop_column('teams', 'league_id')
    op.drop_table('leagues')
