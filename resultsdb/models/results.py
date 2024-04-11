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
import uuid as lib_uuid

from flask import current_app
from sqlalchemy.orm import relationship

from resultsdb.models import db
from resultsdb.serializers import DBSerialize

__all__ = [
    "Testcase",
    "Group",
    "Result",
    "ResultData",
    "GroupsToResults",
    "result_outcomes",
]

PRESET_OUTCOMES = ("PASSED", "INFO", "FAILED", "NEEDS_INSPECTION")


def result_outcomes():
    additional_result_outcomes = tuple(
        current_app.config.get("ADDITIONAL_RESULT_OUTCOMES", [])
    )
    return PRESET_OUTCOMES + additional_result_outcomes


def utcnow_naive():
    """Returns current UTC date/time without the timezone info."""
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


class GroupsToResults(db.Model):
    __tablename__ = "groups_to_results"
    id = db.Column(db.Integer, primary_key=True)
    group_uuid = db.Column(db.String(36), db.ForeignKey("group.uuid"))
    result_id = db.Column(db.Integer, db.ForeignKey("result.id"))

    __table_args__ = (
        db.Index(
            "gtr_fk_group_uuid",
            "group_uuid",
            postgresql_ops={"uuid": "text_pattern_ops"},
        ),
        db.Index("gtr_fk_result_id", "result_id"),
    )


# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
#
# DO NOT FORGET TO UPDATE SERIALIZERS AFTER CHANGING STRUCTURE
#
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!


class Group(db.Model, DBSerialize):
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True)
    description = db.Column(db.Text)
    ref_url = db.Column(db.Text)

    results = relationship("Result", secondary="groups_to_results", backref="groups")

    __table_args__ = (
        db.Index(
            "group_idx_uuid",
            "uuid",
            postgresql_ops={"uuid": "text_pattern_ops"},
        ),
    )

    def __init__(self, uuid=None, ref_url=None, description=None):
        if uuid is None:
            uuid = str(lib_uuid.uuid1())
        self.uuid = uuid
        self.ref_url = ref_url
        self.description = description


class Testcase(db.Model, DBSerialize):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, unique=True)
    ref_url = db.Column(db.Text)

    __table_args__ = (
        db.Index(
            "testcase_idx_name",
            "name",
            postgresql_ops={"name": "text_pattern_ops"},
        ),
    )

    def __init__(self, name, ref_url=None):
        self.ref_url = ref_url
        self.name = name


class Result(db.Model, DBSerialize):
    id = db.Column(db.Integer, primary_key=True)
    testcase_name = db.Column(db.Text, db.ForeignKey("testcase.name"))

    submit_time = db.Column(db.DateTime, default=utcnow_naive)
    outcome = db.Column(db.String(32))
    note = db.Column(db.Text)
    ref_url = db.Column(db.Text)

    testcase = relationship("Testcase", backref="results")  # , lazy = False)
    data = relationship("ResultData", backref="result")  # , lazy = False)

    __table_args__ = (
        db.Index(
            "result_fk_testcase_name",
            "testcase_name",
            postgresql_ops={"testcase_name": "text_pattern_ops"},
        ),
        db.Index("result_submit_time", "submit_time"),
        db.Index(
            "result_idx_outcome",
            "outcome",
            postgresql_ops={"outcome": "text_pattern_ops"},
        ),
    )

    def __init__(
        self, testcase, outcome, groups=None, ref_url=None, note=None, submit_time=None
    ):
        self.testcase = testcase
        self.outcome = outcome
        self.ref_url = ref_url
        self.note = note
        self.groups = groups
        self.submit_time = submit_time


class ResultData(db.Model, DBSerialize):
    id = db.Column(db.Integer, primary_key=True)
    result_id = db.Column(db.Integer, db.ForeignKey("result.id"))

    key = db.Column(db.Text)
    value = db.Column(db.Text)

    __table_args__ = (
        db.Index(
            "result_data_idx_key_value",
            "key",
            "value",
            postgresql_ops={"key": "text_pattern_ops", "value": "text_pattern_ops"},
        ),
        db.Index("result_data_fk_result_id", "result_id"),
    )

    def __init__(self, result, key, value):
        self.result = result
        self.key = key
        self.value = value
