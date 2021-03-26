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

# For Python 2.7 compatibility
from __future__ import print_function

import os
import sys


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

    # Extend the list of allowed outcomes.
    ADDITIONAL_RESULT_OUTCOMES = ()

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
    # e.g. org.fedoraproject.prod.resultsdb.result.new
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

    # Publish Taskotron-compatible fedmsgs on the 'taskotron' topic
    MESSAGE_BUS_PUBLISH_TASKOTRON = False


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
    ADDITIONAL_RESULT_OUTCOMES = ('AMAZING',)
    MESSAGE_BUS_PLUGIN = 'dummy'
    MESSAGE_BUS_KWARGS = {}


def openshift_config(config_object, openshift_production):
    # First, get db details from env
    try:
        config_object["SQLALCHEMY_DATABASE_URI"] = "postgresql+psycopg2://%s:%s@%s:%s/%s" % (
            os.environ["POSTGRESQL_USER"],
            os.environ["POSTGRESQL_PASSWORD"],
            os.environ["POSTGRESQL_SERVICE_HOST"],
            os.environ["POSTGRESQL_SERVICE_PORT"],
            os.environ["POSTGRESQL_DATABASE"]
        )
        config_object["SECRET_KEY"] = os.environ["SECRET_KEY"]
    except KeyError:
        print("OpenShift mode enabled but required values couldn't be fetched. "
              "Check, if you have these variables defined in you env: "
              "(POSTGRESQL_[USER, PASSWORD, DATABASE, SERVICE_HOST, SERVICE_PORT], "
              "SECRET_KEY)", file=sys.stderr)
        sys.exit(1)

    # Nuke out messaging, we don't support this in OpenShift mode
    # Inject settings.py and disable OpenShift mode if you need this
    config_object["MESSAGE_BUS_PLUGIN"] = 'dummy'
    config_object["MESSAGE_BUS_KWARGS"] = {}

    if os.getenv("MESSAGE_BUS_PLUGIN") or os.getenv("MESSAGE_BUS_KWARGS"):
        print("It appears you've tried to set up messaging in OpenShift mode.")
        print("This is not supported, you need to inject setting.py and disable "
              "OpenShift mode if you need messaging.")

    # Danger zone, keep this False out in the wild, always
    config_object["SHOW_DB_URI"] = False
