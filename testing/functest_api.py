# Copyright 2014, Red Hat, Inc.
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

import json
import datetime
import os
import tempfile

import resultsdb
import resultsdb.cli

class TestFuncApi():
    @classmethod
    def setup_class(cls):
        cls.dbfile = tempfile.NamedTemporaryFile(delete=False)
        cls.dbfile.close()
        resultsdb.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///%s' % cls.dbfile.name

    @classmethod
    def teardown_class(cls):
        os.unlink(cls.dbfile.name)

    def setup_method(self, method):
        self.app = resultsdb.app.test_client()
        resultsdb.cli.initialize_db(destructive=True)

        self.ref_testcase_name = "testcase"
        self.ref_testcase_url = "http://fedoraqa.fedoraproject.org/%s" % self.ref_testcase_name
        self.ref_job_id = 1
        self.ref_job_uuid = '12-3456-7890'
        self.ref_job_url = "http://fedoraqa.fedoraproject.org"
        self.ref_job_name = "F20 Virtualization Testday"
        self.ref_status = "SCHEDULED"
        self.ref_outcome = "PASSED"
        self.ref_result_id = 1
        self.ref_result_data = {'data': 'fakedata', 'data1': ['fakedata1'], 'data2': 1}
        self.ref_result_summary = "1 PASSED, 0 FAILED"
        self.ref_result_log_url = "http://fedoraqa.fedoraproject.org/logs"

    def test_create_testcase(self):
        ref_data = json.dumps({'name': self.ref_testcase_name, 'url': self.ref_testcase_url})

        r = self.app.post('/api/v1.0/testcases', data=ref_data, content_type='application/json')

        data = json.loads(r.data)

        assert r.status_code == 201
        assert data['name'] == self.ref_testcase_name
        assert data['url'] == self.ref_testcase_url

    def test_create_duplicate_testcase(self):
        self.test_create_testcase()

        ref_data = json.dumps({'name': self.ref_testcase_name, 'url': self.ref_testcase_url})


        r = self.app.post('/api/v1.0/testcases', data=ref_data, content_type='application/json')

        data = json.loads(r.data)

        assert r.status_code == 400
        assert data['message'] == "Testcase with this name already exists"

    def test_update_testcase(self):
        self.test_create_testcase()

        ref_data = json.dumps({'url': self.ref_testcase_url})

        r = self.app.put('/api/v1.0/testcases/%s' % self.ref_testcase_name, data=ref_data, content_type='application/json')

        data = json.loads(r.data)

        assert r.status_code == 200
        assert data['name'] == self.ref_testcase_name
        assert data['url'] == self.ref_testcase_url

    def test_update_invalid_testcase(self):
        ref_data = json.dumps({'url': self.ref_testcase_url})

        r = self.app.put('/api/v1.0/testcases/%s' % self.ref_testcase_name, data=ref_data, content_type='application/json')

        data = json.loads(r.data)

        assert r.status_code == 404
        assert data['message'] == "Testcase not found"

    def test_get_testcase(self):
        self.test_create_testcase()

        r = self.app.get('/api/v1.0/testcases/%s' % self.ref_testcase_name)

        data = json.loads(r.data)

        assert r.status_code == 200
        assert data['name'] == self.ref_testcase_name
        assert data['url'] == self.ref_testcase_url

    def test_get_invalid_testcase(self):
        r = self.app.get('/api/v1.0/testcases/%s' % self.ref_testcase_name)

        data = json.loads(r.data)

        assert r.status_code == 404
        assert data['message'] == "Testcase not found"

    def test_get_testcases(self):
        self.test_create_testcase()

        r = self.app.get('/api/v1.0/testcases')

        data = json.loads(r.data)

        assert r.status_code == 200
        assert data['data'][0]['name'] == self.ref_testcase_name
        assert data['data'][0]['url'] == self.ref_testcase_url

    def test_get_empty_testcases(self):
        r = self.app.get('/api/v1.0/testcases')

        data = json.loads(r.data)

        assert r.status_code == 200
        assert data['data'] == []

    def test_create_job(self):
        ref_data = json.dumps({
            'ref_url': self.ref_job_url,
            'status': self.ref_status,
            'name': self.ref_job_name,
            'uuid': self.ref_job_uuid,
            })

        r = self.app.post('/api/v1.0/jobs', data=ref_data, content_type='application/json')

        data = json.loads(r.data)

        assert r.status_code == 201
        assert data['ref_url'] == self.ref_job_url
        assert data['status'] == self.ref_status
        assert data['uuid'] == self.ref_job_uuid

    def test_create_invalid_job(self):
        ref_data = json.dumps({'ref_url': self.ref_job_url, 'status': 'INVALIDFAKE'})

        r = self.app.post('/api/v1.0/jobs', data=ref_data, content_type='application/json')

        data = json.loads(r.data)

        assert r.status_code == 400
        assert data['message'].startswith("status must be one of")

    def test_update_job(self):
        self.test_create_job()

        ref_status = "RUNNING"
        ref_data = json.dumps({'status': ref_status})

        r = self.app.put('/api/v1.0/jobs/%d' % self.ref_job_id, data=ref_data, content_type='application/json')

        data = json.loads(r.data)

        assert r.status_code == 200
        assert data['status'] == ref_status
        assert data['start_time'] is not None

    def test_update_job_to_completed(self):
        self.test_create_job()

        ref_status = "COMPLETED"
        ref_data = json.dumps({'status': ref_status})

        r = self.app.put('/api/v1.0/jobs/%d' % self.ref_job_id, data=ref_data, content_type='application/json')

        data = json.loads(r.data)

        assert r.status_code == 200
        assert data['status'] == ref_status
        assert data['start_time'] is not None
        assert data['end_time'] is not None

    def test_update_invalid_job(self):
        ref_status = "RUNNING"
        ref_data = json.dumps({'status': ref_status})

        r = self.app.put('/api/v1.0/jobs/%d' % self.ref_job_id, data=ref_data, content_type='application/json')

        data = json.loads(r.data)

        assert r.status_code == 404
        assert data['message'] == "Job not found"

    def test_update_invalid_status_job(self):
        self.test_create_job()

        ref_status = "INVALIDFAKE"
        ref_data = json.dumps({'status': ref_status})

        r = self.app.put('/api/v1.0/jobs/%d' % self.ref_job_id, data=ref_data, content_type='application/json')

        data = json.loads(r.data)

        assert r.status_code == 400
        assert data['message'].startswith("status must be one of")

    def test_get_job(self):
        self.test_create_job()

        r = self.app.get('/api/v1.0/jobs/%d' % self.ref_job_id)

        data = json.loads(r.data)

        assert r.status_code == 200
        assert data['id'] == self.ref_job_id
        assert data['status'] == self.ref_status

    def test_get_job_uuid(self):
        self.test_create_job()

        r = self.app.get('/api/v1.0/jobs/%s' % self.ref_job_uuid)

        data = json.loads(r.data)

        assert r.status_code == 200
        assert data['id'] == self.ref_job_id
        assert data['status'] == self.ref_status

    def test_get_invalid_job(self):
        r = self.app.get('/api/v1.0/jobs/%d' % self.ref_job_id)

        data = json.loads(r.data)

        assert r.status_code == 404
        assert data['message'] == "Job not found"

    def test_get_invalid_job_uuid(self):
        r = self.app.get('/api/v1.0/jobs/%s' % self.ref_job_uuid)

        data = json.loads(r.data)

        assert r.status_code == 404
        assert data['message'] == "Job not found"

    def test_get_jobs(self):
        self.test_create_job()

        r = self.app.get('/api/v1.0/jobs')

        data = json.loads(r.data)

        assert r.status_code == 200
        assert data['data'][0]['id'] == self.ref_job_id
        assert data['data'][0]['status'] == self.ref_status

    def test_get_jobs_params(self):
        self.test_create_job()

        ref_data = json.dumps({'page': 0,
                                'limit': 10,
                                'status': self.ref_status,
                                'since': datetime.datetime(1970, 1, 1).isoformat(' ')})

        r = self.app.get('/api/v1.0/jobs', data=ref_data)

        data = json.loads(r.data)

        assert r.status_code == 200
        assert data['data'][0]['id'] == self.ref_job_id
        assert data['data'][0]['status'] == self.ref_status

    def test_get_empty_jobs(self):
        r = self.app.get('/api/v1.0/jobs')

        data = json.loads(r.data)

        assert r.status_code == 200
        assert data['data'] == []

    def test_create_result(self):
        self.test_create_testcase()
        self.test_create_job()
        self.test_update_job()

        ref_data = json.dumps({'outcome': self.ref_outcome,
                                'job_id': self.ref_job_id,
                                'testcase_name': self.ref_testcase_name,
                                'result_data': self.ref_result_data,
                                'summary': self.ref_result_summary,
                                'log_url': self.ref_result_log_url})

        r = self.app.post('/api/v1.0/results', data=ref_data, content_type='application/json')

        data = json.loads(r.data)

        assert r.status_code == 201
        assert data['outcome'] == self.ref_outcome
        assert data['id'] == self.ref_job_id
        assert data['testcase']['name'] == self.ref_testcase_name

    def test_create_invalid_job_result(self):
        self.test_create_testcase()
        # not creating any jobs

        ref_data = json.dumps({'outcome': self.ref_outcome, 'job_id': self.ref_job_id, 'testcase_name': self.ref_testcase_name})

        r = self.app.post('/api/v1.0/results', data=ref_data, content_type='application/json')

        data = json.loads(r.data)

        assert r.status_code == 404
        assert data['message'] == "Job not found"

    def test_create_invalid_outcome_result(self):
        self.test_create_testcase()
        self.test_create_job()
        self.test_update_job()

        ref_data = json.dumps({'outcome': 'FAKEOUTCOME', 'job_id': self.ref_job_id, 'testcase_name': self.ref_testcase_name})

        r = self.app.post('/api/v1.0/results', data=ref_data, content_type='application/json')

        data = json.loads(r.data)

        assert r.status_code == 400
        assert data['message'].startswith("outcome must be one of")

    def test_create_invalid_result(self):
        self.test_create_testcase()
        self.test_create_job() # create SCHEDULED job

        ref_data = json.dumps({'outcome': self.ref_outcome, 'job_id': self.ref_job_id, 'testcase_name': self.ref_testcase_name})

        r = self.app.post('/api/v1.0/results', data=ref_data, content_type='application/json')

        data = json.loads(r.data)

        assert r.status_code == 400
        assert data['message'] == "Job not running"

    def test_get_result(self):
        self.test_create_result()

        r = self.app.get('/api/v1.0/results/%d' % self.ref_result_id)

        data = json.loads(r.data)

        assert r.status_code == 200
        assert data['outcome'] == self.ref_outcome
        assert data['id'] == self.ref_job_id
        assert data['testcase']['name'] == self.ref_testcase_name

    def test_get_invalid_result(self):
        r = self.app.get('/api/v1.0/results/%d' % self.ref_result_id)

        data = json.loads(r.data)

        assert r.status_code == 404
        assert data['message'] == "Result not found"

    def test_get_results(self):
        self.test_create_result()

        r = self.app.get('/api/v1.0/results')

        data = json.loads(r.data)

        assert r.status_code == 200
        assert data['data'][0]['outcome'] == self.ref_outcome
        assert data['data'][0]['id'] == self.ref_job_id
        assert data['data'][0]['testcase']['name'] == self.ref_testcase_name

    def test_get_empty_results(self):
        r = self.app.get('/api/v1.0/results')

        data = json.loads(r.data)

        assert r.status_code == 200
        assert data['data'] == []

    def test_get_testcases_results(self):
        self.test_create_result()

        r = self.app.get('/api/v1.0/testcases/%s/results' % self.ref_testcase_name)

        data = json.loads(r.data)

        assert r.status_code == 200
        assert data['data'][0]['outcome'] == self.ref_outcome
        assert data['data'][0]['id'] == self.ref_job_id
        assert data['data'][0]['testcase']['name'] == self.ref_testcase_name

    def test_get_testcases_empty_results(self):
        r = self.app.get('/api/v1.0/testcases/%s/results' % self.ref_testcase_name)

        data = json.loads(r.data)

        assert r.status_code == 404
        assert data['message'] == "Testcase not found"

    def test_get_jobs_results(self):
        self.test_create_result()

        r = self.app.get('/api/v1.0/testcases/%s/results' % self.ref_testcase_name)

        data = json.loads(r.data)

        assert r.status_code == 200
        assert data['data'][0]['outcome'] == self.ref_outcome
        assert data['data'][0]['id'] == self.ref_job_id
        assert data['data'][0]['testcase']['name'] == self.ref_testcase_name

    def test_get_jobs_empty_results(self):
        r = self.app.get('/api/v1.0/jobs/%s/results' % self.ref_job_id)

        data = json.loads(r.data)

        assert r.status_code == 404
        assert data['message'] == "Job not found"

    def test_get_jobs_results_with_jsonp(self):
        self.test_create_result()

        r = self.app.get('/api/v1.0/testcases/%s/results?callback=wat' % self.ref_testcase_name)

        assert r.data.startswith('wat(')
        data = json.loads(r.data[4:-2])

        assert r.status_code == 200
        assert data['data'][0]['outcome'] == self.ref_outcome
        assert data['data'][0]['id'] == self.ref_job_id
        assert data['data'][0]['testcase']['name'] == self.ref_testcase_name
