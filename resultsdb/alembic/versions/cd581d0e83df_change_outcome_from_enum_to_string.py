"""Change outcome from enum to string.

Revision ID: cd581d0e83df
Revises: 4dbe714897fe
Create Date: 2018-03-28 20:47:27.338605

"""

# revision identifiers, used by Alembic.
revision = 'cd581d0e83df'
down_revision = '4dbe714897fe'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute(
        "ALTER TABLE result "
        "ALTER COLUMN outcome "
        "TYPE VARCHAR(32)")


def downgrade():
    op.execute(
        "ALTER TABLE result "
        "ALTER COLUMN outcome "
        "TYPE resultoutcome USING outcome::resultoutcome")
