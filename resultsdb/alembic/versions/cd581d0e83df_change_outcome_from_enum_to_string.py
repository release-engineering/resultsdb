"""Change outcome from enum to string.

Revision ID: cd581d0e83df
Revises: 4dbe714897fe
Create Date: 2018-03-28 20:47:27.338605

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "cd581d0e83df"
down_revision = "4dbe714897fe"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("result", "outcome", type_=sa.String(32))
    op.create_index(
        "result_idx_outcome",
        "result",
        ["outcome"],
        unique=False,
        postgresql_ops={"outcome": "text_pattern_ops"},
    )


def downgrade():
    op.execute(
        text(
            "ALTER TABLE result ALTER COLUMN outcome TYPE resultoutcome USING outcome::resultoutcome;"
        )
    )
    op.drop_index("result_idx_outcome", table_name="result")
