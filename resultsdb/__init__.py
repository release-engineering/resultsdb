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
#   Josef Skladanka <jskladan@redhat.com>
#   Ralph Bean <rbean@redhat.com>

import logging
import logging.handlers
import logging.config as logging_config
import os

from resultsdb import proxy
from . import config

import flask
from flask import Flask
from flask_sqlalchemy import SQLAlchemy


# the version as used in setup.py
__version__ = "2.2.0"

try:
    basestring
except NameError:
    basestring = (str, bytes)


# Flask App
app = Flask(__name__)
app.secret_key = 'replace-me-with-something-random'

# make sure app behaves when behind a proxy
app.wsgi_app = proxy.ReverseProxied(app.wsgi_app)

# Monkey patch Flask's "jsonify" to also handle JSONP
original_jsonify = flask.jsonify

# Expose the __version__ variable in templates
app.jinja_env.globals['app_version'] = __version__


def jsonify_with_jsonp(*args, **kwargs):
    response = original_jsonify(*args, **kwargs)

    callback = flask.request.args.get('callback', None)

    if callback:
        if not isinstance(callback, basestring):
            callback = callback[0]
        response.mimetype = 'application/javascript'
        response.set_data('%s(%s);' % (callback, response.get_data()))

    return response

flask.jsonify = jsonify_with_jsonp

# Checks for env variable OPENSHIFT_PROD to trigger OpenShift codepath on init
# The main difference is that settings will be queried from env (check config.openshift_config())
# Possible values are:
# "1" - OpenShift production deployment
# "0" - OpenShift testing deployment
openshift = os.getenv('OPENSHIFT_PROD')

# Load default config, then override that with a config file
if os.getenv('DEV') == 'true':
    default_config_obj = 'resultsdb.config.DevelopmentConfig'
    default_config_file = os.getcwd() + '/conf/settings.py'
elif os.getenv('TEST') == 'true' or openshift == "0":
    default_config_obj = 'resultsdb.config.TestingConfig'
    default_config_file = ''
else:
    default_config_obj = 'resultsdb.config.ProductionConfig'
    default_config_file = '/etc/resultsdb/settings.py'

app.config.from_object(default_config_obj)

if openshift:
    config.openshift_config(app.config, openshift)

config_file = os.environ.get('RESULTSDB_CONFIG', default_config_file)
if os.path.exists(config_file):
    app.config.from_pyfile(config_file)

if app.config['PRODUCTION']:
    if app.secret_key == 'replace-me-with-something-random':
        raise Warning("You need to change the app.secret_key value for production")


def setup_logging():
    # Use LOGGING if defined instead of the old options
    log_config = app.config.get('LOGGING')
    if log_config:
        logging_config.dictConfig(log_config)
        return

    fmt = '[%(filename)s:%(lineno)d] ' if app.debug else '%(module)-12s '
    fmt += '%(asctime)s %(levelname)-7s %(message)s'
    datefmt = '%Y-%m-%d %H:%M:%S'
    loglevel = logging.DEBUG if app.debug else logging.INFO
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    root_logger = logging.getLogger('')
    root_logger.setLevel(logging.DEBUG)

    # Keep the old way to setup logging in settings.py or config.py, example:
    # LOGFILE = '/var/log/resultsdb/resultsdb.log'
    # FILE_LOGGING = False
    # SYSLOG_LOGGING = False
    # STREAM_LOGGING = True
    if app.config['STREAM_LOGGING']:
        print("doing stream logging")
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(loglevel)
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)
        app.logger.addHandler(stream_handler)

    if app.config['SYSLOG_LOGGING']:
        print("doing syslog logging")
        syslog_handler = logging.handlers.SysLogHandler(address='/dev/log',
                                                        facility=logging.handlers.SysLogHandler.LOG_LOCAL4)
        syslog_handler.setLevel(loglevel)
        syslog_handler.setFormatter(formatter)
        root_logger.addHandler(syslog_handler)
        app.logger.addHandler(syslog_handler)

    if app.config['FILE_LOGGING'] and app.config['LOGFILE']:
        print("doing file logging to %s" % app.config['LOGFILE'])
        file_handler = logging.handlers.RotatingFileHandler(
            app.config['LOGFILE'], maxBytes=500000, backupCount=5)
        file_handler.setLevel(loglevel)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        app.logger.addHandler(file_handler)


setup_logging()

if app.config['SHOW_DB_URI']:
    app.logger.debug('using DBURI: %s' % app.config['SQLALCHEMY_DATABASE_URI'])

db = SQLAlchemy(app)

from resultsdb.controllers.main import main
app.register_blueprint(main)

from resultsdb.controllers.api_v2 import api as api_v2
app.register_blueprint(api_v2, url_prefix="/api/v2.0")

from resultsdb.controllers.api_v3 import api as api_v3, oidc
app.register_blueprint(api_v3, url_prefix="/api/v3")

if app.config['AUTH_MODULE'] == 'oidc':
    @app.route("/auth/oidclogin")
    @oidc.require_login
    def login():
        return {
            'username': oidc.user_getfield(app.config["OIDC_USERNAME_FIELD"]),
            'token': oidc.get_access_token(),
        }

    oidc.init_app(app)
    app.oidc = oidc
    app.logger.info('OpenIDConnect authentication is enabled')
else:
    app.logger.info('OpenIDConnect authentication is disabled')

app.logger.debug("Finished ResultsDB initialization")
