"""Migration script template used by alembic when generating revisions.
This is a minimal template sufficient for autogenerate to write migration files.
"""

"""baseline
Revision ID: 581f0f59e94d
Revises: None
Create Date: 2025-09-16 19:28:33.137523
"""

# revision identifiers, used by Alembic.
revision = "581f0f59e94d"
down_revision = None
branch_labels = None
depends_on = None

"""Baseline migration (no-op).

This migration is intentionally a no-op baseline. We generated an autogenerate
revision to capture the current DB state, but we do not want to perform any DDL
that would drop or recreate existing tables at this stage.

To mark the current database as matching this revision, either run:
    alembic stamp head
or, if you prefer to apply this migration file, run:
    alembic upgrade head

Edit this file later if you need to create conversion steps from the legacy
`giocatori`/`fantateam` schema to the new ORM tables.
"""



# revision identifiers, used by Alembic (kept from generated file)
# revision = '581f0f59e94d'
# down_revision = None


def upgrade():
    """No-op baseline upgrade.

    This intentionally does nothing so the database is not modified. Use
    `alembic stamp head` to mark the DB as at this revision without running
    migrations, or keep this file as the baseline for future migrations.
    """
    pass


def downgrade():
    """No-op downgrade for baseline."""
    pass
