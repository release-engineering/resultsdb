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

import json
import datetime
import os
import tempfile
import copy

import resultsdb
from resultsdb import db
import resultsdb.cli
import resultsdb.messaging
from resultsdb.models.results import Result


class TestFuncApiV10(object):

    def setup_method(self, method):
        self.dbfile = tempfile.NamedTemporaryFile(delete=False)
        self.dbfile.close()
        resultsdb.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///%s' % self.dbfile.name
        resultsdb.app.config['MESSAGE_BUS_PUBLISH'] = True
        resultsdb.app.config['MESSAGE_BUS_PLUGIN'] = 'dummy'
        resultsdb.cli.initialize_db(destructive=True)
        self.app = resultsdb.app.test_client()

    def teardown_method(self, method):
        resultsdb.messaging.DummyPlugin.history = []
        db.session.remove()
        os.unlink(self.dbfile.name)

    def test_create_result(self):
        job_data = {
            'name': 'dist.rpmlint',
            'ref_url': 'https://taskotron.example.com/execdb/',
        }
        r = self.app.post('/api/v1.0/jobs', data=json.dumps(job_data), content_type='application/json')
        assert r.status_code == 201
        job_id = json.loads(r.data)['id']
        job_uuid = json.loads(r.data)['uuid']

        result_data = {
            'job_id': job_id,
            'outcome': 'FAILED',
            'testcase_name': 'dist.rpmlint',
            'summary': '78 errors, 150 warnings',
            'result_data': {
                'type': ['koji_build'],
                'item': ['openfst-1.6.6-1.fc28'],
            },
            'log_url': 'https://taskotron.example.com/artifacts/',
        }
        r = self.app.post('/api/v1.0/results', data=json.dumps(result_data), content_type='application/json')
        assert r.status_code == 201
        result_id = json.loads(r.data)['id']

        # Check that the result was stored in the database.
        result = db.session.query(Result).get(result_id)
        assert result.outcome == 'FAILED'

        # Check that a message was emitted.
        plugin = resultsdb.messaging.DummyPlugin
        assert len(plugin.history) == 1, plugin.history
        assert plugin.history[0]['data']['item'] == ['openfst-1.6.6-1.fc28']
        assert plugin.history[0]['data']['type'] == ['koji_build']
        assert plugin.history[0]['id'] == 1
        assert plugin.history[0]['outcome'] == 'FAILED'
        assert plugin.history[0]['groups'] == [job_uuid]
        assert plugin.history[0]['note'] == '78 errors, 150 warnings'
        assert plugin.history[0]['ref_url'] == 'https://taskotron.example.com/artifacts/'
        assert plugin.history[0]['testcase']['name'] == 'dist.rpmlint'
