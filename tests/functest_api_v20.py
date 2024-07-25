# Copyright 2016, Red Hat, Inc.
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

import copy
import datetime
import os
from unittest import TestCase
from unittest.mock import ANY, patch

from flask import current_app as app

import resultsdb.messaging
from resultsdb.models import db
from resultsdb.models.results import utcnow_naive

GROUPS_API = "/api/v2.0/groups"
RESULTS_API = "/api/v2.0/results"
TESTCASES_API = "/api/v2.0/testcases"

EMPTY_TESTCASE_ERROR = {
    "validation_error": [
        {
            "loc": ["testcase"],
            "msg": "Value error, testcase name must be non-empty",
            "type": "value_error",
            "input": ANY,
            "url": ANY,
        }
    ]
}


def field_required_error(field):
    return {
        "validation_error": [
            {
                "loc": [field],
                "msg": "Field required",
                "type": "missing",
                "input": ANY,
                "url": ANY,
            }
        ]
    }


class AboutTime:
    def __eq__(self, value):
        start = (utcnow_naive() - datetime.timedelta(seconds=10)).isoformat()
        stop = (utcnow_naive() + datetime.timedelta(seconds=10)).isoformat()
        return start <= value <= stop


class TestFuncApiV20(TestCase):
    def require_postgres(self):
        if os.getenv("NO_CAN_HAS_POSTGRES", None):
            self.skipTest(
                "PostgreSQL server not available (disabled with NO_CAN_HAS_POSTGRES)"
            )

        if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
            raise RuntimeError(
                "This test requires PostgreSQL to work properly. "
                "You can disable it by setting NO_CAN_HAS_POSTGRES "
                "env variable to any non-empty value.\n"
                f'Current DB URI: {app.config["SQLALCHEMY_DATABASE_URI"]}'
            )

        assert db.engine.name == "postgresql"

    @classmethod
    def setup_class(cls):
        app.config["MESSAGE_BUS_PUBLISH"] = True
        app.config["MESSAGE_BUS_PLUGIN"] = "dummy"

    def setup_method(self, method):
        db.session.rollback()
        db.drop_all()
        db.create_all()
        self.app = app.test_client()
        self.ref_url_prefix = "http://localhost/api/v2.0"

        # Testcase data
        self.ref_testcase_name = "fedora-ci.koji-build./plans/basic.functional"
        self.ref_testcase_ref_url = (
            "https://example.com/fedora-ci.koji-build./plans/basic.functional"
        )
        self.ref_testcase = {
            "name": self.ref_testcase_name,
            "ref_url": self.ref_testcase_ref_url,
            "href": self.ref_url_prefix + "/testcases/" + self.ref_testcase_name,
        }

        # Group data
        self.ref_group_uuid = "3ce5f6d7-ce34-489b-ab61-325ce634eab5"
        self.ref_group_description = "Testing Group"
        self.ref_group_ref_url = "https://example.com/testing.group"
        self.ref_group = {
            "uuid": self.ref_group_uuid,
            "description": self.ref_group_description,
            "ref_url": self.ref_group_ref_url,
            "href": self.ref_url_prefix + "/groups/" + self.ref_group_uuid,
            "results_count": 0,
            "results": self.ref_url_prefix + "/results?groups=" + self.ref_group_uuid,
        }

        # Result data
        self.ref_result_id = 1
        self.ref_result_outcome = "PASSED"
        self.ref_result_note = "Result Note"
        self.ref_result_item = "perl-Specio-0.25-1.fc26"
        self.ref_result_type = "koji_build"
        self.ref_result_arch = "x86_64"
        self.ref_result_data = {
            "item": self.ref_result_item,
            "type": self.ref_result_type,
            "arch": self.ref_result_arch,
            "moo": ["boo", "woof"],
        }
        self.ref_result_ref_url = "https://example.com/testing.result"
        self.ref_result = {
            "id": self.ref_result_id,
            "groups": [self.ref_group["uuid"]],
            "testcase": self.ref_testcase,
            "submit_time": AboutTime(),
            "outcome": self.ref_result_outcome,
            "note": self.ref_result_note,
            "ref_url": self.ref_result_ref_url,
            "data": {
                key: [value] if isinstance(value, (str, bytes)) else value
                for key, value in self.ref_result_data.items()
            },
            "href": self.ref_url_prefix + "/results/1",
        }

    def teardown_method(self, method):
        # Reset this for each test.
        resultsdb.messaging.DummyPlugin.history = []

    # =============== TESTCASES ==================

    def helper_create_testcase(self, name=None, ref_url=None):
        if name is None:
            name = self.ref_testcase_name
        if ref_url is None:
            ref_url = self.ref_testcase_ref_url
        return self.app.post(TESTCASES_API, json={"name": name, "ref_url": ref_url})

    def test_create_testcase(self):
        r = self.helper_create_testcase()
        assert r.status_code == 201
        assert r.json == self.ref_testcase

    def test_create_testcase_missing_data(self):
        r = self.app.post(TESTCASES_API, json={"ref_url": self.ref_testcase_ref_url})
        assert r.status_code == 400
        assert r.json == field_required_error("name")

    def test_create_testcase_empty_name(self):
        r = self.app.post(TESTCASES_API, json={"name": ""})
        assert r.status_code == 400
        assert r.json == {
            "validation_error": [
                {
                    "loc": ["name"],
                    "msg": "String should have at least 1 character",
                    "type": "string_too_short",
                    "input": ANY,
                    "url": ANY,
                }
            ]
        }

    def test_update_testcase(self):
        self.test_create_testcase()

        testcase = copy.copy(self.ref_testcase)
        testcase["ref_url"] = "Updated"

        data = {"name": self.ref_testcase_name, "ref_url": testcase["ref_url"]}

        r = self.app.post(TESTCASES_API, json=data)
        assert r.status_code == 201
        assert r.json == testcase

    def test_get_testcase(self):
        self.test_create_testcase()

        r = self.app.get(f"{TESTCASES_API}/{self.ref_testcase_name}")
        assert r.status_code == 200
        assert r.json == self.ref_testcase

    def test_get_missing_testcase(self):
        r = self.app.get(f"{TESTCASES_API}/{self.ref_testcase_name}")

        assert r.status_code == 404
        assert r.json is not None
        assert r.json["message"] == "Testcase not found"

    def test_get_testcases(self):
        r = self.app.get(TESTCASES_API)

        assert r.status_code == 200
        assert r.json is not None
        assert r.json["data"] == []

        self.test_create_testcase()

        r = self.app.get(TESTCASES_API)

        assert r.status_code == 200
        assert r.json is not None
        assert len(r.json["data"]) == 1
        assert r.json["data"][0] == self.ref_testcase

    def test_get_testcases_by_name(self):
        self.test_create_testcase()

        r = self.app.get(f"{TESTCASES_API}?name={self.ref_testcase_name}")

        assert r.status_code == 200
        assert r.json is not None
        assert len(r.json["data"]) == 1
        assert r.json["data"][0] == self.ref_testcase

        r = self.app.get(f"{TESTCASES_API}?name:like=*{self.ref_testcase_name[1:-1]}*")

        assert r.status_code == 200
        assert r.json is not None
        assert len(r.json["data"]) == 1
        assert r.json["data"][0] == self.ref_testcase

    # =============== GROUPS ==================

    def helper_create_group(self, uuid=None, description=None, ref_url=None):
        if uuid is None:
            uuid = self.ref_group_uuid
        if description is None:
            description = self.ref_group_description
        if ref_url is None:
            ref_url = self.ref_group_ref_url

        data = {"uuid": uuid, "description": description, "ref_url": ref_url}

        return self.app.post(GROUPS_API, json=data)

    def test_create_group(self):
        r = self.helper_create_group()
        assert r.status_code == 201
        assert r.json == self.ref_group

    def test_create_group_no_data(self):
        r = self.app.post(GROUPS_API, json={})

        assert r.status_code == 201
        assert r.json is not None
        assert len(r.json["uuid"]) == len(self.ref_group_uuid)
        assert r.json["description"] is None
        assert r.json["ref_url"] is None
        assert r.json["href"] == self.ref_url_prefix + "/groups/" + r.json["uuid"]
        assert r.json["results_count"] == 0
        assert (
            r.json["results"]
            == self.ref_url_prefix + "/results?groups=" + r.json["uuid"]
        )

    def test_update_group(self):
        self.test_create_group()

        data = {
            "uuid": self.ref_group_uuid,
            "description": "Changed",
            "ref_url": "Changed",
        }

        r = self.app.post(GROUPS_API, json=data)

        group = copy.copy(self.ref_group)
        group["description"] = group["ref_url"] = "Changed"

        assert r.status_code == 201
        assert r.json == group

    def test_get_group(self):
        self.test_create_group()

        r = self.app.get(f"{GROUPS_API}/{self.ref_group_uuid}")

        assert r.status_code == 200
        assert r.json == self.ref_group

    def test_get_missing_group(self):
        r = self.app.get("/api/v2.0/groups/missing")

        assert r.status_code == 404
        assert r.json is not None
        assert r.json["message"] == "Group not found"

    def test_get_groups(self):
        r = self.app.get(GROUPS_API)

        assert r.status_code == 200
        assert r.json is not None
        assert len(r.json["data"]) == 0

        self.test_create_group()
        r = self.app.get(GROUPS_API)

        assert r.status_code == 200
        assert r.json is not None
        assert len(r.json["data"]) == 1
        assert r.json["data"][0] == self.ref_group

    def test_get_groups_by_description(self):
        self.test_create_group()

        r = self.app.get(f"{GROUPS_API}?description={self.ref_group_description}")

        assert r.status_code == 200
        assert r.json is not None
        assert len(r.json["data"]) == 1
        assert r.json["data"][0] == self.ref_group

        r = self.app.get(
            "/api/v2.0/groups?description:like=*%s*" % self.ref_group_description[1:-1]
        )

        assert r.status_code == 200
        assert r.json is not None
        assert len(r.json["data"]) == 1
        assert r.json["data"][0] == self.ref_group

    def test_get_groups_by_more_descriptions(self):
        self.helper_create_group(uuid="1", description="FooBar")
        self.helper_create_group(uuid="2", description="BarFoo")

        r = self.app.get("/api/v2.0/groups?description=FooBar,BarFoo")

        assert r.status_code == 200
        assert r.json is not None
        assert len(r.json["data"]) == 2

        r = self.app.get("/api/v2.0/groups?description:like=*oo*,*ar*")

        assert r.status_code == 200
        assert r.json is not None
        assert len(r.json["data"]) == 2

    def test_get_groups_by_more_uuids(self):
        self.helper_create_group(uuid="FooBar")
        self.helper_create_group(uuid="BarFoo")

        r = self.app.get("/api/v2.0/groups?uuid=FooBar,BarFoo")

        assert r.status_code == 200
        assert r.json is not None
        assert len(r.json["data"]) == 2

    # =============== RESULTS ==================

    def helper_create_result(self, outcome=None, groups=None, testcase=None, data=None):
        if outcome is None:
            outcome = self.ref_result_outcome
        if groups is None:
            groups = [self.ref_group_uuid]
        if testcase is None:
            testcase = self.ref_testcase_name
        if data is None:
            data = self.ref_result_data

        data = dict(
            outcome=outcome,
            testcase=testcase,
            groups=groups,
            note=self.ref_result_note,
            data=data,
            ref_url=self.ref_result_ref_url,
        )

        return self.app.post(RESULTS_API, json=data)

    def test_create_result(self):
        self.test_create_group()
        self.test_create_testcase()

        r = self.helper_create_result()
        assert r.status_code == 201
        assert r.json == self.ref_result

    def test_create_result_custom_outcome(self):
        self.test_create_group()
        self.test_create_testcase()
        ref_result = copy.deepcopy(self.ref_result)
        ref_result["outcome"] = "AMAZING"

        r = self.helper_create_result(outcome="AMAZING")

        assert r.status_code == 201
        assert r.json == ref_result

    def test_create_result_with_testcase_name(self):
        self.test_create_group()
        self.test_create_testcase()
        testcase_name = self.ref_result["testcase"]["name"]

        r = self.helper_create_result(outcome="AMAZING", testcase=testcase_name)

        assert r.status_code == 201
        assert r.json is not None
        assert r.json["testcase"]["name"] == testcase_name

    def test_create_result_empty_testcase(self):
        r = self.app.post(RESULTS_API, json={"outcome": "passed", "testcase": ""})
        assert r.status_code == 400
        assert r.json == EMPTY_TESTCASE_ERROR

    def test_create_result_empty_testcase_name(self):
        r = self.app.post(
            RESULTS_API, json={"outcome": "passed", "testcase": {"name": ""}}
        )

        assert r.status_code == 400
        assert r.json == EMPTY_TESTCASE_ERROR

    def test_create_result_empty_testcase_dict(self):
        r = self.app.post(RESULTS_API, json={"outcome": "passed", "testcase": {}})

        assert r.status_code == 400
        assert r.json == EMPTY_TESTCASE_ERROR

    def test_create_result_missing_testcase(self):
        r = self.app.post(RESULTS_API, json={"outcome": "passed"})

        assert r.status_code == 400
        assert r.json == field_required_error("testcase")

    def test_create_result_missing_outcome(self):
        r = self.app.post(RESULTS_API, json={"testcase": self.ref_testcase})

        assert r.status_code == 400
        assert r.json == field_required_error("outcome")

    def test_create_result_multiple_groups(self):
        uuid2 = "1c26effb-7c07-4d90-9428-86aac053288c"
        self.test_create_group()
        self.helper_create_group(uuid=uuid2)
        self.test_create_testcase()

        r = self.helper_create_result(groups=[self.ref_group, uuid2])

        assert r.status_code == 201
        assert r.json is not None
        assert len(r.json["groups"]) == 2
        assert self.ref_group_uuid in " ".join(r.json["groups"])
        assert uuid2 in ";".join(r.json["groups"])

        ref_result = copy.deepcopy(self.ref_result)
        ref_result["groups"] = None
        data = copy.deepcopy(r.json)
        data["groups"] = None
        assert data == ref_result

    def test_create_result_group_is_none(self):
        ref_data = dict(
            outcome=self.ref_result_outcome,
            testcase=self.ref_testcase,
            groups=None,
        )

        r = self.app.post(RESULTS_API, json=ref_data)

        assert r.status_code == 201
        assert r.json is not None
        assert r.json["groups"] == []

    def test_create_result_group_did_not_exist(self):
        self.helper_create_result(groups=[self.ref_group])

        r = self.app.get(f"{GROUPS_API}/{self.ref_group_uuid}")

        ref_group = copy.deepcopy(self.ref_group)
        ref_group["results_count"] = 1

        assert r.status_code == 200
        assert r.json == ref_group

        uuid2 = "1c26effb-7c07-4d90-9428-86aac053288c"
        self.helper_create_result(groups=[uuid2])
        r = self.app.get(f"{GROUPS_API}/{uuid2}")

        assert r.status_code == 200
        assert r.json is not None
        assert r.json["uuid"] == uuid2
        assert r.json["description"] is None
        assert r.json["ref_url"] is None

    def test_create_result_testcase_did_not_exist(self):
        self.helper_create_result(testcase=self.ref_testcase)

        r = self.app.get(f"{TESTCASES_API}/{self.ref_testcase_name}")

        assert r.status_code == 200
        assert r.json == self.ref_testcase

        name2 = self.ref_testcase_name + ".fake"
        self.helper_create_result(testcase=name2)
        r = self.app.get(f"{TESTCASES_API}/{name2}")

        assert r.status_code == 200
        assert r.json is not None
        assert r.json["name"] == name2

    def test_create_result_invalid_outcome(self):
        ref_data = {"outcome": "FAKEOUTCOME", "testcase": self.ref_testcase}

        r = self.app.post(RESULTS_API, json=ref_data)

        assert r.status_code == 400
        assert r.json == {
            "validation_error": [
                {
                    "loc": ["outcome"],
                    "msg": (
                        "Value error, must be one of:"
                        " PASSED, INFO, FAILED, NEEDS_INSPECTION, AMAZING"
                    ),
                    "type": "value_error",
                    "input": ANY,
                    "url": ANY,
                }
            ]
        }

    def test_create_result_invalid_data(self):
        ref_data = {
            "outcome": self.ref_result_outcome,
            "testcase": self.ref_testcase,
            "data": {"validkey": 1, "invalid:key": 2, "another:invalid:key": 3},
        }

        r = self.app.post(RESULTS_API, json=ref_data)

        assert r.status_code == 400
        assert r.json is not None
        assert r.json["message"].startswith("Colon not allowed in key name:")

    def test_create_result_submit_time_as_number(self):
        ref_data = dict(
            outcome=self.ref_result_outcome,
            testcase=self.ref_testcase,
            submit_time=1661324097123,
        )

        r = self.app.post(RESULTS_API, json=ref_data)

        assert r.status_code == 201, r.json
        assert r.json is not None
        assert r.json["submit_time"] == "2022-08-24T06:54:57.123000"

    def test_create_result_submit_time_as_number_string(self):
        ref_data = dict(
            outcome=self.ref_result_outcome,
            testcase=self.ref_testcase,
            submit_time="1661324097123",
        )

        r = self.app.post(RESULTS_API, json=ref_data)

        assert r.status_code == 201, r.json
        assert r.json is not None
        assert r.json["submit_time"] == "2022-08-24T06:54:57.123000"

    def test_create_result_submit_time_as_datetime(self):
        for suffix in ("", "Z", "+00:00", "+0000", "+00"):
            ref_data = dict(
                outcome=self.ref_result_outcome,
                testcase=self.ref_testcase,
                submit_time=f"2022-08-24T06:54:57.123456{suffix}",
            )

            r = self.app.post(RESULTS_API, json=ref_data)

            assert r.status_code == 201, r.json
            assert r.json is not None
            assert r.json["submit_time"] == "2022-08-24T06:54:57.123456"

    def test_create_result_submit_time_as_invalid(self):
        ref_data = dict(
            outcome=self.ref_result_outcome,
            testcase=self.ref_testcase,
            submit_time="now",
        )

        r = self.app.post(RESULTS_API, json=ref_data)

        assert r.status_code == 400, r.json
        assert r.json is not None
        assert r.json == {
            "validation_error": [
                {
                    "loc": ["submit_time"],
                    "msg": (
                        "Value error, Expected timestamp in milliseconds or datetime"
                        " (in format YYYY-MM-DDTHH:MM:SS.ffffff), got 'now'"
                    ),
                    "type": "value_error",
                    "input": ANY,
                    "url": ANY,
                }
            ]
        }

    def test_get_result(self):
        self.test_create_result()

        r = self.app.get("/api/v2.0/results/%d" % self.ref_result_id)

        assert r.status_code == 200
        assert r.json == self.ref_result

    def test_get_missing_result(self):
        r = self.app.get("/api/v2.0/results/%d" % self.ref_result_id)

        assert r.status_code == 404
        assert r.json is not None
        assert r.json["message"] == "Result not found"

    def test_get_results(self):
        r = self.app.get(RESULTS_API)

        assert r.status_code == 200
        assert r.json is not None
        assert r.json["data"] == []

        self.test_create_result()

        r = self.app.get(RESULTS_API)

        assert r.status_code == 200
        assert r.json is not None
        assert len(r.json["data"]) == 1
        assert r.json["data"][0] == self.ref_result

    def test_get_results_sorted_by_submit_time_desc_by_default(self):
        r1 = self.helper_create_result()
        assert r1.json is not None
        r2 = self.helper_create_result()
        assert r2.json is not None

        r = self.app.get(RESULTS_API)

        assert r.status_code == 200
        assert r.json is not None
        assert len(r.json["data"]) == 2

        assert r.json["data"][0]["id"] == r2.json["id"]
        assert r.json["data"][1]["id"] == r1.json["id"]

    def test_get_results_by_group(self):
        uuid2 = "1c26effb-7c07-4d90-9428-86aac053288c"
        self.helper_create_group(uuid=uuid2)

        self.test_create_result()
        self.helper_create_result(groups=[uuid2])

        r1 = self.app.get(f"{GROUPS_API}/{self.ref_group_uuid}/results")
        r2 = self.app.get(f"{RESULTS_API}?groups={self.ref_group_uuid}")

        assert r1.status_code == 200, r1.text
        assert r2.status_code == 200, r2.text
        assert r1.json is not None
        assert r2.json is not None
        assert len(r1.json["data"]) == len(r1.json["data"]) == 1
        assert r1.json == r2.json
        assert r1.json["data"][0] == self.ref_result

        r = self.app.get(f"{RESULTS_API}?groups={self.ref_group_uuid},{uuid2}")

        assert r.status_code == 200
        assert r.json is not None
        assert len(r.json["data"]) == 2

    def test_get_results_by_testcase(self):
        name2 = self.ref_testcase_name + ".fake"
        self.helper_create_testcase(name=name2)

        self.test_create_result()
        self.helper_create_result(testcase=name2)

        r1 = self.app.get(f"{TESTCASES_API}/{self.ref_testcase_name}/results")
        r2 = self.app.get(f"{RESULTS_API}?testcases={self.ref_testcase_name}")

        assert r1.status_code == 200, r1.text
        assert r2.status_code == 200, r2.text
        assert r1.json is not None
        assert r2.json is not None
        assert r1.json["data"][0] == self.ref_result
        assert r2.json["data"][0] == self.ref_result

        r = self.app.get(f"{RESULTS_API}?testcases={self.ref_testcase_name},{name2}")

        assert r.status_code == 200
        assert r.json is not None
        assert len(r.json["data"]) == 2

    def test_get_results_by_testcase_like(self):
        name2 = self.ref_testcase_name + ".fake"
        self.helper_create_testcase(name=name2)

        self.test_create_result()
        self.helper_create_result(testcase=name2)

        r1 = self.app.get(f"{TESTCASES_API}/{self.ref_testcase_name}/results")
        r2 = self.app.get(f"{RESULTS_API}?testcases:like={self.ref_testcase_name}")

        assert r1.status_code == 200, r1.text
        assert r2.status_code == 200, r2.text
        assert r1.json is not None
        assert r2.json is not None
        assert r1.json["data"][0] == self.ref_result
        assert r2.json["data"][0] == self.ref_result

        r1 = self.app.get(f"{RESULTS_API}?testcases:like={self.ref_testcase_name}*")
        r2 = self.app.get(
            f"{RESULTS_API}?testcases:like={self.ref_testcase_name},{self.ref_testcase_name}*"
        )

        assert r1.status_code == r2.status_code == 200
        assert r1.json == r2.json

    def test_get_results_by_outcome(self):
        self.test_create_result()
        self.helper_create_result(outcome="FAILED")

        r = self.app.get("/api/v2.0/results?outcome=PASSED")

        assert r.status_code == 200
        assert r.json is not None
        assert len(r.json["data"]) == 1
        assert r.json["data"][0] == self.ref_result

        r = self.app.get("/api/v2.0/results?outcome=PASSED,FAILED")

        assert r.status_code == 200
        assert r.json is not None
        assert len(r.json["data"]) == 2

    def test_get_results_sorting_by_submit_time(self):
        name1 = "aa_fake." + self.ref_testcase_name
        self.helper_create_testcase(name=name1)

        self.test_create_result()
        self.helper_create_result(testcase=name1)

        r1 = self.app.get("/api/v2.0/results?_sort=desc:submit_time")
        data1 = r1.json
        assert data1 is not None

        assert r1.status_code == 200
        assert len(data1["data"]) == 2

        r2 = self.app.get("/api/v2.0/results?_sort=asc:submit_time")
        data2 = r2.json
        assert data2 is not None

        assert r2.status_code == 200
        assert len(data2["data"]) == 2

        # Checks if the first result retrieved from a parameterless API call
        # is the last result of an API call with the '_sort' parameter and vice-versa.
        assert data1["data"][0]["submit_time"] == data2["data"][1]["submit_time"]
        assert data1["data"][1]["submit_time"] == data2["data"][0]["submit_time"]

        # Confirms if the results are in descending order.
        assert data1["data"][0]["testcase"]["name"] == name1
        assert data1["data"][1]["testcase"]["name"] == self.ref_testcase_name

        # Confirms if the results are in ascending order.
        assert data2["data"][0]["testcase"]["name"] == self.ref_testcase_name
        assert data2["data"][1]["testcase"]["name"] == name1

    def test_get_results_by_since(self):
        self.test_create_result()
        before1 = (utcnow_naive() - datetime.timedelta(seconds=100)).isoformat()
        before2 = (utcnow_naive() - datetime.timedelta(seconds=99)).isoformat()
        after = (utcnow_naive() + datetime.timedelta(seconds=100)).isoformat()

        r = self.app.get(f"{RESULTS_API}?since={before1}")
        assert r.status_code == 200, r.text
        assert r.json is not None
        assert len(r.json["data"]) == 1
        assert r.json["data"][0] == self.ref_result

        r = self.app.get(f"{RESULTS_API}?since={before1},{after}")
        assert r.status_code == 200, r.text
        assert r.json is not None
        assert len(r.json["data"]) == 1
        assert r.json["data"][0] == self.ref_result

        r = self.app.get(f"{RESULTS_API}?since={(after)}")
        assert r.status_code == 200, r.text
        assert r.json is not None
        assert len(r.json["data"]) == 0

        r = self.app.get(f"{RESULTS_API}?since={before1},{before2}")
        assert r.status_code == 200, r.text
        assert r.json is not None
        assert len(r.json["data"]) == 0

    def test_get_results_by_result_data(self):
        self.test_create_result()

        r = self.app.get("/api/v2.0/results?item=perl-Specio-0.25-1.fc26")
        assert r.status_code == 200
        assert r.json is not None
        assert len(r.json["data"]) == 1
        assert r.json["data"][0] == self.ref_result

        r = self.app.get("/api/v2.0/results?item=perl-Specio-0.25-1.fc26&moo=boo,woof")
        assert r.status_code == 200
        assert r.json is not None
        assert len(r.json["data"]) == 1
        assert r.json["data"][0] == self.ref_result

        r = self.app.get("/api/v2.0/results?item=perl-Specio-0.25-1.fc26&moo=boo,fake")
        assert r.status_code == 200
        assert r.json is not None
        assert len(r.json["data"]) == 1
        assert r.json["data"][0] == self.ref_result

        r = self.app.get("/api/v2.0/results?moo:like=*oo*")
        assert r.status_code == 200
        assert r.json is not None
        assert len(r.json["data"]) == 1
        assert r.json["data"][0] == self.ref_result

        r = self.app.get("/api/v2.0/results?moo:like=*fake*,*oo*")
        assert r.status_code == 200
        assert r.json is not None
        assert len(r.json["data"]) == 1
        assert r.json["data"][0] == self.ref_result

    def test_get_results_latest(self):
        self.helper_create_testcase()
        self.helper_create_testcase(name=self.ref_testcase_name + ".1")
        self.helper_create_testcase(name=self.ref_testcase_name + ".2")

        self.helper_create_result(outcome="PASSED")
        r = self.app.get("/api/v2.0/results/latest")

        assert r.json is not None
        assert len(r.json["data"]) == 1

        self.helper_create_result(outcome="FAILED")
        r = self.app.get("/api/v2.0/results/latest")

        assert r.json is not None
        assert len(r.json["data"]) == 1
        assert r.json["data"][0]["outcome"] == "FAILED"

        self.helper_create_result(testcase=self.ref_testcase_name + ".1")
        r = self.app.get("/api/v2.0/results/latest")

        assert r.json is not None
        assert len(r.json["data"]) == 2
        assert r.json["data"][0]["testcase"]["name"] == self.ref_testcase_name + ".1"
        assert r.json["data"][1]["testcase"]["name"] == self.ref_testcase_name
        assert r.json["data"][1]["outcome"] == "FAILED"

    def test_get_results_latest_modifiers(self):
        self.helper_create_testcase()
        self.helper_create_testcase(name=self.ref_testcase_name + ".1")
        self.helper_create_testcase(name=self.ref_testcase_name + ".2")

        self.helper_create_result(outcome="PASSED")
        self.helper_create_result(outcome="FAILED")
        self.helper_create_result(
            testcase=self.ref_testcase_name + ".1", outcome="PASSED"
        )
        self.helper_create_result(
            testcase=self.ref_testcase_name + ".1",
            groups=["foobargroup"],
            outcome="FAILED",
        )

        r = self.app.get(f"{RESULTS_API}/latest?testcases={self.ref_testcase_name}")

        assert r.json is not None
        assert len(r.json["data"]) == 1
        assert r.json["data"][0]["testcase"]["name"] == self.ref_testcase_name
        assert r.json["data"][0]["outcome"] == "FAILED"

        r = self.app.get(
            f"{RESULTS_API}/latest?testcases={self.ref_testcase_name},{self.ref_testcase_name + '.1'}"
        )

        assert r.json is not None
        assert len(r.json["data"]) == 2
        assert r.json["data"][0]["testcase"]["name"] == self.ref_testcase_name + ".1"
        assert r.json["data"][0]["outcome"] == "FAILED"
        assert r.json["data"][1]["testcase"]["name"] == self.ref_testcase_name
        assert r.json["data"][1]["outcome"] == "FAILED"

        r = self.app.get("/api/v2.0/results/latest?testcases:like=*")

        assert r.json is not None
        assert len(r.json["data"]) == 2
        assert r.json["data"][0]["testcase"]["name"] == self.ref_testcase_name + ".1"
        assert r.json["data"][0]["outcome"] == "FAILED"
        assert r.json["data"][1]["testcase"]["name"] == self.ref_testcase_name
        assert r.json["data"][1]["outcome"] == "FAILED"

        r = self.app.get(f"{RESULTS_API}/latest?groups={self.ref_group_uuid}")

        assert r.json is not None
        assert len(r.json["data"]) == 2
        assert r.json["data"][0]["testcase"]["name"] == self.ref_testcase_name + ".1"
        assert r.json["data"][0]["outcome"] == "PASSED"
        assert r.json["data"][1]["testcase"]["name"] == self.ref_testcase_name
        assert r.json["data"][1]["outcome"] == "FAILED"

    def test_get_results_latest_distinct_on(self):
        """This test requires PostgreSQL, because DISTINCT ON does work differently in SQLite"""
        self.require_postgres()

        self.helper_create_testcase()

        self.helper_create_result(
            outcome="PASSED",
            data={"scenario": "scenario1"},
            testcase=self.ref_testcase_name,
        )
        self.helper_create_result(
            outcome="FAILED",
            data={"scenario": "scenario2"},
            testcase=self.ref_testcase_name,
        )

        r = self.app.get(
            "/api/v2.0/results/latest?testcases="
            + self.ref_testcase_name
            + "&_distinct_on=scenario"
        )
        assert r.json is not None
        assert len(r.json["data"]) == 2
        assert r.json["data"][0]["data"]["scenario"][0] == "scenario2"
        assert r.json["data"][1]["data"]["scenario"][0] == "scenario1"

        r = self.app.get("/api/v2.0/results/latest?testcases=" + self.ref_testcase_name)
        assert r.json is not None
        assert len(r.json["data"]) == 1
        assert r.json["data"][0]["data"]["scenario"][0] == "scenario2"

    def test_get_results_latest_distinct_on_more_specific_cases_1(self):
        """This test requires PostgreSQL, because DISTINCT ON does work differently in SQLite"""
        self.require_postgres()

        """
            | id | testcase | scenario |
            |----|----------|----------|
            | 1  | tc_1     | s_1      |
            | 2  | tc_2     | s_1      |
            | 3  | tc_2     | s_2      |
            | 4  | tc_3     |          |
        """
        self.helper_create_result(
            outcome="PASSED", testcase="tc_1", data={"item": "grub", "scenario": "s_1"}
        )
        self.helper_create_result(
            outcome="PASSED", testcase="tc_2", data={"item": "grub", "scenario": "s_1"}
        )
        self.helper_create_result(
            outcome="PASSED", testcase="tc_2", data={"item": "grub", "scenario": "s_2"}
        )
        self.helper_create_result(
            outcome="PASSED", testcase="tc_3", data={"item": "grub"}
        )

        r = self.app.get("/api/v2.0/results/latest?item=grub&_distinct_on=scenario")

        assert r.json is not None
        assert len(r.json["data"]) == 4

    def test_get_results_latest_distinct_on_more_specific_cases_2(self):
        """This test requires PostgreSQL, because DISTINCT ON does work differently in SQLite"""
        self.require_postgres()

        """
            | id | testcase | scenario |
            |----|----------|----------|
            | 1  | tc_1     | s_1      |
            | 2  | tc_2     | s_1      |
            | 3  | tc_2     | s_2      |
            | 4  | tc_3     |          |
            | 5  | tc_1     |          |
        """
        self.helper_create_result(
            outcome="PASSED", testcase="tc_1", data={"item": "grub", "scenario": "s_1"}
        )
        self.helper_create_result(
            outcome="PASSED", testcase="tc_2", data={"item": "grub", "scenario": "s_1"}
        )
        self.helper_create_result(
            outcome="PASSED", testcase="tc_2", data={"item": "grub", "scenario": "s_2"}
        )
        self.helper_create_result(
            outcome="PASSED", testcase="tc_3", data={"item": "grub"}
        )
        self.helper_create_result(
            outcome="FAILED", testcase="tc_1", data={"item": "grub"}
        )

        r = self.app.get("/api/v2.0/results/latest?item=grub&_distinct_on=scenario")

        assert r.json is not None
        assert len(r.json["data"]) == 5

    def test_get_results_latest_distinct_on_more_specific_cases_3(self):
        """This test requires PostgreSQL, because DISTINCT ON does work differently in SQLite"""
        self.require_postgres()

        """
            | id | testcase | scenario |
            |----|----------|----------|
            | 1  | tc_1     | s_1      |
            | 2  | tc_2     | s_1      |
            | 3  | tc_2     | s_2      |
            | 4  | tc_3     |          |
            | 5  | tc_1     |          |
            | 6  | tc_1     | s_1      |
        """
        self.helper_create_result(
            outcome="PASSED", testcase="tc_1", data={"item": "grub", "scenario": "s_1"}
        )
        self.helper_create_result(
            outcome="PASSED", testcase="tc_2", data={"item": "grub", "scenario": "s_1"}
        )
        self.helper_create_result(
            outcome="PASSED", testcase="tc_2", data={"item": "grub", "scenario": "s_2"}
        )
        self.helper_create_result(
            outcome="PASSED", testcase="tc_3", data={"item": "grub"}
        )
        self.helper_create_result(
            outcome="FAILED", testcase="tc_1", data={"item": "grub"}
        )
        self.helper_create_result(
            outcome="INFO", testcase="tc_1", data={"item": "grub", "scenario": "s_1"}
        )

        r = self.app.get("/api/v2.0/results/latest?item=grub&_distinct_on=scenario")

        assert r.json is not None
        items = [
            (
                x["data"].get("scenario", [None])[0],
                x["testcase"]["name"],
                x["outcome"],
            )
            for x in r.json["data"]
        ]
        assert items == [
            ("s_1", "tc_1", "INFO"),
            (None, "tc_1", "FAILED"),
            (None, "tc_3", "PASSED"),
            ("s_2", "tc_2", "PASSED"),
            ("s_1", "tc_2", "PASSED"),
        ]

    def test_get_results_latest_distinct_on_with_scenario_not_defined(self):
        """This test requires PostgreSQL, because DISTINCT ON does work differently in SQLite"""
        self.require_postgres()

        self.helper_create_testcase()
        self.helper_create_result(outcome="PASSED", testcase=self.ref_testcase_name)
        self.helper_create_result(outcome="FAILED", testcase=self.ref_testcase_name)

        r = self.app.get(
            "/api/v2.0/results/latest?testcases="
            + self.ref_testcase_name
            + "&_distinct_on=scenario"
        )

        assert r.json is not None
        assert len(r.json["data"]) == 1
        assert r.json["data"][0]["outcome"] == "FAILED"

    def test_get_results_latest_distinct_on_wrong_params(self):
        r = self.app.get("/api/v2.0/results/latest?_distinct_on=scenario")
        assert r.status_code == 400
        assert r.json is not None
        assert (
            r.json["message"]
            == "Please, provide at least one filter beside '_distinct_on'"
        )

    def test_message_publication(self):
        self.helper_create_result()
        plugin = resultsdb.messaging.DummyPlugin
        assert len(plugin.history) == 1, plugin.history
        assert plugin.history[0]["data"]["item"] == [self.ref_result_item]
        assert plugin.history[0]["data"]["type"] == [self.ref_result_type]
        assert plugin.history[0]["id"] == 1
        assert plugin.history[0]["outcome"] == self.ref_result_outcome
        assert plugin.history[0]["ref_url"] == self.ref_result_ref_url
        assert plugin.history[0]["groups"] == [self.ref_group_uuid]
        assert plugin.history[0]["note"] == self.ref_result_note
        assert plugin.history[0]["testcase"]["name"] == self.ref_testcase_name

    def test_get_outcomes_on_landing_page(self):
        r = self.app.get("/api/v2.0/")
        assert r.status_code == 300
        assert r.json is not None
        assert r.json["outcomes"] == [
            "PASSED",
            "INFO",
            "FAILED",
            "NEEDS_INSPECTION",
            "AMAZING",
        ]

    def test_healthcheck_success(self):
        r = self.app.get("/api/v2.0/healthcheck")
        assert r.status_code == 200

        assert r.json is not None
        assert r.json.get("message") == "Health check OK"

    def test_healthcheck_fail(self):
        with patch("resultsdb.controllers.api_v2.db") as db:
            db.session.execute.side_effect = RuntimeError("Testing DB outage")
            r = self.app.get("/api/v2.0/healthcheck")
        assert r.status_code == 503

        assert r.json is not None
        assert r.json.get("message") == "Unable to communicate with database"
