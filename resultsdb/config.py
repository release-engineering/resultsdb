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
#   Ralph Bean <rbean@redhat.com>


class Config(object):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'

    LOGFILE = '/var/log/resultsdb/resultsdb.log'
    FILE_LOGGING = False
    SYSLOG_LOGGING = False
    STREAM_LOGGING = True

    HOST = '0.0.0.0'
    PORT = 5001

    PRODUCTION = False

    SHOW_DB_URI = False

    FEDMENU_URL = 'https://apps.fedoraproject.org/fedmenu'
    FEDMENU_DATA_URL = 'https://apps.fedoraproject.org/js/data.js'


class ProductionConfig(Config):
    DEBUG = False
    PRODUCTION = True


class DevelopmentConfig(Config):
    TRAP_BAD_REQUEST_ERRORS = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:////var/tmp/resultsdb_db.sqlite'
    SHOW_DB_URI = True


class TestingConfig(Config):
    TRAP_BAD_REQUEST_ERRORS = True
    TESTING = True
    FEDMENU_URL = 'https://apps.stg.fedoraproject.org/fedmenu'
    FEDMENU_DATA_URL = 'https://apps.stg.fedoraproject.org/js/data.js'
