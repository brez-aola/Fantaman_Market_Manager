"""add player fields

Revision ID: 0003_add_player_fields
Revises: 0002_create_orm_tables
Create Date: 2025-09-17
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0003_add_player_fields'
down_revision = '0002_create_orm_tables'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('players', sa.Column('costo', sa.Integer(), nullable=True))
    op.add_column('players', sa.Column('anni_contratto', sa.Integer(), nullable=True))
    op.add_column('players', sa.Column('opzione', sa.String(length=8), nullable=True))
    op.add_column('players', sa.Column('squadra_reale', sa.String(length=128), nullable=True))


def downgrade():
    op.drop_column('players', 'squadra_reale')
    op.drop_column('players', 'opzione')
    op.drop_column('players', 'anni_contratto')
    op.drop_column('players', 'costo')
