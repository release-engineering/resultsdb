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
#   Martin Krizek <mkrizek@redhat.com>


import os
import tempfile

import resultsdb
import resultsdb.cli

from resultsdb import db
from resultsdb.models.results import Testcase, Job, Result, ResultData
from resultsdb.controllers.api_v1 import is_duplicate_result


class TestFuncDuplicateResult():
    @classmethod
    def setup_class(cls):
        cls.dbfile = tempfile.NamedTemporaryFile(delete=False)
        cls.dbfile.close()
        resultsdb.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///%s' % cls.dbfile.name

    @classmethod
    def teardown_class(cls):
        os.unlink(cls.dbfile.name)

    def setup_method(self, method):
        resultsdb.cli.initialize_db(destructive=True)

        self.ref_testcase_name = "testcase"
        self.ref_testcase_url = "http://fedoraqa.fedoraproject.org/%s" % self.ref_testcase_name
        self.ref_job_uuid = '12-3456-7890'
        self.ref_job_url = "http://fedoraqa.fedoraproject.org"
        self.ref_job_name = "F20 Virtualization Testday"
        self.ref_status = "SCHEDULED"
        self.ref_outcome = "PASSED"
        self.ref_result_summary = "1 PASSED, 0 FAILED"
        self.ref_result_log_url = "http://fedoraqa.fedoraproject.org/logs"
        self.ref_item = 'chat-2.8.8-21.fc20'
        self.ref_type = 'koji_build'
        self.ref_arch = 'x86_64'

        self.testcase = Testcase(self.ref_testcase_name, self.ref_testcase_url)
        db.session.add(self.testcase)
        db.session.commit()

        self.job = Job(self.ref_status, self.ref_job_url, self.ref_job_name, self.ref_job_uuid)
        db.session.add(self.job)
        db.session.commit()

        self.create_result(self.testcase, self.ref_outcome, self.ref_item, self.ref_arch)

    def create_result(self, testcase, outcome, item=None, arch=None):
        result = Result(self.job,
                        testcase,
                        outcome,
                        self.ref_result_log_url,
                        self.ref_result_summary)

        if item:
            ResultData(result, 'item', item)

        ResultData(result, 'type', self.ref_type)

        if arch:
            ResultData(result, 'arch', arch)

        db.session.add(result)
        db.session.commit()

        return result

    def test_duplicate_result(self):
        result = self.create_result(self.testcase, self.ref_outcome, self.ref_item, self.ref_arch)

        assert is_duplicate_result(result)

    def test_duplicate_result_more_results(self):
        result = self.create_result(self.testcase, self.ref_outcome, self.ref_item, self.ref_arch)
        self.create_result(self.testcase, self.ref_outcome, 'item1', 'arch1')
        self.create_result(self.testcase, self.ref_outcome, 'item2', 'arch2')
        self.create_result(self.testcase, self.ref_outcome, 'item3', 'arch3')

        assert is_duplicate_result(result)

    def test_not_duplicate_result_item(self):
        result = self.create_result(self.testcase, self.ref_outcome, item='chat-2.8.8-21.fc21', arch=self.ref_arch)

        assert not is_duplicate_result(result)

    def test_not_duplicate_result_arch(self):
        result = self.create_result(self.testcase, self.ref_outcome, item=self.ref_item, arch='i686')

        assert not is_duplicate_result(result)

    def test_not_duplicate_result_testcase(self):
        testcase = Testcase('random_testcase_unique', 'random_testcase_unique_url')
        db.session.add(testcase)
        db.session.commit()

        result = self.create_result(testcase, self.ref_outcome, self.ref_item, self.ref_arch)

        assert not is_duplicate_result(result)

    def test_not_duplicate_result_outcome(self):
        result = self.create_result(self.testcase, 'FAILED', self.ref_item, self.ref_arch)

        assert not is_duplicate_result(result)
