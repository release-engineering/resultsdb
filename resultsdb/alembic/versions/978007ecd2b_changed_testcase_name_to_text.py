"""Changed testcase.name to text

Revision ID: 978007ecd2b
Revises: 4bf1390f06d1
Create Date: 2016-02-18 21:41:04.273020

"""

# revision identifiers, used by Alembic.
revision = "978007ecd2b"
down_revision = "4bf1390f06d1"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.alter_column("testcase", "name", type_=sa.Text)
    op.create_index(
        "testcase_idx_name",
        "testcase",
        ["name"],
        unique=False,
        postgresql_ops={"name": "text_pattern_ops"},
    )
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.alter_column("testcase", "name", type_=sa.String(255))
    op.drop_index("testcase_idx_name", table_name="testcase")
    ### end Alembic commands ###
