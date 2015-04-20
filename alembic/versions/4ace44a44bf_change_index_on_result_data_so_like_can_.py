"""Change index on result_data so LIKE can use it

Revision ID: 4ace44a44bf
Revises: 153c416322c2
Create Date: 2015-04-14 17:20:32.575195

"""

# revision identifiers, used by Alembic.
revision = '4ace44a44bf'
down_revision = '153c416322c2'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_index('result_data_idx_key_value', 'result_data', ['key', 'value'], unique=False,
            postgresql_ops={'value': 'text_pattern_ops', 'key': 'text_pattern_ops'})
    op.drop_index('rd_key_value_idx', table_name='result_data')
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_index('rd_key_value_idx', 'result_data', ['key', 'value'], unique=False)
    op.drop_index('result_data_idx_key_value', table_name='result_data')
    ### end Alembic commands ###
