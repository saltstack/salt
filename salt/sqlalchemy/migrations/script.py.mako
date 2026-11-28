"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
"""

import sqlalchemy as sa
from alembic import context, op

${imports if imports else ""}
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade():
    ${upgrades if upgrades else "pass"}


def downgrade():
    ${downgrades if downgrades else "pass"}
