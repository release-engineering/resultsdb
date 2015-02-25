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

from resultsdb.serializers import DBSerialize, BaseSerializer

class Serializer(BaseSerializer):

    def __init__(self, uri_generator):
        self.get_uri = uri_generator

    def _serialize_Job(self, o, job_load_results = True, **kwargs):
        rv = dict(
                id = o.id,
                uuid = o.uuid,
                name = o.name,
                status = o.status,
                start_time = o.start_time,
                end_time = o.end_time,
                ref_url = o.ref_url,
                results = None,
                results_count = len(o.results), # find out how to make this fast
                href = self.get_uri(o),
                )
        if job_load_results:
                rv['results'] = o.results

        return {key: self.serialize(value) for key, value in rv.iteritems()}


    def _serialize_Testcase(self, o, **kwargs):
        rv = dict(
                name = o.name,
                url = o.url,
                href = self.get_uri(o)
                )

        return {key: self.serialize(value) for key, value in rv.iteritems()}

    def _serialize_Result(self, o, **kwargs):
        result_data = {}
        for rd in o.result_data:
            try:
                result_data[rd.key].append(rd.value)
            except KeyError:
                result_data[rd.key] = [rd.value]

        rv = dict(
                id = o.id,
                job_url = self.get_uri(o.job),
                testcase = o.testcase,
                submit_time = o.submit_time,
                outcome = o.outcome,
                summary = o.summary,
                log_url = o.log_url,
                result_data = result_data,
                href = self.get_uri(o),
                )

        return {key: self.serialize(value) for key, value in rv.iteritems()}

    def _serialize_ResultData(self, o, **kwargs):
        rv = dict(
                key = o.key,
                value = o.value,
                )

        return {key: self.serialize(value) for key, value in rv.iteritems()}
