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

import os
import sys


def db_uri_for_testing():
    postgres_port = os.getenv("POSTGRES_5432_TCP")
    if postgres_port:
        return f"postgresql+psycopg2://resultsdb:resultsdb@localhost:{postgres_port}/resultsdb"

    return "sqlite:///.test_db.sqlite"


class Config:
    DEFAULT_CONFIG_FILE: str | None = None

    DEBUG = True
    PRODUCTION = False
    SECRET_KEY = "replace-me-with-something-random"  # nosec

    HOST = "127.0.0.1"
    PORT = 5001

    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SHOW_DB_URI = True

    FLASK_PYDANTIC_VALIDATION_ERROR_RAISE = True

    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "loggers": {
            "resultsdb": {
                "level": "INFO",
            },
            "dogpile": {
                "level": "WARNING",
            },
        },
        "handlers": {
            "console": {
                "formatter": "bare",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "level": "INFO",
            },
        },
        "formatters": {
            "bare": {
                "format": "[%(asctime)s] [%(process)d] [%(levelname)s] %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        },
        "root": {
            "level": "WARNING",
            "handlers": ["console"],
        },
    }

    # Extend the list of allowed outcomes.
    ADDITIONAL_RESULT_OUTCOMES: tuple[str] | tuple[()] = ()

    PERMISSIONS: list[dict[str, object]] = []

    # Supported values: "oidc"
    AUTH_MODULE: str | None = None

    OIDC_CLIENT_SECRETS = "/etc/resultsdb/oauth2_client_secrets.json"
    OIDC_USERNAME_FIELD = "uid"
    OIDC_SESSION_REFRESH_INTERVAL_SECONDS = 300
    OIDC_SESSION_PERMANENT = False
    PERMANENT_SESSION_LIFETIME = 300

    SESSION_TYPE = "sqlalchemy"
    SESSION_SQLALCHEMY_TABLE = "sessions"
    SESSION_PERMANENT = True
    SESSION_USE_SIGNER = True
    SESSION_COOKIE_NAME = "session"
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "Lax"

    FEDMENU_URL = "https://apps.fedoraproject.org/fedmenu"
    FEDMENU_DATA_URL = "https://apps.fedoraproject.org/js/data.js"

    # Set this to True or False to enable publishing to a message bus
    MESSAGE_BUS_PUBLISH = True
    # Name of the message bus plugin to use goes here.  'fedmsg' is installed by
    # default, but you could create your own.
    # Supported values: 'dummy', 'stomp', 'fedmsg'
    MESSAGE_BUS_PLUGIN = "dummy"
    # You can pass extra arguments to your message bus plugin here.  For instance,
    # the fedmsg plugin expects an extra `modname` argument that can be used to
    # configure the topic, like this:
    #   <topic_prefix>.<environment>.<modname>.<topic>
    # e.g. org.fedoraproject.prod.resultsdb.result.new
    MESSAGE_BUS_KWARGS: dict[str, object] = {}

    # Publish Taskotron-compatible fedmsgs on the 'taskotron' topic
    MESSAGE_BUS_PUBLISH_TASKOTRON = False
    OTEL_EXPORTER_OTLP_METRICS_ENDPOINT = None
    OTEL_EXPORTER_SERVICE_NAME = "resultsdb"


class ProductionConfig(Config):
    DEFAULT_CONFIG_FILE = "/etc/resultsdb/settings.py"
    DEBUG = False
    PRODUCTION = True
    SHOW_DB_URI = False
    MESSAGE_BUS_PLUGIN = "fedmsg"
    MESSAGE_BUS_KWARGS = {"modname": "resultsdb"}


class DevelopmentConfig(Config):
    DEFAULT_CONFIG_FILE = os.getcwd() + "/conf/settings.py"
    TRAP_BAD_REQUEST_ERRORS = True
    SQLALCHEMY_DATABASE_URI = "sqlite:////var/tmp/resultsdb_db.sqlite"
    OIDC_CLIENT_SECRETS = os.getcwd() + "/conf/oauth2_client_secrets.json.example"


class TestingConfig(Config):
    TRAP_BAD_REQUEST_ERRORS = True

    SQLALCHEMY_DATABASE_URI = db_uri_for_testing()

    FEDMENU_URL = "https://apps.stg.fedoraproject.org/fedmenu"
    FEDMENU_DATA_URL = "https://apps.stg.fedoraproject.org/js/data.js"
    ADDITIONAL_RESULT_OUTCOMES = ("AMAZING",)
    MESSAGE_BUS_PLUGIN = "dummy"
    MESSAGE_BUS_KWARGS = {}
    PERMISSIONS = [
        {
            "users": ["testuser1"],
            "testcases": ["testcase1"],
        }
    ]
    AUTH_MODULE = "oidc"
    LDAP_HOST = "ldap://ldap.example.com"
    LDAP_SEARCHES = [
        {
            "BASE": "ou=Groups,dc=example,dc=com",
            "SEARCH_STRING": "(memberUid={user})",
        }
    ]

    OIDC_CLIENT_SECRETS = os.getcwd() + "/conf/oauth2_client_secrets.json.example"


def openshift_config(config_object, openshift_production):
    # First, get db details from env
    try:
        config_object["SQLALCHEMY_DATABASE_URI"] = (
            "postgresql+psycopg2://{}:{}@{}:{}/{}".format(
                os.environ["POSTGRESQL_USER"],
                os.environ["POSTGRESQL_PASSWORD"],
                os.environ["POSTGRESQL_SERVICE_HOST"],
                os.environ["POSTGRESQL_SERVICE_PORT"],
                os.environ["POSTGRESQL_DATABASE"],
            )
        )
        config_object["SECRET_KEY"] = os.environ["SECRET_KEY"]
    except KeyError:
        print(
            "OpenShift mode enabled but required values couldn't be fetched. "
            "Check, if you have these variables defined in you env: "
            "(POSTGRESQL_[USER, PASSWORD, DATABASE, SERVICE_HOST, SERVICE_PORT], "
            "SECRET_KEY)",
            file=sys.stderr,
        )
        sys.exit(1)

    # Nuke out messaging, we don't support this in OpenShift mode
    # Inject settings.py and disable OpenShift mode if you need this
    config_object["MESSAGE_BUS_PLUGIN"] = "dummy"
    config_object["MESSAGE_BUS_KWARGS"] = {}

    if os.getenv("MESSAGE_BUS_PLUGIN") or os.getenv("MESSAGE_BUS_KWARGS"):
        print("It appears you've tried to set up messaging in OpenShift mode.")
        print(
            "This is not supported, you need to inject setting.py and disable "
            "OpenShift mode if you need messaging."
        )

    # Danger zone, keep this False out in the wild, always
    config_object["SHOW_DB_URI"] = False
