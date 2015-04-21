# Copyright 2013, Red Hat, Inc
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Authors:
#   Josef Skladanka <jskladan@redhat.com>

import datetime

from resultsdb import db
from resultsdb.serializers import DBSerialize


__all__ = ['Testcase', 'Job', 'Result', 'ResultData', 'JOB_STATUS', 'RESULT_OUTCOME']



JOB_STATUS = ('SCHEDULED', 'RUNNING', 'COMPLETED', 'ABORTED', 'CRASHED', 'NEEDS_INSPECTION')
RESULT_OUTCOME = ('PASSED', 'INFO', 'FAILED', 'ERROR', 'WAIVED', 'NEEDS_INSPECTION', 'ABORTED')


# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
#
# DO NOT FORGET TO UPDATE SERIALIZERS AFTER CHANGING STRUCTURE
#
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

class Job(db.Model, DBSerialize):

    id = db.Column(db.Integer, primary_key = True)
    status = db.Column(db.Enum(*JOB_STATUS, name='jobstatus'))
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    ref_url = db.Column(db.Text)
    name = db.Column(db.Text)
    uuid = db.Column(db.String(36))

    results = db.relation('Result', backref = 'job') #, lazy = False)

    def __init__(self, status = 'SCHEDULED', ref_url = None, name = None, uuid = None):
        self.status = status
        self.ref_url = ref_url
        self.name = name
        self.uuid = uuid


class Testcase(db.Model, DBSerialize):

    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(255), unique = True)
    url = db.Column(db.Text)

    def __init__(self, name, url):
        self.url = url
        self.name = name


class Result(db.Model, DBSerialize):

    id = db.Column(db.Integer, primary_key = True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'))
    testcase_id = db.Column(db.Integer, db.ForeignKey('testcase.id'))

    submit_time = db.Column(db.DateTime, default = datetime.datetime.utcnow)
    outcome = db.Column(db.Enum(*RESULT_OUTCOME, name='resultoutcome'))
    summary = db.Column(db.Text)
    log_url = db.Column(db.Text)

    testcase = db.relation('Testcase', backref = 'results') #, lazy = False)
    result_data = db.relation('ResultData', backref = 'result') #, lazy = False)

    __table_args__ = (
            db.Index('result_fk_job_id', 'job_id'),
            db.Index('result_fk_testcase_id', 'testcase_id'),
            )

    def __init__(self, job, testcase, outcome, log_url = None, summary = None):
        self.job = job
        self.testcase = testcase
        self.outcome = outcome
        self.log_url = log_url
        self.summary = summary

class ResultData(db.Model, DBSerialize):

    id = db.Column(db.Integer, primary_key = True)
    result_id = db.Column(db.Integer, db.ForeignKey('result.id'))

    key = db.Column(db.Text)
    value = db.Column(db.Text)

    __table_args__ = (
            db.Index('result_data_idx_key_value', 'key', 'value',
                postgresql_ops={'key': 'text_pattern_ops', 'value': 'text_pattern_ops'},
                ),
            db.Index('result_data_fk_result_id', 'result_id'),
            )

    def __init__(self, result, key, value):
        self.result = result
        self.key = key
        self.value = value

