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

class DBSerialize(object):
    pass

class BaseSerializer(object):

   def serialize(self, value):
        # serialize the database objects
        #   the specific serializer needs to implement serialize_CLASSNAME methods
        if DBSerialize in value.__class__.__bases__:
            return getattr(self, '_serialize_%s' % value.__class__.__name__)(value)

        # convert datetimes to the right format
        if type(value) in (datetime, date):
            return value.isoformat()

        if isinstance(value, dict):
            ret = {}
            for k, v  in value.iteritems():
                ret[k] = self.serialize(v)
            return ret

        # convert iterables to list of serialized stuff
        if hasattr(value, '__iter__'):
            ret = []
            for v in value:
                ret.append(self.serialize(v))
            return ret

        return value

