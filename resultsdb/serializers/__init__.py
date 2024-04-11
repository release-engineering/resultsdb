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

from datetime import date, datetime


class DBSerialize:
    pass


class BaseSerializer:
    def serialize(self, value, **kwargs):
        # serialize the database objects
        #   the specific serializer needs to implement serialize_CLASSNAME methods
        if DBSerialize in value.__class__.__bases__:
            return getattr(self, f"_serialize_{value.__class__.__name__}")(
                value, **kwargs
            )

        # convert datetimes to the right format
        if type(value) in (datetime, date):
            return value.isoformat()

        if isinstance(value, dict):
            ret = {}
            for k, v in value.items():
                ret[k] = self.serialize(v, **kwargs)
            return ret

        # in py3 string-like types have __iter__ causing endless loops
        if isinstance(value, (str, bytes)):
            return value

        # convert iterables to list of serialized stuff
        if hasattr(value, "__iter__"):
            ret = []
            for v in value:
                ret.append(self.serialize(v, **kwargs))
            return ret

        return value
