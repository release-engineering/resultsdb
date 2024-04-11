"""Remove the user model

Revision ID: 4dbe714897fe
Revises: dbfab576c81
Create Date: 2016-10-17 15:52:14.061320

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4dbe714897fe"
down_revision = "dbfab576c81"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("user")


def downgrade():
    op.create_table(
        "user",
        sa.Column("id", sa.INTEGER(), nullable=False),
        sa.Column("username", sa.VARCHAR(length=80), nullable=True),
        sa.Column("pw_hash", sa.VARCHAR(length=120), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
