"""Migration script template used by alembic when generating revisions.
This is a minimal template sufficient for autogenerate to write migration files.
"""
<%!
from alembic import op
import sqlalchemy as sa
%>
"""${message}
Revision ID: ${up_revision}
Revises: ${down_revision if down_revision else 'None'}
Create Date: ${create_date}
"""

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision) if down_revision else None}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}

from alembic import op
import sqlalchemy as sa


def upgrade():
${upgrades if upgrades else '    pass'}


def downgrade():
${downgrades if downgrades else '    pass'}
