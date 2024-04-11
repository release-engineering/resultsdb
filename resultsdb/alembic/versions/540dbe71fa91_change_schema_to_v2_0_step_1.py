"""Change schema to v2.0 - step 1 - prepare columns

Revision ID: 59bef5afc9aa
Revises: 978007ecd2b
Create Date: 2016-08-23 20:10:05.734728

"""

import logging

import sqlalchemy as sa
from alembic import op
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.orm.decl_api import DeclarativeMeta
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = "540dbe71fa91"
down_revision = "978007ecd2b"
branch_labels = None
depends_on = None

Session = sessionmaker()
Base: DeclarativeMeta = declarative_base()


class Job(Base):
    __tablename__ = "job"

    id = sa.Column(sa.Integer, primary_key=True)
    uuid = sa.Column(sa.String(36), unique=True)
    results = relationship("Result", backref="job")


class Result(Base):
    __tablename__ = "result"

    id = sa.Column(sa.Integer, primary_key=True)
    job_id = sa.Column(sa.Integer, sa.ForeignKey("job.id"))


def upgrade():
    # Merge duplicate Jobs
    logger = logging.getLogger("alembic")
    connection = op.get_bind()
    session = Session(bind=connection)
    merge_targets = {}
    jobs_to_delete = []

    job_count_query = connection.execute(
        text(
            "select count(*) from job where uuid in (select uuid from job group by uuid having count(uuid) > 1);"
        )
    )
    job_count = -1
    for row in job_count_query:
        job_count = row[0]

    logger.info("Jobs marked for inspection: %s", job_count)

    job_query = (
        session.query(Job)
        .from_statement(
            text(
                "select id, uuid from job where uuid in (select uuid from job group by uuid having count(uuid) > 1) order by id;"
            )
        )
        .yield_per(100)
    )

    j = r = 0
    for job in job_query:
        j += 1
        primary = merge_targets.setdefault(job.uuid, job)
        if primary.id != job.id:
            for result in job.results:
                r += 1
                result.job_id = primary.id
                session.add(result)
            jobs_to_delete.append(job)
        if not j % 1000:
            logger.info("Jobs seen: %s out of %s", j, job_count)
            logger.info("Results marked for move: %s", r)
            session.commit()
    session.commit()
    logger.info("Removing duplicate jobs")
    for job in jobs_to_delete:
        session.delete(job)
    session.commit()

    logger.info("Changing table structure")

    # JOB
    op.rename_table("job", "group")
    op.alter_column("group", "name", new_column_name="description")
    op.drop_column("group", "status")
    op.drop_column("group", "start_time")
    op.drop_column("group", "end_time")
    op.create_unique_constraint(None, "group", ["uuid"])
    op.create_index(
        "group_idx_uuid",
        "group",
        ["uuid"],
        unique=False,
        postgresql_ops={"uuid": "text_pattern_ops"},
    )

    # RESULT
    op.add_column("result", sa.Column("testcase_name", sa.Text(), nullable=True))
    op.alter_column("result", "summary", new_column_name="note")
    op.alter_column("result", "log_url", new_column_name="ref_url")
    op.create_index(
        "result_fk_testcase_name",
        "result",
        ["testcase_name"],
        unique=False,
        postgresql_ops={"testcase_name": "text_pattern_ops"},
    )
    op.drop_index("result_fk_job_id", table_name="result")
    op.drop_index("result_fk_testcase_id", table_name="result")
    op.drop_constraint("result_testcase_id_fkey", "result", type_="foreignkey")
    op.drop_constraint("result_job_id_fkey", "result", type_="foreignkey")
    op.create_foreign_key(None, "result", "testcase", ["testcase_name"], ["name"])

    # TESTCASE
    op.alter_column("testcase", "url", new_column_name="ref_url")

    # MANY TO MANY
    op.create_table(
        "groups_to_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_uuid", sa.String(36), nullable=True),
        sa.Column("result_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["group_uuid"],
            ["group.uuid"],
        ),
        sa.ForeignKeyConstraint(
            ["result_id"],
            ["result.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "gtr_fk_group_uuid",
        "groups_to_results",
        ["group_uuid"],
        unique=False,
        postgresql_ops={"uuid": "text_pattern_ops"},
    )
    op.create_index(
        "gtr_fk_result_id", "groups_to_results", ["result_id"], unique=False
    )


def downgrade():
    # TESTCASE
    op.alter_column("testcase", "ref_url", new_column_name="url")

    # RESULT
    op.alter_column("result", "note", new_column_name="summary")
    op.alter_column("result", "ref_url", new_column_name="log_url")
    op.drop_constraint("result_testcase_name_fkey", "result", type_="foreignkey")
    op.create_index("result_fk_testcase_id", "result", ["testcase_id"], unique=False)
    op.create_index("result_fk_job_id", "result", ["job_id"], unique=False)
    op.drop_index("result_fk_testcase_name", table_name="result")
    op.drop_column("result", "testcase_name")

    # JOB
    op.rename_table("group", "job")
    op.alter_column("job", "description", new_column_name="name")
    op.add_column("job", sa.Column("end_time", sa.DateTime(), nullable=True))
    op.add_column("job", sa.Column("start_time", sa.DateTime(), nullable=True))
    op.add_column("job", sa.Column("status", sa.VARCHAR(length=16), nullable=True))
    op.drop_index("group_idx_uuid", table_name="job")

    # MANY TO MANY
    op.drop_index("gtr_fk_result_id", table_name="groups_to_results")
    op.drop_index("gtr_fk_group_uuid", table_name="groups_to_results")
    op.drop_table("groups_to_results")

    # CONSTRAINTS
    op.create_foreign_key(None, "result", "job", ["job_id"], ["id"])
    op.create_foreign_key(None, "result", "testcase", ["testcase_id"], ["id"])
    op.drop_constraint("group_uuid_key", "job")
