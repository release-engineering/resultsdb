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
import os


class Config(object):
    DEBUG = True
    PRODUCTION = False
    SECRET_KEY = 'replace-me-with-something-random'

    HOST = '0.0.0.0'
    PORT = 5001

    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    SHOW_DB_URI = True

    LOGFILE = '/var/log/resultsdb/resultsdb.log'
    FILE_LOGGING = False
    SYSLOG_LOGGING = False
    STREAM_LOGGING = True

    # Specify which fields are required (in addition to those already required)
    #  when creating result/group/testcase.
    # If you want to set some result's extra-data as required, you can do so by
    #  prepending 'data.' to the name (e.g. 'data.arch').
    REQUIRED_DATA = {
        'create_result': [],
        'create_group': [],
        'create_testcase': [],
        }

    # Supported values: "oidc"
    AUTH_MODULE = None

    # OIDC Configuration
    OIDC_ADMINS = [] # should contain list of usernames that can do POSTs e.g. ['tflink', 'kparal']
    OIDC_CLIENT_SECRETS = '/etc/resultsdb/oauth2_client_secrets.json'
    OIDC_AUD = 'My-Client-ID'
    OIDC_SCOPE = 'https://pagure.io/taskotron/resultsdb/access'
    OIDC_RESOURCE_SERVER_ONLY = True

    FEDMENU_URL = 'https://apps.fedoraproject.org/fedmenu'
    FEDMENU_DATA_URL = 'https://apps.fedoraproject.org/js/data.js'

    # Set this to True or False to enable publishing to a message bus
    MESSAGE_BUS_PUBLISH = True
    # Name of the message bus plugin to use goes here.  'fedmsg' is installed by
    # default, but you could create your own.
    # Supported values: 'dummy', 'stomp', 'fedmsg'
    MESSAGE_BUS_PLUGIN = 'dummy'
    # You can pass extra arguments to your message bus plugin here.  For instance,
    # the fedmsg plugin expects an extra `modname` argument that can be used to
    # configure the topic, like this:
    #   <topic_prefix>.<environment>.<modname>.<topic>
    # e.g. org.fedoraproject.prod.taskotron.result.new
    MESSAGE_BUS_KWARGS = {}

    ## Alternatively, you could use the 'stomp' messaging plugin.
    #MESSAGE_BUS_PLUGIN = 'stomp'
    #MESSAGE_BUS_KWARGS = {
    #    'destination': 'topic://VirtualTopic.eng.resultsdb.result.new',
    #    'connection': {
    #        'host_and_ports': [
    #            ('broker01', '61612'),
    #            ('broker02', '61612'),
    #        ],
    #        'use_ssl': True,
    #        'ssl_key_file': '/path/to/key/file',
    #        'ssl_cert_file': '/path/to/cert/file',
    #        'ssl_ca_certs': '/path/to/ca/certs',
    #    },
    #}


class ProductionConfig(Config):
    DEBUG = False
    PRODUCTION = True
    SHOW_DB_URI = False
    MESSAGE_BUS_PLUGIN = 'fedmsg'
    MESSAGE_BUS_KWARGS = {'modname': 'resultsdb'}


class DevelopmentConfig(Config):
    TRAP_BAD_REQUEST_ERRORS = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:////var/tmp/resultsdb_db.sqlite'
    OIDC_CLIENT_SECRETS = os.getcwd() + '/conf/oauth2_client_secrets.json.example'


class TestingConfig(Config):
    TRAP_BAD_REQUEST_ERRORS = True
    FEDMENU_URL = 'https://apps.stg.fedoraproject.org/fedmenu'
    FEDMENU_DATA_URL = 'https://apps.stg.fedoraproject.org/js/data.js'
