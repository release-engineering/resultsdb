"""Change schema to v2.0 - step 1 - prepare columns

Revision ID: 59bef5afc9aa
Revises: 978007ecd2b
Create Date: 2016-08-23 20:10:05.734728

"""

# revision identifiers, used by Alembic.
revision = '540dbe71fa91'
down_revision = '978007ecd2b'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    # JOB
    op.rename_table('job', 'group')
    op.alter_column('group', 'name', new_column_name='description')
    op.drop_column(u'group', 'status')
    op.drop_column(u'group', 'start_time')
    op.drop_column(u'group', 'end_time')
    op.create_unique_constraint(None, 'group', ['uuid'])
    op.create_index(
        'group_idx_uuid', 'group', ['uuid'], unique=False, postgresql_ops={'uuid': 'text_pattern_ops'})

    # RESULT
    op.add_column(u'result', sa.Column('testcase_name', sa.Text(), nullable=True))
    op.alter_column('result', 'summary', new_column_name='note')
    op.alter_column('result', 'log_url', new_column_name='ref_url')
    op.create_index('result_fk_testcase_name', 'result', [
                    'testcase_name'], unique=False, postgresql_ops={'testcase_name': 'text_pattern_ops'})
    op.drop_index('result_fk_job_id', table_name='result')
    op.drop_index('result_fk_testcase_id', table_name='result')
    op.drop_constraint(u'result_testcase_id_fkey', 'result', type_='foreignkey')
    op.drop_constraint(u'result_job_id_fkey', 'result', type_='foreignkey')
    op.create_foreign_key(None, 'result', 'testcase', ['testcase_name'], ['name'])

    # TESTCASE
    op.alter_column('testcase', 'url', new_column_name='ref_url')

    # MANY TO MANY
    op.create_table('groups_to_results',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('group_uuid', sa.String(36), nullable=True),
                    sa.Column('result_id', sa.Integer(), nullable=True),
                    sa.ForeignKeyConstraint(['group_uuid'], ['group.uuid'], ),
                    sa.ForeignKeyConstraint(['result_id'], ['result.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_index('gtr_fk_group_uuid', 'groups_to_results', [
                    'group_uuid'], unique=False, postgresql_ops={'uuid': 'text_pattern_ops'})
    op.create_index('gtr_fk_result_id', 'groups_to_results', ['result_id'], unique=False)


def downgrade():
    # TESTCASE
    op.alter_column('testcase', 'ref_url', new_column_name='url')

    # RESULT
    op.alter_column('result', 'note', new_column_name='summary')
    op.alter_column('result', 'ref_url', new_column_name='log_url')
    op.drop_constraint('result_testcase_name_fkey', 'result', type_='foreignkey')
    op.create_index('result_fk_testcase_id', 'result', ['testcase_id'], unique=False)
    op.create_index('result_fk_job_id', 'result', ['job_id'], unique=False)
    op.drop_index('result_fk_testcase_name', table_name='result')
    op.drop_column(u'result', 'testcase_name')

    # JOB
    op.rename_table('group', 'job')
    op.alter_column('job', 'description', new_column_name='name')
    op.add_column(u'job', sa.Column('end_time', sa.DateTime(), nullable=True))
    op.add_column(u'job', sa.Column('start_time', sa.DateTime(), nullable=True))
    op.add_column(u'job', sa.Column('status', sa.VARCHAR(length=16), nullable=True))
    op.drop_index('group_idx_uuid', table_name='job')

    # MANY TO MANY
    op.drop_index('gtr_fk_result_id', table_name='groups_to_results')
    op.drop_index('gtr_fk_group_uuid', table_name='groups_to_results')
    op.drop_table('groups_to_results')

    # CONSTRAINTS
    op.create_foreign_key(None, 'result', 'job', ['job_id'], ['id'])
    op.create_foreign_key(None, 'result', 'testcase', ['testcase_id'], ['id'])
    op.drop_constraint('group_uuid_key', 'job')
