"""Added UUID column to the Job table

Revision ID: 17ec41bd6e9a
Revises: 433d0b5b3b96
Create Date: 2015-02-23 17:45:57.085449

"""

# revision identifiers, used by Alembic.
revision = '17ec41bd6e9a'
down_revision = '433d0b5b3b96'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('job', sa.Column('uuid', sa.String(length=36), nullable=True))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('job', 'uuid')
    ### end Alembic commands ###