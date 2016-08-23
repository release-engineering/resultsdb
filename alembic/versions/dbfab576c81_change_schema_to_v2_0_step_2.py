"""Change schema to v2.0 - step 2 - data migration

Revision ID: dbfab576c81
Revises: 540dbe71fa91
Create Date: 2016-08-23 23:02:56.928292

"""

# revision identifiers, used by Alembic.
revision = 'dbfab576c81'
down_revision = '540dbe71fa91'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as db
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, relation, sessionmaker
import uuid

Session = sessionmaker()
Base = declarative_base()


db.relationship = relationship
db.relation = relation

RESULT_OUTCOME = ('PASSED', 'INFO', 'FAILED', 'NEEDS_INSPECTION')
JOB_STATUS = []


class GroupsToResults(Base):
    __tablename__ = 'groups_to_results'
    id = db.Column(db.Integer, primary_key=True)
    group_uuid = db.Column(db.String(36), db.ForeignKey('group.uuid'))
    result_id = db.Column(db.Integer, db.ForeignKey('result.id'))


class Group(Base):
    __tablename__ = 'group'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True)
#    results = db.relationship("Result", secondary = 'groups_to_results', backref="groups")


class Testcase(Base):
    __tablename__ = 'testcase'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, unique=True)


def upgrade():
    class Result(Base):
        __tablename__ = 'result'

        id = db.Column(db.Integer, primary_key=True)
        job_id = db.Column(db.Integer, db.ForeignKey('group.id'))
        testcase_id = db.Column(db.Integer, db.ForeignKey('testcase.id'))
        testcase_name = db.Column(db.Text)

        groups = db.relationship("Group", secondary='groups_to_results', backref="results")
        job = db.relation('Group')  # , lazy = False)
        testcase = db.relation('Testcase', backref='results')  # , lazy = False)

    connection = op.get_bind()
    session = Session(bind=connection)
    for group in session.query(Group):
        if not group.uuid:
            group.uuid = str(uuid.uuid1())
            session.add(group)
            session.commit()
    for result in session.query(Result):
        result.groups = [result.job]
        result.testcase_name = result.testcase.name
        session.add(result)
        session.commit()
    op.drop_column('result', 'testcase_id')
    op.drop_column('result', 'job_id')


def downgrade():
    class Result(Base):
        __tablename__ = 'result'

        id = db.Column(db.Integer, primary_key=True)
        job_id = db.Column(db.Integer, db.ForeignKey('group.id'))
        testcase_id = db.Column(db.Integer)
        testcase_name = db.Column(db.Text, db.ForeignKey('testcase.name'))

        groups = db.relationship("Group", secondary='groups_to_results', backref="results")
        job = db.relation('Group')  # , lazy = False)
        testcase = db.relation('Testcase', backref='results')  # , lazy = False)

    op.add_column('result', db.Column('job_id', db.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('result', db.Column(
        'testcase_id', db.INTEGER(), autoincrement=False, nullable=True))

    connection = op.get_bind()
    session = Session(bind=connection)
    for result in session.query(Result):
        result.job_id = result.groups[0].id
        result.testcase_id = result.testcase.id
        session.add(result)
        session.commit()
