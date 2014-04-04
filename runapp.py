#!/usr/bin/python
#
# runapp.py - script to facilitate running the resultsdb app from the CLI
#
# Copyright 2013-2014, Red Hat, Inc
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
#   Tim Flink <tflink@redhat.com>
#   Ralph Bean <rbean@redhat.com>


import resultsdb

if __name__ == '__main__':
    resultsdb.app.run(
        host=resultsdb.app.config['HOST'],
        port=resultsdb.app.config['PORT'],
        debug=resultsdb.app.config['DEBUG'],
    )
