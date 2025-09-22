"""add canonical_mappings and import_audit tables

Revision ID: 0005_add_canonical_and_audit
Revises: 0004_add_leagues_and_aliases
Create Date: 2025-09-20 13:40:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0005_add_canonical_and_audit"
down_revision = "0004_add_leagues_and_aliases"
branch_labels = None
depends_on = None


def table_exists(tablename):
    conn = op.get_bind()
    res = conn.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
        {"t": tablename},
    ).fetchone()
    return bool(res)


def upgrade():
    # canonical_mappings
    if not table_exists("canonical_mappings"):
        op.create_table(
            "canonical_mappings",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "variant", sa.String(256), nullable=False, unique=True, index=True
            ),
            sa.Column("canonical", sa.String(256), nullable=False),
        )

    # import_audit
    if not table_exists("import_audit"):
        op.create_table(
            "import_audit",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("filename", sa.String(256), nullable=True),
            sa.Column("user", sa.String(128), nullable=True),
            sa.Column("inserted", sa.Integer, default=0),
            sa.Column("updated", sa.Integer, default=0),
            sa.Column("aliases_created", sa.Integer, default=0),
            sa.Column("success", sa.Boolean, default=True),
            sa.Column("message", sa.String(1024), nullable=True),
        )


def downgrade():
    if table_exists("import_audit"):
        op.drop_table("import_audit")
    if table_exists("canonical_mappings"):
        op.drop_table("canonical_mappings")
