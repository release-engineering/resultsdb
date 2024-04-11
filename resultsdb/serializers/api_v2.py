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

from flask import url_for

from resultsdb.models.results import GroupsToResults
from resultsdb.serializers import BaseSerializer


class Serializer(BaseSerializer):
    def _serialize_Group(self, o, **kwargs):
        rv = dict(
            uuid=o.uuid,
            description=o.description,
            ref_url=o.ref_url,
            results=url_for("api_v2.get_results", groups=[o.uuid], _external=True),
            results_count=GroupsToResults.query.filter_by(group_uuid=o.uuid).count(),
            href=url_for("api_v2.get_group", group_id=o.uuid, _external=True),
        )

        return {key: self.serialize(value) for key, value in rv.items()}

    def _serialize_Testcase(self, o, **kwargs):
        rv = dict(
            name=o.name,
            ref_url=o.ref_url,
            href=url_for("api_v2.get_testcase", testcase_name=o.name, _external=True),
        )

        return {key: self.serialize(value) for key, value in rv.items()}

    def _serialize_Result(self, o, **kwargs):
        result_data = {}
        for rd in o.data:
            try:
                result_data[rd.key].append(rd.value)
            except KeyError:
                result_data[rd.key] = [rd.value]

        rv = dict(
            id=o.id,
            groups=[group.uuid for group in o.groups],
            testcase=o.testcase,
            submit_time=o.submit_time.isoformat(),
            outcome=o.outcome,
            note=o.note,
            ref_url=o.ref_url,
            data=result_data,
            href=url_for("api_v2.get_result", result_id=o.id, _external=True),
        )

        return {key: self.serialize(value) for key, value in rv.items()}

    def _serialize_ResultData(self, o, **kwargs):
        rv = dict(
            key=o.key,
            value=o.value,
        )

        return {key: self.serialize(value) for key, value in rv.items()}
