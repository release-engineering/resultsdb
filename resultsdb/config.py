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

    HOST = None
    PORT = None

    PRODUCTION = False

    SHOW_DB_URI = False


class ProductionConfig(Config):
    DEBUG = False
    PRODUCTION = True


class DevelopmentConfig(Config):
    TRAP_BAD_REQUEST_ERRORS = True
    SQLALCHEMY_DATABASE_URI = \
        'mysql://resultsdb:TOP_SECRET_PASSWORD@localhost/resultsdb'
    HOST = '0.0.0.0'
    PORT = 5000


class TestingConfig(Config):
    TRAP_BAD_REQUEST_ERRORS = True
    TESTING = True
