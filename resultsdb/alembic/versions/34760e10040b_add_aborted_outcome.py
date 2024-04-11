"""Add ABORTED outcome

Revision ID: 34760e10040b
Revises: 4ace44a44bf
Create Date: 2015-04-21 14:01:41.374105

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "34760e10040b"
down_revision = "4ace44a44bf"
branch_labels = None
depends_on = None

old_values = ("PASSED", "INFO", "FAILED", "ERROR", "WAIVED", "NEEDS_INSPECTION")
new_values = (
    "PASSED",
    "INFO",
    "FAILED",
    "ERROR",
    "WAIVED",
    "NEEDS_INSPECTION",
    "ABORTED",
)

old_enum = sa.Enum(*old_values, name="resultoutcome")
tmp_enum = sa.Enum(*new_values, name="resultoutcome_tmp")
new_enum = sa.Enum(*new_values, name="resultoutcome")


def upgrade():
    # this migration is postgresql specific and fails on sqlite
    if op.get_bind().engine.url.drivername.startswith("postgresql"):
        tmp_enum.create(op.get_bind(), checkfirst=False)
        op.execute(
            text(
                "ALTER TABLE result ALTER COLUMN outcome TYPE resultoutcome_tmp "
                " USING outcome::text::resultoutcome_tmp"
            )
        )
        old_enum.drop(op.get_bind(), checkfirst=False)
        new_enum.create(op.get_bind(), checkfirst=False)
        op.execute(
            text(
                "ALTER TABLE result ALTER COLUMN outcome TYPE resultoutcome "
                " USING outcome::text::resultoutcome"
            )
        )
        tmp_enum.drop(op.get_bind(), checkfirst=False)


def downgrade():
    # this migration is postgresql specific and fails on sqlite
    if op.get_bind().engine.url.drivername.startswith("postgresql"):
        op.execute(text("UPDATE result SET outcome='ERROR' WHERE outcome='ABORTED'"))

        tmp_enum.create(op.get_bind(), checkfirst=False)
        op.execute(
            text(
                "ALTER TABLE result ALTER COLUMN outcome TYPE resultoutcome_tmp "
                " USING outcome::text::resultoutcome_tmp"
            )
        )
        new_enum.drop(op.get_bind(), checkfirst=False)
        old_enum.create(op.get_bind(), checkfirst=False)
        op.execute(
            text(
                "ALTER TABLE result ALTER COLUMN outcome TYPE resultoutcome "
                " USING outcome::text::resultoutcome"
            )
        )
        tmp_enum.drop(op.get_bind(), checkfirst=False)
