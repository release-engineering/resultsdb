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

import json
import datetime
import os
import tempfile
import copy

import resultsdb
import resultsdb.cli
import resultsdb.controllers.api_v2 as apiv2
import resultsdb.messaging


class MyResultData(object):

    def __init__(self, key, value):
        self.key = key
        self.value = value


class MyResult(object):

    def __init__(self, id, testcase_name, outcome, item, item_type, arch, scenario):
        self.id = id
        self.testcase_name = testcase_name
        self.outcome = outcome
        self.data = [
            MyResultData('item', item),
            MyResultData('type', item_type),
            MyResultData('arch', arch),
            MyResultData('scenario', scenario),
        ]


class AboutTime(object):

    def __eq__(self, value):
        start = (datetime.datetime.utcnow() - datetime.timedelta(seconds=10)).isoformat()
        stop = (datetime.datetime.utcnow() + datetime.timedelta(seconds=10)).isoformat()
        return start <= value <= stop


class TestFuncCreateFedmsg():

    @classmethod
    def setup_class(cls):
        cls.dbfile = tempfile.NamedTemporaryFile(delete=False)
        cls.dbfile.close()
        resultsdb.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///%s' % cls.dbfile.name
        resultsdb.app.config['MESSAGE_BUS_PUBLISH'] = True
        resultsdb.app.config['MESSAGE_BUS_PLUGIN'] = 'dummy'

    @classmethod
    def teardown_class(cls):
        os.unlink(cls.dbfile.name)

    def setup_method(self, method):
        resultsdb.cli.initialize_db(destructive=True)
        self.app = resultsdb.app.test_client()
        self.ref_url_prefix = "http://localhost/api/v2.0"

        # Testcase data
        self.ref_testcase_name = "scratch.testing.mytestcase"

        # Group data
        self.ref_group_uuid = '3ce5f6d7-ce34-489b-ab61-325ce634eab5'

        # Result data
        self.ref_result_outcome = 'PASSED'
        self.ref_result_note = 'Result Note'
        self.ref_result_item = 'perl-Specio-0.25-1.fc26'
        self.ref_result_type = 'koji_build'
        self.ref_result_arch = 'x86_64'
        self.ref_result_scenario = 'x86_64.efi'
        self.ref_result_data = {
            'item': self.ref_result_item,
            'type': self.ref_result_type,
            'arch': self.ref_result_arch,
            'scenario': self.ref_result_scenario,
            'moo': ['boo', 'woof'],
        }
        self.ref_result_ref_url = 'http://example.com/testing.result'
        self.ref_result_obj = MyResult(
            0, self.ref_testcase_name, self.ref_result_outcome, self.ref_result_item,
            self.ref_result_type, self.ref_result_arch, self.ref_result_scenario)

    def teardown_method(self, method):
        # Reset this for each test.
        resultsdb.messaging.DummyPlugin.history = []

    def helper_create_result(self, outcome=None, groups=None, testcase=None, data=None):
        if outcome is None:
            outcome = self.ref_result_outcome
        if groups is None:
            groups = [self.ref_group_uuid]
        if testcase is None:
            testcase = self.ref_testcase_name
        if data is None:
            data = self.ref_result_data

        ref_data = json.dumps(dict(
            outcome=outcome,
            testcase=testcase,
            groups=groups,
            note=self.ref_result_note,
            data=data,
            ref_url=self.ref_result_ref_url,
        ))

        r = self.app.post('/api/v2.0/results', data=ref_data, content_type='application/json')
        data = json.loads(r.data)

        return r, data

    def test_get_prev_result_no_results(self):
        prev_result = apiv2.get_prev_result(self.ref_result_obj)
        assert prev_result is None

    def test_get_prev_result_exists(self):
        self.helper_create_result()
        prev_result = apiv2.get_prev_result(self.ref_result_obj)

        assert prev_result.id == 1
        assert prev_result.outcome == self.ref_result_outcome
        assert prev_result.testcase_name == self.ref_testcase_name
        for result_data in prev_result.data:
            if result_data.key == 'item':
                assert result_data.value == self.ref_result_item
            if result_data.key == 'type':
                assert result_data.value == self.ref_result_type
            if result_data.key == 'arch':
                assert result_data.value == self.ref_result_arch
            if result_data.key == 'scenario':
                assert result_data.value == self.ref_result_scenario

        self.helper_create_result()
        prev_result = apiv2.get_prev_result(self.ref_result_obj)

        assert prev_result.id == 2
        assert prev_result.outcome == self.ref_result_outcome
        assert prev_result.testcase_name == self.ref_testcase_name
        for result_data in prev_result.data:
            if result_data.key == 'item':
                assert result_data.value == self.ref_result_item
            if result_data.key == 'type':
                assert result_data.value == self.ref_result_type
            if result_data.key == 'arch':
                assert result_data.value == self.ref_result_arch
            if result_data.key == 'scenario':
                assert result_data.value == self.ref_result_scenario

        ref_outcome = 'FAILED'
        if self.ref_result_outcome == ref_outcome:
            ref_outcome = 'PASSED'
        self.helper_create_result(outcome=ref_outcome)
        prev_result = apiv2.get_prev_result(self.ref_result_obj)

        assert prev_result.id == 3
        assert prev_result.outcome == ref_outcome
        assert prev_result.testcase_name == self.ref_testcase_name
        for result_data in prev_result.data:
            if result_data.key == 'item':
                assert result_data.value == self.ref_result_item
            if result_data.key == 'type':
                assert result_data.value == self.ref_result_type
            if result_data.key == 'arch':
                assert result_data.value == self.ref_result_arch
            if result_data.key == 'scenario':
                assert result_data.value == self.ref_result_scenario

    def test_get_prev_result_different_item(self):
        data = copy.deepcopy(self.ref_result_data)
        data['item'] = data['item'] + '.fake'
        self.helper_create_result(data=data)

        prev_result = apiv2.get_prev_result(self.ref_result_obj)
        assert prev_result is None

    def test_get_prev_result_different_type(self):
        data = copy.deepcopy(self.ref_result_data)
        data['type'] = data['type'] + '.fake'
        self.helper_create_result(data=data)

        prev_result = apiv2.get_prev_result(self.ref_result_obj)
        assert prev_result is None

    def test_get_prev_result_different_arch(self):
        data = copy.deepcopy(self.ref_result_data)
        data['arch'] = data['arch'] + '.fake'
        self.helper_create_result(data=data)

        prev_result = apiv2.get_prev_result(self.ref_result_obj)
        assert prev_result is None

    def test_get_prev_result_different_scenario(self):
        data = copy.deepcopy(self.ref_result_data)
        data['scenario'] = data['scenario'] + '.fake'
        self.helper_create_result(data=data)

        prev_result = apiv2.get_prev_result(self.ref_result_obj)
        assert prev_result is None

    def test_get_prev_result_different_testcase_name(self):
        self.helper_create_result(testcase={'name': self.ref_testcase_name + '.fake'})

        prev_result = apiv2.get_prev_result(self.ref_result_obj)
        assert prev_result is None

    def test_message_publication(self):
        self.helper_create_result()
        plugin = resultsdb.messaging.DummyPlugin
        assert len(plugin.history) == 1, plugin.history
        assert plugin.history == [{'id': 1}]
