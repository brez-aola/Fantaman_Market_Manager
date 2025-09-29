"""create orm tables

Revision ID: 0002_create_orm_tables
Revises: 581f0f59e94d
Create Date: 2025-09-16
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_create_orm_tables"
down_revision = "581f0f59e94d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False, unique=True),
        sa.Column("cash", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column(
            "is_injured", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")
        ),
    )


def downgrade():
    op.drop_table("players")
    op.drop_table("teams")
